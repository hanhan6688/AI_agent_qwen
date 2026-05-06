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
import hashlib
import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
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
from qwen_process_url_new import extract_once, preprocess_context, MODEL_PRO, normalize_inference_config

PROMPT_MODE_FIELDS = "fields"
PROMPT_MODE_NATURAL = "natural"
DETERMINISTIC_CACHE_VERSION = "2026-04-28-v1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTRACTION_CACHE_DIR = PROJECT_ROOT / "data" / "extraction_cache"

COMMON_EXTRACTION_PROMPT = """你是一个专业的文档信息提取助手。请从提供的正文、图像、表格、图注和链接信息中提取关键内容，并严格按 JSON 格式输出。

输出规则：
1. 只能输出合法 JSON，不要输出解释、注释、Markdown、代码块或多余文字。
2. 最终输出的 JSON 必须包含 "data" 字段，且 "data" 必须是数组 []。即使只有一组结果，也必须用数组包裹。
3. 数组中每一项是一个对象，包含本次要求提取的所有字段。
4. 缺失信息统一填写 "NA"，不要使用 null、空字符串或省略字段。
5. 优先保留原文中的专有名词、单位、符号、英文大小写和编号。
6. 如果文档包含多组并列或对比实验数据（如多个样品、多种条件、多行表格），必须为每组数据输出一个独立的对象放入 "data" 数组，不要合并或只取最优组。
7. 如果来源是表格，请把每一行都展开为 "data" 数组中的一个独立对象；不要把整张表只总结成一个对象或一句话。
8. 表格行展开时，保留所有列名作为字段名，保留行表头、列分组、单位、脚注或实验条件说明，合并进对应字段的值中。
"""

def load_config(model_mode: str = "normal"):
    """加载环境变量。local 模式不强制要求 DashScope。"""
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

def build_field_schema_example(extract_fields) -> Dict[str, str]:
    """将字段配置转换成更直观的 JSON schema 示例。"""
    schema_example: Dict[str, str] = {}

    if isinstance(extract_fields, list):
        for index, field in enumerate(extract_fields, 1):
            if isinstance(field, dict):
                field_name = str(field.get("name", "")).strip()
                description = str(field.get("description", "")).strip()
            else:
                field_name = str(field).strip()
                description = ""

            if not field_name:
                continue
            schema_example[field_name] = description or f"字段{index}对应的提取结果"
    elif isinstance(extract_fields, dict):
        for field_name, description in extract_fields.items():
            normalized_name = str(field_name).strip()
            if not normalized_name:
                continue
            normalized_description = str(description).strip() if description is not None else ""
            schema_example[normalized_name] = normalized_description or "对应字段的提取结果"

    return schema_example


def build_exhaustive_extraction_rules() -> str:
    return (
        "\n补充要求：\n"
        "1. 每次提取时尽可能保留更多有效数据，不要因为摘要化而丢掉明显可提取的字段。\n"
        "2. 如果存在多组样品、多组条件、多行表格、多条曲线或多组对照，必须为每一组生成一个独立的 \"data\" 数组元素，不要只返回一组最优结果。\n"
        "3. 如果来源是表格，请把每一行都转换为 \"data\" 数组中的一个独立对象；不要把整张表只总结成一个对象或一句话。\n"
        "4. 表格行展开时，以用户指定的字段名为键，以该行对应列为值；如果表格有行表头、列分组、单位、脚注或条件说明，请合并进对应字段的值中，不要丢失单位和实验条件。\n"
    )


def extract_schema_from_custom_prompt(custom_prompt: str) -> Dict[str, str]:
    """尽量从自然语言 prompt 中提取字段规范，统一走字段模式思路。"""
    schema_example: Dict[str, str] = {}
    current_group_prefix = ""

    for raw_line in custom_prompt.splitlines():
        line = raw_line.strip().rstrip(",")
        if not line:
            continue

        if "mult-data" in line:
            current_group_prefix = "mult-data[]"
            continue

        if line.startswith("]"):
            current_group_prefix = ""
            continue

        match = re.match(r'["\']?([A-Za-z0-9_\-\.\[\]]+)["\']?\s*:\s*(.+)', line)
        if not match:
            continue

        field_name = match.group(1).strip()
        field_desc = match.group(2).strip().strip(",").strip()
        field_desc = field_desc.strip('"').strip("'")

        if not field_name:
            continue

        normalized_name = field_name
        if current_group_prefix and field_name in {"content", "image", "url"}:
            normalized_name = f"{current_group_prefix}.{field_name}"

        schema_example[normalized_name] = field_desc or "对应字段的提取结果"

    return schema_example


