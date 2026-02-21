import os
import time
import random
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dashscope import MultiModalConversation
from pathlib import Path
import dashscope
from dotenv import load_dotenv

load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MaterialExtractor')

# 使用绝对路径加载prompt.txt
PROMPT_PATH = Path(__file__).parent / "prompt.txt"
if not PROMPT_PATH.exists():
    logger.error(f"prompt.txt 文件不存在: {PROMPT_PATH}")
    PROMPT_TXT = ""
else:
    PROMPT_TXT = open(PROMPT_PATH, encoding="utf-8").read()
    if not PROMPT_TXT.strip():
        logger.warning("prompt.txt 文件为空，Qwen 将无法正确提取数据！")

# 更新为qwen-vl-max-latest模型的配置
MODEL_NAME = "qwen-vl-max-latest"  # 使用qwen-vl-max-latest模型[7](@ref)
MAX_CONTEXT_LENGTH = 150000  # 从80K提升到150K，为图片和prompt留出106K空间[6](@ref)
MAX_IMAGES = 15
MAX_TOTAL_LENGTH = 128000  # qwen-vl-max-latest原生支持256K上下文[6](@ref)
MAX_TPM = 1000000  # 适当提高TPM限制以适应新模型
TOKEN_BUCKET = MAX_TPM
LAST_REFILL_TIME = time.time()
TOKEN_LOCK = threading.Lock()

def refill_token_bucket():
    """补充令牌桶"""
    global TOKEN_BUCKET, LAST_REFILL_TIME
    current_time = time.time()
    elapsed = current_time - LAST_REFILL_TIME
    if elapsed > 60:
        TOKEN_BUCKET = MAX_TPM
        LAST_REFILL_TIME = current_time
    else:
        refill_amount = (elapsed / 60) * MAX_TPM
        TOKEN_BUCKET = min(MAX_TPM, TOKEN_BUCKET + refill_amount)
        LAST_REFILL_TIME = current_time

def wait_for_tokens(required_tokens):
    """等待直到令牌桶中有足够令牌"""
    global TOKEN_BUCKET
    with TOKEN_LOCK:
        refill_token_bucket()
        while TOKEN_BUCKET < required_tokens:
            deficit = required_tokens - TOKEN_BUCKET
            wait_seconds = (deficit / MAX_TPM) * 60 + 0.1
            logger.info(f"TPM不足，需要等待{wait_seconds:.2f}秒 (需求:{required_tokens} 可用:{TOKEN_BUCKET:.0f})")
            time.sleep(wait_seconds)
            refill_token_bucket()
        
        TOKEN_BUCKET -= required_tokens
        logger.info(f"扣除{required_tokens} tokens，剩余:{TOKEN_BUCKET:.0f}")

def preprocess_context(context):
    """增强型文本预处理 - 移除不需要的部分，利用Qwen3-VL的长上下文优势"""
    sections_to_remove = [
        r'references?',
        r'acknowledg?e?ments?',
        r'data availability',
        r'declaration of competing interest',
        r'conflict of interest',
        r'funding',
        r'appendix',
    ]
    pattern = r'(?i)\n#*\s*(' + '|'.join(sections_to_remove) + r')[\s\S]*?(\n#|$)'
    context = re.sub(pattern, '', context)
    context = re.sub(r'(?i)(\n|^)\s*acknowledg?e?ments?[\s\S]*?(\n#|$)', '', context)
    return context[:MAX_CONTEXT_LENGTH]

def try_repair_json(json_str: str):
    """针对Qwen3-VL输出的JSON修复"""
    cleaned = json_str.strip()
    
    # 处理可能的输出格式
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON解析失败，尝试修复: {e}")
        
        # 尝试修复常见的格式问题
        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)  # 去除尾随逗号
        cleaned = re.sub(r'([{\[])\s*,', r'\1', cleaned)  # 去除开头逗号
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

