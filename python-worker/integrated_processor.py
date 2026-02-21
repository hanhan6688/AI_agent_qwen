#!/usr/bin/env python3
"""
集成处理器 - 统一处理PDF上传、MinerU解析和Qwen3-VL提取
支持按任务名组织目录结构，自动合并JSON到Excel
"""
import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import shutil

# 配置日志 - 输出到stderr，避免污染stdout（stdout用于输出JSON结果给Java）
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # 日志输出到stderr
)
logger = logging.getLogger('IntegratedProcessor')

# 将当前目录添加到Python路径，以便导入其他模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_process import upload_batch, wait_until_done, fetch_and_download, BATCH_SIZE
from qwen_process_url_new import extract_once, preprocess_context

def load_config():
    """加载环境变量"""
    from dotenv import load_dotenv
    load_dotenv()
    
    config = {
        'MINERU_API_KEY': os.getenv('MINERU_API_KEY'),
        'DASHSCOPE_API_KEY': os.getenv('DASHSCOPE_API_KEY'),
        'mineru_base_url': 'https://mineru.net/api/v4',
        'batch_size': 200
    }
    
    if not config['MINERU_API_KEY']:
        raise RuntimeError('MINERU_API_KEY环境变量未设置')
    if not config['DASHSCOPE_API_KEY']:
        raise RuntimeError('DASHSCOPE_API_KEY环境变量未设置')
    
    return config

def build_prompt_from_fields(extract_fields) -> str:
    """
    从提取字段配置构建提示词
    
    Args:
        extract_fields: 前端传入的提取字段配置
            - 数组格式: [{"name": "指标1", "description": "描述1"}, ...]
            - 字典格式: {"指标1": "描述1", "指标2": "描述2"}
    
    Returns:
        构建好的提示词字符串
    """
    if not extract_fields:
        return "你是一个能从图文信息提取指标为json的智能助手，只输出提取出的json信息。"
    
    prompt = "你是一个能从图文信息提取指标为json的智能助手，只输出提取出的json信息。\n\n你要提取的指标有：\n"
    
    # 支持两种格式：数组格式和字典格式
    if isinstance(extract_fields, list):
        # 数组格式: [{"name": "指标1", "description": "描述1"}, ...]
        for i, field in enumerate(extract_fields, 1):
            field_name = field.get('name', '') if isinstance(field, dict) else str(field)
            description = field.get('description', '') if isinstance(field, dict) else ''
            if field_name:
                prompt += f"{i}. {field_name}：{description}\n"
    elif isinstance(extract_fields, dict):
        # 字典格式: {"指标1": "描述1", "指标2": "描述2"}
        for i, (field_name, description) in enumerate(extract_fields.items(), 1):
            prompt += f"{i}. {field_name}：{description}\n"
    else:
        logger.warning(f"未知的提取字段格式: {type(extract_fields)}")
        return "你是一个能从图文信息提取指标为json的智能助手，只输出提取出的json信息。"
    
    prompt += "\n请以JSON格式输出，如果某字段无法从文本中提取，请设为null。"
    
    return prompt