def build_prompt_from_fields(extract_fields) -> str:
    """
    从提取字段配置构建提示词，包含 few-shot 示例

    Args:
        extract_fields: 前端传入的提取字段配置
            - 数组格式: [{"name": "指标1", "description": "描述1"}, ...]
            - 字典格式: {"指标1": "描述1", "指标2": "描述2"}

    Returns:
        构建好的提示词字符串
    """
    if not extract_fields:
        return COMMON_EXTRACTION_PROMPT + "\n请根据文档内容提取最重要的信息，并输出一个包含 \"data\" 数组的 JSON 结果。"

    schema_example = build_field_schema_example(extract_fields)
    if not schema_example:
        logger.warning(f"未知的提取字段格式: {type(extract_fields)}")
        return COMMON_EXTRACTION_PROMPT + "\n请根据文档内容提取最重要的信息，并输出一个包含 \"data\" 数组的 JSON 结果。"

    field_names = list(schema_example.keys())
    field_descriptions = list(schema_example.values())

    # 构造 few-shot 示例值（根据字段描述推断示例值）
    def _guess_example_value(desc: str, index: int, variant: str = "A") -> str:
        """根据字段描述和索引，生成示例值"""
        desc_lower = desc.lower() if desc else ""
        if "温度" in desc_lower:
            return f"500 °C" if variant == "A" else f"600 °C"
        if "时间" in desc_lower:
            return f"2 h" if variant == "A" else f"4 h"
        if "浓度" in desc_lower:
            return f"0.1 mol/L" if variant == "A" else f"0.5 mol/L"
        if "名称" in desc_lower or "材料" in desc_lower:
            return f"样品{variant}" if variant == "A" else f"样品{variant}"
        if "催化" in desc_lower or "种类" in desc_lower:
            return f"催化剂{variant}" if variant == "A" else f"催化剂{variant}"
        if "率" in desc_lower or "比值" in desc_lower or "效率" in desc_lower:
            return f"85.2%" if variant == "A" else f"92.1%"
        if "方法" in desc_lower or "方式" in desc_lower:
            return f"方法{variant}"
        return f"示例值{variant}"

    # 构造单组示例
    single_example = {}
    for i, name in enumerate(field_names):
        desc = field_descriptions[i] if i < len(field_descriptions) else ""
        single_example[name] = _guess_example_value(desc, i, "A")

    # 构造多组示例
    multi_example_group1 = {}
    multi_example_group2 = {}
    for i, name in enumerate(field_names):
        desc = field_descriptions[i] if i < len(field_descriptions) else ""
        multi_example_group1[name] = _guess_example_value(desc, i, "A")
        multi_example_group2[name] = _guess_example_value(desc, i, "B")

    prompt = COMMON_EXTRACTION_PROMPT
    prompt += "\n本次需要提取的字段及说明：\n"

    for i, name in enumerate(field_names):
        desc = field_descriptions[i] if i < len(field_descriptions) else ""
        prompt += f"- {name}: {desc}\n"

    prompt += f"""
## 输出格式要求（重要！）

无论文档包含单组还是多组数据，"data" 都必须是数组。请严格遵循以下格式：

### 如果是单组数据（文档只涉及一种材料/条件）：
```json
{{
  "data": [
    {json.dumps(single_example, ensure_ascii=False, indent=4)}
  ]
}}
```

### 如果是多组对比数据（文档对比了多种材料/条件/参数）：
```json
{{
  "data": [
    {json.dumps(multi_example_group1, ensure_ascii=False, indent=4)},
    {json.dumps(multi_example_group2, ensure_ascii=False, indent=4)}
  ]
}}
```

请严格遵循以上格式：
- "data" 必须是数组，即使只有一组结果
- 每个数组元素是一个包含所有提取字段的对象
- 多组对比数据必须展开为多个独立对象，不要合并
- 缺失信息填 "NA"
"""
    prompt += build_exhaustive_extraction_rules()
    return prompt