def build_messages(text: str, img_abs_paths: list[str], prompt: str = None) -> list:
    """为Qwen3-VL构建消息格式 - 使用system角色传递提示词"""
    # 使用传入的提示词或默认提示词
    actual_prompt = prompt if prompt else PROMPT_TXT
    if not actual_prompt or not actual_prompt.strip():
        actual_prompt = "你是一个能从图文信息提取指标为json的智能助手，只输出提取出的json信息。"
        logger.warning("使用默认提示词，因为未提供有效的提示词")
    
    # 创建系统消息（包含提示词）
    system_msg = {
        "role": "system",
        "content": [{"text": actual_prompt}]
    }
    
    # 创建用户消息（包含论文文本和图片）
    user_content = [{"text": text}]
    
    # 添加图片 - Qwen3-VL支持更好的多图像处理
    for img_path in img_abs_paths:
        user_content.append({"image": f"file://{img_path}"})
    
    user_msg = {
        "role": "user", 
        "content": user_content
    }
    
    return [system_msg, user_msg]

def extract_once(md_file: str, prompt: str = None) -> tuple:
    """使用Qwen3-VL进行提取
    
    Args:
        md_file: Markdown文件路径
        prompt: 动态提示词（可选，如果不提供则使用默认PROMPT_TXT）
    
    Returns:
        (status, result) 元组
    """
    try:
        # 1. 读文本（含预处理）
        text = open(md_file, encoding="utf-8").read()
        text = preprocess_context(text)
        
        # 2. 解析md中所有图片路径
        md_dir = Path(md_file).parent
        fig_imgs = []
        
        # 改进的正则表达式，更好地匹配图片和对应的Fig描述
        pattern = re.compile(
            r'!\[\]\(images/([^)]+)\)[\s\S]*?(Fig\.|Figure|图)\s?\d+[\.\d]*\..*?(\n|$)',
            re.IGNORECASE | re.MULTILINE
        )
        
        for m in pattern.finditer(text):
            img_name = m.group(1)
            rel_path = f"images/{img_name}"
            abs_path = (md_dir / rel_path).resolve()
            if abs_path.exists():
                fig_imgs.append(str(abs_path))
                logger.info(f"找到带Fig.描述的图片: {img_name}")
            else:
                logger.warning(f"图片不存在: {abs_path}")

        if not fig_imgs:
            logger.info("未找到带Fig描述的图片，尝试文件名包含'fig'的图片")
            img_dir = md_dir / "images"
            if img_dir.exists():
                for p in img_dir.glob("*"):
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".gif"} and "fig" in p.stem.lower():
                        fig_imgs.append(str(p.resolve()))
                        logger.info(f"添加文件名含'fig'的图片: {p.name}")
        
        abs_imgs = fig_imgs[:MAX_IMAGES]
        logger.info(f"最终使用 {len(abs_imgs)} 张图片")

        # 3. 估算token - Qwen3-VL有更好的token效率
        estimated_tokens = len(text) // 3.5 + len(abs_imgs) * 1000
        
        # 4. 添加重试机制
        max_retries = 3
        rsp = None
        for attempt in range(max_retries):
            try:
                wait_for_tokens(estimated_tokens)
                rsp = MultiModalConversation.call(
                    model=MODEL_NAME,  # 使用Qwen3-VL-Plus模型
                    messages=build_messages(text, abs_imgs, prompt=prompt),
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                if rsp.status_code == 200:
                    break  # 成功则退出重试循环
                else:
                    logger.warning(f"API返回状态码异常: {rsp.status_code} (尝试 {attempt+1}/{max_retries})")
            except Exception as e:
                logger.warning(f"API调用失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        if not rsp or rsp.status_code != 200:
            error_msg = f"API错误: {getattr(rsp, 'message', 'Unknown error')}" if rsp else "API调用失败"
            raise RuntimeError(error_msg)
        
        # 5. 解析返回
        content = rsp.output.choices[0].message.content
        if isinstance(content, list) and content and "text" in content[0]:
            json_str = content[0]["text"]
            
            # 先尝试直接解析
            try:
                return ("success", json.loads(json_str))
            except json.JSONDecodeError:
                pass
            
            # 尝试修复
            repaired_obj = try_repair_json(json_str)
            if repaired_obj is not None:
                return ("success", repaired_obj)
            
            # 修复失败，返回原始响应
            return ("partial_data", json_str)
        else:
            return ("error", "API返回格式错误")
            
    except Exception as e:
        logger.error(f"处理失败: {e}")
        return ("error", str(e))

def should_skip_processing(output_path, error_output_path):
    """检查是否需要跳过处理（同时检查正常输出和错误输出）"""
    for path in [output_path, error_output_path]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content == '[]' or not content:
                        continue
                    if 'compressive' in content or 'error' in content:
                        return True
            except Exception:
                pass
    return False

def process_task(file_path, output_folder, error_output_folder, output_file):
    """处理单个文件任务"""
    logger.info(f"开始处理: {file_path}")
    start_time = time.time()
    
    try:
        # 调用extract_once函数
        status, result = extract_once(file_path)
        
        if status == "success":
            # 保存正常结果
            output_file_path = os.path.join(output_folder, output_file)
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            elapsed = time.time() - start_time
            logger.info(f"处理完成，耗时: {elapsed:.2f}秒")
            return ("success", 1)
        elif status == "partial_data":
            # 保存部分数据结果
            error_data = {
                "error": "部分数据修复失败",
                "raw_response": result,
                "source_file": file_path,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            error_file_path = os.path.join(error_output_folder, output_file)
            with open(error_file_path, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, ensure_ascii=False, indent=2)
            logger.warning(f"部分数据保存到: {error_file_path}")
            return ("partial_error", 0)
        else:
            # 保存错误结果
            error_file_path = os.path.join(error_output_folder, output_file)
            error_data = {
                "error": status,
                "raw_response": result,
                "source_file": file_path,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(error_file_path, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, ensure_ascii=False, indent=2)
            logger.error(f"处理失败，错误结果已保存到: {error_file_path}")
            return ("error", 0)
    except Exception as e:
        logger.error(f"任务执行失败: {file_path} - {e}")
        return ("error", 0)

def main():
    md_folder = "input"
    output_folder = "output"
    error_output_folder = "output_error"

    # 确保输出目录存在
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(error_output_folder, exist_ok=True)

    success_count = 0
    error_count = 0
    skipped_count = 0
    tasks = []

    # 收集任务
    for root, dirs, files in os.walk(md_folder):
        for file in files:
            if file == "full.md":
                file_path = os.path.join(root, file)
                folder_name = os.path.basename(root)

                # 提取PDF编号或名称
                match = re.match(r'^(\d+)', folder_name)
                if match:
                    pdf_number = match.group(1)
                    output_file = f"{pdf_number}.txt"
                else:
                    pdf_name = folder_name.split('-')[0] + ".pdf"
                    output_file = os.path.splitext(pdf_name)[0] + ".txt"

                output_path = os.path.join(output_folder, output_file)
                error_output_path = os.path.join(error_output_folder, output_file)
                
                # 检查是否跳过处理
                if should_skip_processing(output_path, error_output_path):
                    logger.info(f'跳过已处理文件: {output_file}')
                    skipped_count += 1
                    continue

                tasks.append((file_path, output_folder, error_output_folder, output_file))

    logger.info(f"共发现 {len(tasks)} 个需要处理的任务")

    # 使用线程池并发处理
    max_workers = min(3, len(tasks))  # 限制并发数避免过载
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for task in tasks:
            future = executor.submit(process_task, *task)
            futures.append(future)
        
        # 等待所有任务完成
        for future in as_completed(futures):
            try:
                status, count = future.result()
                if status == "success":
                    success_count += count
                elif status == "partial_error":
                    # 部分错误也计入错误计数
                    error_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.error(f"任务执行异常: {e}")
                error_count += 1

    logger.info(f"Qwen3-VL-Plus处理摘要: 成功 {success_count} 个, 失败 {error_count} 个, 跳过 {skipped_count} 个")

if __name__ == "__main__":
    main()