def process_single_pdf(pdf_path: str, config: Dict, temp_work_dir: Path, 
                        task_data_dir: Optional[Path] = None, 
                        original_filename: Optional[str] = None,
                        extract_fields: Optional[Dict] = None) -> Tuple[str, Dict]:
    """
    处理单个PDF文件的完整流程
    
    Args:
        pdf_path: PDF文件的完整路径
        config: 配置字典
        temp_work_dir: 临时工作目录
        task_data_dir: 任务数据目录（用于保存JSON结果）
        original_filename: 原始文件名（用于命名JSON）
        extract_fields: 前端传入的提取字段配置
    
    Returns:
        (status, result) 元组
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        return "error", {"error": f"PDF文件不存在: {pdf_path}"}
    
    # 用于保存JSON的文件名 - 使用PDF的UUID文件名，与input文件夹名称一致
    json_filename = pdf_file.stem
    
    try:
        # 检查是否已存在该PDF对应的MinerU处理结果
        md_file = None
        if task_data_dir:
            mineru_output_base = task_data_dir / "input"
            # 根据PDF文件名（UUID）查找对应的处理结果目录
            pdf_uuid = pdf_file.stem  # PDF文件名就是UUID
            expected_md = mineru_output_base / f"{pdf_uuid}.pdf-id" / "full.md"
            if expected_md.exists():
                md_file = expected_md
                logger.info(f"✅ 发现已存在的MinerU处理结果: {md_file}")
            else:
                # 尝试其他可能的命名模式
                if mineru_output_base.exists():
                    for subdir in mineru_output_base.iterdir():
                        if subdir.is_dir() and subdir.name.startswith(pdf_uuid):
                            potential_md = subdir / "full.md"
                            if potential_md.exists():
                                md_file = potential_md
                                logger.info(f"✅ 发现已存在的MinerU处理结果: {md_file}")
                                break
        
        # 如果没有已存在的结果，则调用MinerU处理
        if not md_file:
            logger.info(f"=== 步骤1: 上传PDF到MinerU - {pdf_file.name} ===")
            mineru_input_dir = temp_work_dir / "mineru_input"
            mineru_input_dir.mkdir(exist_ok=True)
            
            # 创建临时PDF文件
            temp_pdf = mineru_input_dir / pdf_file.name
            shutil.copy2(pdf_file, temp_pdf)
            
            # 上传并等待处理
            batch_id = upload_batch([temp_pdf])
            logger.info(f"批次ID: {batch_id}")
            
            # 等待MinerU处理完成
            logger.info("=== 步骤2: 等待MinerU处理完成 ===")
            results = wait_until_done(batch_id)
            
            # 下载结果 - 直接下载到任务目录的input文件夹
            logger.info("=== 步骤3: 下载MinerU解析结果 ===")
            
            # 使用任务目录下的input文件夹存放MinerU处理结果
            if task_data_dir:
                mineru_output_base = task_data_dir / "input"
            else:
                mineru_output_base = temp_work_dir / "mineru_output"
            mineru_output_base.mkdir(parents=True, exist_ok=True)
            
            # 传入自定义输出目录给fetch_and_download（skip_batch_dir=True 直接输出到input目录）
            fetch_and_download(batch_id, results, output_dir=mineru_output_base, skip_batch_dir=True)
            
            # 查找full.md文件（现在直接在input目录下）
            md_files = list(mineru_output_base.rglob("full.md"))
            if not md_files:
                return "error", {"error": "MinerU未生成full.md文件"}
            
            md_file = md_files[0]
            logger.info(f"找到Markdown文件: {md_file}")
        
        # 步骤4: 使用Qwen3-VL提取信息
        logger.info("=== 步骤4: 使用Qwen3-VL提取信息 ===")
        # 构建动态提示词
        prompt = build_prompt_from_fields(extract_fields)
        # 安全地记录提取字段信息
        if extract_fields:
            if isinstance(extract_fields, list):
                field_names = [f.get('name', '') for f in extract_fields if isinstance(f, dict)]
                logger.info(f"提取字段: {field_names}")
            elif isinstance(extract_fields, dict):
                logger.info(f"提取字段: {list(extract_fields.keys())}")
            else:
                logger.info(f"提取字段: {extract_fields}")
        else:
            logger.info("提取字段: 默认")
        status, result = extract_once(str(md_file), prompt=prompt)
        
        if status == "success":
            # 保存JSON到任务目录
            if task_data_dir:
                json_dir = task_data_dir / "json_data"
                json_dir.mkdir(parents=True, exist_ok=True)
                json_path = json_dir / f"{json_filename}.json"
                
                # 构建完整的JSON结果
                json_result = {
                    "status": "success",
                    "source_file": original_filename or pdf_file.name,
                    "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "data": result
                }
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_result, f, ensure_ascii=False, indent=2)
                logger.info(f"JSON已保存: {json_path}")
                
                # 添加JSON路径到结果
                result["_json_path"] = str(json_path)
            
            logger.info(f"=== 处理完成: {pdf_file.name} ===")
            return "success", result
        elif status == "partial_data":
            logger.warning(f"部分数据提取成功: {pdf_file.name}")
            return "partial_success", {
                "warning": "部分数据提取成功",
                "raw_data": result
            }
        else:
            logger.error(f"Qwen3-VL提取失败: {pdf_file.name}")
            return "error", {"error": f"Qwen3-VL提取失败: {result}"}
            
    except Exception as e:
        logger.error(f"处理PDF失败 {pdf_file.name}: {str(e)}", exc_info=True)
        return "error", {"error": str(e)}

def main():
    """主函数 - 从命令行接收输入"""
    if len(sys.argv) != 3:
        print(json.dumps({
            "status": "error",
            "message": "参数错误: 需要输入文件路径和提取字段JSON"
        }, ensure_ascii=False))
        sys.exit(1)
    
    input_file = sys.argv[1]
    extract_fields_json = sys.argv[2]
    
    try:
        # 加载输入数据
        with open(input_file, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        task_id = input_data.get('taskId')
        task_name = input_data.get('taskName')
        file_info = input_data.get('fileInfo', {})
        pdf_path = file_info.get('filePath')
        original_filename = file_info.get('fileName')
        task_data_dir_str = file_info.get('taskDataDir')
        
        if not pdf_path:
            raise ValueError("filePath不能为空")
        
        # 解析提取字段配置
        extract_fields = None
        if extract_fields_json:
            try:
                extract_fields = json.loads(extract_fields_json)
                logger.info(f"提取字段配置: {extract_fields}")
            except json.JSONDecodeError as e:
                logger.warning(f"解析提取字段JSON失败: {e}")
        
        logger.info(f"开始处理任务: taskId={task_id}, taskName={task_name}, file={pdf_path}")
        
        # 加载配置
        config = load_config()
        
        # 创建临时工作目录
        temp_work_dir = Path(f"./temp_task_{task_id}")
        temp_work_dir.mkdir(exist_ok=True)
        
        # 任务数据目录
        task_data_dir = Path(task_data_dir_str) if task_data_dir_str else None
        
        try:
            # 处理PDF
            status, result = process_single_pdf(
                pdf_path, config, temp_work_dir, 
                task_data_dir=task_data_dir,
                original_filename=original_filename,
                extract_fields=extract_fields
            )
            
            # 构建输出
            if status == "success":
                output = {
                    "status": "success",
                    "message": "处理完成",
                    "data": result,
                    "confidence": 0.95,
                    "model": "qwen-vl-max-latest",
                    "mineru_processed": True,
                    "task_data_dir": str(task_data_dir) if task_data_dir else None
                }
            elif status == "partial_success":
                output = {
                    "status": "partial_success",
                    "message": "部分数据提取成功",
                    "data": result,
                    "confidence": 0.7,
                    "model": "qwen-vl-max-latest",
                    "task_data_dir": str(task_data_dir) if task_data_dir else None
                }
            else:
                output = {
                    "status": "error",
                    "message": result.get("error", "未知错误"),
                    "task_data_dir": str(task_data_dir) if task_data_dir else None
                }
            
            # 输出结果（Spring Boot会读取这个）
            print(json.dumps(output, ensure_ascii=False, indent=2))
            
        finally:
            # 清理临时文件
            if temp_work_dir.exists():
                shutil.rmtree(temp_work_dir)
            
            # 清理mineru的input目录（上传临时文件）
            mineru_input_dir = Path("./PDFS")
            if mineru_input_dir.exists():
                shutil.rmtree(mineru_input_dir)
            
            # 注意：不再清理input目录，因为MinerU处理结果现在存放在任务目录的input文件夹
            # 如果需要清理，可以手动删除任务目录
    
    except Exception as e:
        logger.error(f"主流程失败: {str(e)}", exc_info=True)
        error_output = {
            "status": "error",
            "message": str(e)
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