def build_prompt_from_custom_text(custom_prompt: str) -> str:
    """为自然语言提示词套上一层统一的专业提取约束。"""
    extracted_schema = extract_schema_from_custom_prompt(custom_prompt)
    if extracted_schema:
        prompt = build_prompt_from_fields(extracted_schema)
        prompt += "\n以下是用户补充的提取要求，请继续优先遵循；如果和字段说明有冲突，以用户原始要求为准：\n"
        prompt += custom_prompt.strip()
        return prompt

    prompt = COMMON_EXTRACTION_PROMPT
    prompt += build_exhaustive_extraction_rules()
    prompt += "\n以下是用户补充的提取要求，请优先遵循；如果用户自定义了字段或结构，以用户要求为准，但仍必须只输出合法 JSON：\n"
    prompt += custom_prompt.strip()
    return prompt

def resolve_prompt_config(extract_fields: Optional[Any]) -> Dict[str, Any]:
    """兼容旧版字段数组和新版 prompt 配置对象。"""
    fields_config = extract_fields
    prompt_mode = PROMPT_MODE_FIELDS
    custom_prompt = None

    if isinstance(extract_fields, dict):
        looks_like_prompt_wrapper = any(
            key in extract_fields for key in ("promptMode", "customPrompt", "fields")
        )
        if looks_like_prompt_wrapper:
            fields_config = extract_fields.get("fields")
            prompt_mode = str(extract_fields.get("promptMode") or PROMPT_MODE_FIELDS).strip().lower()
            raw_custom_prompt = extract_fields.get("customPrompt")
            if isinstance(raw_custom_prompt, str) and raw_custom_prompt.strip():
                custom_prompt = raw_custom_prompt.strip()

    if prompt_mode not in {PROMPT_MODE_FIELDS, PROMPT_MODE_NATURAL}:
        logger.warning(f"未知提示词模式: {prompt_mode}，将回退到字段模式")
        prompt_mode = PROMPT_MODE_FIELDS

    return {
        "fields": fields_config,
        "prompt_mode": prompt_mode,
        "custom_prompt": custom_prompt
    }


def build_effective_prompt(extract_fields: Optional[Any]) -> Tuple[str, Dict[str, Any]]:
    """根据提示词模式生成最终发送给模型的 prompt。"""
    prompt_config = resolve_prompt_config(extract_fields)

    if prompt_config["prompt_mode"] == PROMPT_MODE_NATURAL:
        if prompt_config["custom_prompt"]:
            return build_prompt_from_custom_text(prompt_config["custom_prompt"]), prompt_config
        logger.warning("自然语言提示词模式未提供 customPrompt，回退为字段模式")
        prompt_config["prompt_mode"] = PROMPT_MODE_FIELDS

    return build_prompt_from_fields(prompt_config["fields"]), prompt_config


def _clone_json_safe(value: Any) -> Any:
    return copy.deepcopy(value)


def canonicalize_json(value: Any) -> Any:
    """递归规范化 JSON 结构，尽量让同结果拥有稳定键顺序。"""
    if isinstance(value, dict):
        return {key: canonicalize_json(value[key]) for key in sorted(value.keys())}
    if isinstance(value, list):
        return [canonicalize_json(item) for item in value]
    return value


def remove_runtime_fields(value: Any) -> Any:
    """移除任务运行期字段，避免污染跨任务缓存。"""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if key in {"_json_path", "_cache_hit"}:
                continue
            cleaned[key] = remove_runtime_fields(item)
        return cleaned
    if isinstance(value, list):
        return [remove_runtime_fields(item) for item in value]
    return value


def build_request_signature(file_path: str, prompt: str, model_mode: str,
                            inference_config: Dict[str, Any], prompt_mode: str) -> str:
    file_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            file_hash.update(chunk)

    payload = {
        "cache_version": DETERMINISTIC_CACHE_VERSION,
        "file_sha256": file_hash.hexdigest(),
        "prompt": prompt.strip(),
        "model_mode": model_mode,
        "prompt_mode": prompt_mode,
        "inference_config": canonicalize_json(inference_config)
    }
    signature_source = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(signature_source.encode("utf-8")).hexdigest()


def load_cached_extraction(signature: str) -> Optional[Dict[str, Any]]:
    cache_file = EXTRACTION_CACHE_DIR / f"{signature}.json"
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning(f"读取确定性缓存失败: {cache_file} -> {exc}")
        return None


def save_cached_extraction(signature: str, result: Dict[str, Any]) -> None:
    cache_file = EXTRACTION_CACHE_DIR / f"{signature}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        normalized = canonicalize_json(remove_runtime_fields(result))
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning(f"写入确定性缓存失败: {cache_file} -> {exc}")


def extract_field_names(extract_fields) -> List[str]:
    """从提取字段配置中提取所有字段名"""
    field_names = []
    if isinstance(extract_fields, list):
        for field in extract_fields:
            if isinstance(field, dict):
                name = field.get("name", "")
                if name:
                    field_names.append(name)
            elif isinstance(field, str):
                field_names.append(field)
    elif isinstance(extract_fields, dict):
        # 检查是否有嵌套的 fields 数组（double-encoded 格式）
        if "fields" in extract_fields and isinstance(extract_fields["fields"], list):
            for field in extract_fields["fields"]:
                if isinstance(field, dict):
                    name = field.get("name", "")
                    if name:
                        field_names.append(name)
                elif isinstance(field, str):
                    field_names.append(field)
        else:
            field_names = list(extract_fields.keys())
    return field_names


def filter_result_fields(result: Dict, field_names: List[str]) -> Dict:
    """只保留用户定义的字段，移除所有内部元数据"""
    if not field_names:
        return result

    filtered = {}
    for key in field_names:
        if key in result:
            filtered[key] = result[key]
        else:
            # 检查嵌套结构中的字段（如 mult-data 内的字段）
            for k, v in result.items():
                if isinstance(v, dict) and key in v:
                    filtered[key] = v[key]
                elif isinstance(v, list):
                    # 处理数组情况
                    for item in v:
                        if isinstance(item, dict) and key in item:
                            if key not in filtered:
                                filtered[key] = []
                            filtered[key].append(item[key])

    return filtered if filtered else result


def build_csv_friendly_output(result: Dict, field_names: List[str],
                               source_file: str = None) -> List[Dict]:
    """构建适合CSV/Excel导出的简洁输出，始终返回数组格式"""
    # 如果模型已返回 data 数组，直接使用（格式已在 prompt 中约束）
    model_data = result.get("data")
    if isinstance(model_data, list):
        return model_data

    # 回退：从旧格式模型中提取字段
    extracted_data = {}

    if field_names:
        for field in field_names:
            if field in result:
                extracted_data[field] = result[field]
            else:
                found = _find_field_in_nested(result, field)
                if found is not None:
                    extracted_data[field] = found
                else:
                    extracted_data[field] = "NA"
    else:
        skip_keys = {"_model_route", "_inference_config", "_prompt_mode",
                     "_custom_prompt_used", "_cache_hit", "_json_path", "data"}
        for k, v in result.items():
            if k not in skip_keys:
                if isinstance(v, (dict, list)):
                    extracted_data[k] = json.dumps(v, ensure_ascii=False)
                else:
                    extracted_data[k] = v

    # 始终返回数组格式
    return [extracted_data] if extracted_data else []


def _find_field_in_nested(data: Any, field_name: str) -> Any:
    """在嵌套结构中查找字段"""
    if isinstance(data, dict):
        if field_name in data:
            return data[field_name]
        for v in data.values():
            result = _find_field_in_nested(v, field_name)
            if result is not None:
                return result
    elif isinstance(data, list):
        results = []
        for item in data:
            result = _find_field_in_nested(item, field_name)
            if result is not None:
                results.append(result)
        if results:
            return results[0] if len(results) == 1 else results
    return None


def write_task_json(task_data_dir: Optional[Path], json_filename: str, source_file_name: str,
                    file_ext: str, result_data: Dict[str, Any],
                    user_field_names: List[str] = None) -> Optional[str]:
    if not task_data_dir:
        return None

    json_dir = task_data_dir / "json_data"
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / f"{json_filename}.json"

    # 构建适合CSV导出的简洁JSON
    csv_data = build_csv_friendly_output(result_data, user_field_names, source_file_name)

    # 保存带元数据的完整版（可选）
    json_result = {
        "status": "success",
        "source_file": source_file_name,
        "file_type": file_ext,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data": csv_data,
        "fields": user_field_names or []
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_result, f, ensure_ascii=False, indent=2)

    # 保存纯数据版，方便直接转CSV
    pure_data_path = json_dir / f"{json_filename}_data.json"
    with open(pure_data_path, "w", encoding="utf-8") as f:
        json.dump(csv_data, f, ensure_ascii=False, indent=2)

    return str(json_path)


def sanitize_inference_config(inference_config: Optional[Dict]) -> Dict:
    """规范化推理参数。"""
    return normalize_inference_config(inference_config)

def process_single_pdf(file_path: str, config: Dict, temp_work_dir: Path, 
                        task_data_dir: Optional[Path] = None, 
                        original_filename: Optional[str] = None,
                        extract_fields: Optional[Dict] = None,
                        model_mode: str = "normal",
                        inference_config: Optional[Dict] = None) -> Tuple[str, Dict]:
    """
    处理单个文件（PDF/JPG/PNG）的完整流程
    
    Args:
        file_path: 文件的完整路径（支持 PDF、JPG、PNG）
        config: 配置字典
        temp_work_dir: 临时工作目录
        task_data_dir: 任务数据目录（用于保存JSON结果）
        original_filename: 原始文件名（用于命名JSON）
        extract_fields: 前端传入的提取字段配置
        model_mode: 模型模式
            - "normal": 普通版 - 智能路由；无图片输入走 qwen-long，有图片输入走 qwen3.6-plus
            - "pro": 专业版 - 先由 qwen3-vl-plus 预筛选/理解图片，再交给 qwen3.6-plus 统一提取
    
    Returns:
        (status, result) 元组
    """
    input_file = Path(file_path)
    if not input_file.exists():
        return "error", {"error": f"文件不存在: {file_path}"}
    
    # 检查文件类型
    file_ext = input_file.suffix.lower()
    supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
    if file_ext not in supported_extensions:
        return "error", {"error": f"不支持的文件类型: {file_ext}，支持的类型: {supported_extensions}"}
    
    # 用于保存JSON的文件名 - 使用文件的UUID文件名，与input文件夹名称一致
    json_filename = input_file.stem
    
    try:
        # 检查是否已存在该文件对应的MinerU处理结果
        md_file = None
        if task_data_dir:
            mineru_output_base = task_data_dir / "input"
            # 根据文件名（UUID）查找对应的处理结果目录
            file_uuid = input_file.stem  # 文件名就是UUID
            # 支持多种可能的目录命名模式 (pdf-id, jpg-id, jpeg-id, png-id)
            possible_ids = [
                f"{file_uuid}{file_ext}-id",  # 当前扩展名
                f"{file_uuid}.pdf-id",  # 兼容旧数据
            ]
            for possible_id in possible_ids:
                expected_md = mineru_output_base / possible_id / "full.md"
                if expected_md.exists():
                    md_file = expected_md
                    logger.info(f"✅ 发现已存在的MinerU处理结果: {md_file}")
                    break
            
            if not md_file and mineru_output_base.exists():
                # 尝试其他可能的命名模式
                for subdir in mineru_output_base.iterdir():
                    if subdir.is_dir() and subdir.name.startswith(file_uuid):
                        potential_md = subdir / "full.md"
                        if potential_md.exists():
                            md_file = potential_md
                            logger.info(f"✅ 发现已存在的MinerU处理结果: {md_file}")
                            break
        
        # 如果没有已存在的结果，则调用MinerU处理
        if not md_file:
            # 兼容旧的 pdf 目录和新的 files 目录
            old_pdf_dir = task_data_dir / "pdf" if task_data_dir else None
            new_files_dir = task_data_dir / "files" if task_data_dir else None
            
            # 检查文件在哪个目录
            actual_file_dir = None
            if new_files_dir and (new_files_dir / input_file.name).exists():
                actual_file_dir = new_files_dir
            elif old_pdf_dir and (old_pdf_dir / input_file.name).exists():
                actual_file_dir = old_pdf_dir
            else:
                actual_file_dir = new_files_dir  # 默认使用新目录
            logger.info(f"=== 步骤1: 上传文件到MinerU - {input_file.name} ===")
            mineru_input_dir = temp_work_dir / "mineru_input"
            mineru_input_dir.mkdir(exist_ok=True)
            
            # 创建临时文件
            temp_file = mineru_input_dir / input_file.name
            shutil.copy2(input_file, temp_file)
            
            # 上传并等待处理
            batch_id = upload_batch([temp_file])
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
        
        # 步骤4: 使用Qwen提取信息
        logger.info("=== 步骤4: 使用Qwen提取信息 ===")
        logger.info(f"处理文件: {input_file.name}, 类型: {file_ext}")
        # 构建动态提示词
        prompt, prompt_config = build_effective_prompt(extract_fields)
        prompt_mode = prompt_config.get("prompt_mode", PROMPT_MODE_FIELDS)
        custom_prompt = prompt_config.get("custom_prompt")
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
        
        # 记录模型模式
        if model_mode not in {"normal", "pro"}:
            logger.warning(f"Unsupported model_mode={model_mode}, fallback to normal")
            model_mode = "normal"

        if model_mode == "pro":
            mode_text = "专业版 (qwen3.6-plus + qwen3-vl-plus 预筛选)"
        else:
            mode_text = "普通版 (智能路由：qwen-long / qwen3.6-plus，无前置筛图)"
        logger.info(f"模型模式: {mode_text}")
        inference_config = sanitize_inference_config(inference_config)
        logger.info(f"推理参数: {inference_config}")

        # 提前提取字段名（供后续使用）
        user_field_names = extract_field_names(extract_fields)

        cache_signature = build_request_signature(
            str(input_file),
            prompt,
            model_mode,
            inference_config,
            prompt_mode
        )
        cached_result = load_cached_extraction(cache_signature)
        if cached_result is not None:
            runtime_result = _clone_json_safe(cached_result)
            runtime_result["_cache_hit"] = True
            json_path = write_task_json(
                task_data_dir,
                json_filename,
                original_filename or input_file.name,
                file_ext,
                runtime_result,
                user_field_names
            )
            if json_path:
                runtime_result["_json_path"] = json_path
            logger.info(f"命中确定性缓存: {cache_signature}")
            return "success", runtime_result

        status, result = extract_once(
            str(md_file),
            prompt=prompt,
            model_mode=model_mode,
            inference_config=inference_config
        )
        
        if status == "success":
            result["_prompt_mode"] = prompt_mode
            result["_custom_prompt_used"] = bool(custom_prompt)
            result["_cache_hit"] = False
            normalized_result = canonicalize_json(remove_runtime_fields(result))
            save_cached_extraction(cache_signature, normalized_result)
            result = _clone_json_safe(normalized_result)

            json_path = write_task_json(
                task_data_dir,
                json_filename,
                original_filename or input_file.name,
                file_ext,
                result,
                user_field_names
            )
            if json_path:
                logger.info(f"JSON已保存: {json_path}")
                result["_json_path"] = json_path
            
            logger.info(f"=== 处理完成: {input_file.name} ===")
            return "success", result
        elif status == "partial_data":
            logger.warning(f"部分数据提取成功: {input_file.name}")
            return "partial_success", {
                "warning": "部分数据提取成功",
                "raw_data": result
            }
        else:
            logger.error(f"Qwen提取失败: {input_file.name}")
            return "error", {"error": f"Qwen提取失败: {result}"}
            
    except Exception as e:
        logger.error(f"处理文件失败 {input_file.name}: {str(e)}", exc_info=True)
        return "error", {"error": str(e)}

def main():
    """主函数 - 从命令行接收输入"""
    if len(sys.argv) not in (2, 3):
        print(json.dumps({
            "status": "error",
            "message": "参数错误: 需要输入文件路径，提取字段JSON可选"
        }, ensure_ascii=False))
        sys.exit(1)
    
    input_file = sys.argv[1]
    extract_fields_json = sys.argv[2] if len(sys.argv) >= 3 else None
    
    try:
        # 加载输入数据
        with open(input_file, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        task_id = input_data.get('taskId')
        task_name = input_data.get('taskName')
        file_info = input_data.get('fileInfo', {})
        file_path = file_info.get('filePath')
        original_filename = file_info.get('fileName')
        task_data_dir_str = file_info.get('taskDataDir')
        model_mode = input_data.get('modelMode', 'normal')  # 获取模型模式，默认普通版
        inference_config = input_data.get('inferenceConfig', {})
        embedded_extract_fields_json = input_data.get('extractFieldsJson')
        
        if not file_path:
            raise ValueError("filePath不能为空")
        
        # 兼容处理：如果传入的是相对文件名，尝试在 files 或 pdf 目录中查找
        task_data_dir = Path(task_data_dir_str) if task_data_dir_str else None
        if task_data_dir and not Path(file_path).is_absolute():
            # 新目录结构：files/
            new_path = task_data_dir / "files" / file_path
            # 旧目录结构：pdf/
            old_path = task_data_dir / "pdf" / file_path
            
            if new_path.exists():
                file_path = str(new_path)
            elif old_path.exists():
                file_path = str(old_path)
            else:
                # 默认使用新路径
                file_path = str(new_path)
        
        # 解析提取字段配置
        extract_fields = None
        effective_extract_fields_json = extract_fields_json or embedded_extract_fields_json
        if effective_extract_fields_json:
            try:
                extract_fields = json.loads(effective_extract_fields_json)
                logger.info(f"提取字段配置: {extract_fields}")
            except json.JSONDecodeError as e:
                logger.warning(f"解析提取字段JSON失败: {e}")
        
        if model_mode not in {"normal", "pro"}:
            logger.warning(f"Unsupported model_mode={model_mode}, fallback to normal")
            model_mode = "normal"

        if model_mode == "pro":
            mode_text = "专业版"
        else:
            mode_text = "普通版"
        logger.info(f"开始处理任务: taskId={task_id}, taskName={task_name}, file={file_path}, 模式={mode_text}")
        
        # 加载配置
        config = load_config(model_mode=model_mode)
        
        # 创建临时工作目录（使用绝对路径避免并发冲突）
        temp_work_dir = (task_data_dir / f".temp_task_{task_id}") if task_data_dir else PROJECT_ROOT / "data" / f".temp_task_{task_id}"
        temp_work_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 处理文件（支持 PDF/JPG/PNG）
            status, result = process_single_pdf(
                file_path, config, temp_work_dir, 
                task_data_dir=task_data_dir,
                original_filename=original_filename,
                extract_fields=extract_fields,
                model_mode=model_mode,
                inference_config=inference_config
            )
            
            # 从结果中获取实际使用的模型
            actual_model = result.get("_model_route", {}).get("model", "unknown") if isinstance(result, dict) else "unknown"

            # 提取用户定义的字段名
            user_field_names = extract_field_names(extract_fields)
            # 构建适合CSV导出的简洁数据
            csv_friendly_data = build_csv_friendly_output(result, user_field_names, original_filename)

            # 构建输出
            if status == "success":
                output = {
                    "status": "success",
                    "message": "处理完成",
                    "data": csv_friendly_data,  # 只保留用户字段
                    "fields": user_field_names,  # 字段列表，方便CSV转换
                    "confidence": 0.95,
                    "model": actual_model,
                    "cache_hit": bool(result.get("_cache_hit"))
                }
            elif status == "partial_success":
                output = {
                    "status": "partial_success",
                    "message": "部分数据提取成功",
                    "data": build_csv_friendly_output(result.get("raw_data", {}), user_field_names, original_filename),
                    "fields": user_field_names,
                    "confidence": 0.7,
                    "model": actual_model,
                    "cache_hit": bool(result.get("_cache_hit"))
                }
            else:
                output = {
                    "status": "error",
                    "message": result.get("error", "未知错误"),
                    "fields": user_field_names
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
