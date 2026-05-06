import os
import time
import random
import json
import re
import logging
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dashscope import MultiModalConversation
from pathlib import Path
import dashscope
from dotenv import load_dotenv
from typing import Tuple, Optional, Dict, Any, List

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

# 模型配置
MODEL_VL = "qwen3-vl-plus"             # 仅专业版用于前置图片筛选/图表理解
MODEL_LONG = "qwen-long"              # 普通版纯文本/长文本路由模型
MODEL_PRO = "qwen3.6-plus"             # 普通版图片路线与专业版主抽取模型

# qwen3-vl-plus 参数配置（专业版前置筛选）
MAX_CONTEXT_LENGTH_VL = 254000        # qwen3-vl-plus 最大输入长度 254K
MAX_CONTEXT_LENGTH_LONG = 1000000     # qwen-long 支持超长上下文（1M tokens）

# qwen3.6-plus 参数配置（普通版/专业版主模型）
MAX_CONTEXT_LENGTH_PRO = 991000       # qwen3.6-plus 最大输入长度 991K
MAX_RPM_PRO = 30000                   # 专业版 RPM: 30000
MAX_TPM_PRO = 5000000                 # 专业版 TPM: 5M

# 普通版限流参数
MAX_RPM = 3000                        # RPM: 每分钟请求数限制
MAX_TPM = 5000000                     # TPM: 每分钟token数限制 (5M)

# 令牌桶限流
TOKEN_BUCKET = MAX_TPM
REQUEST_BUCKET = MAX_RPM
LAST_REFILL_TIME = time.time()
TOKEN_LOCK = threading.Lock()


# ============== 图片过滤与理解 ==============
class ImageFilter:
    """图片过滤与理解 - 使用 qwen3-vl-plus 预筛选"""

    # 无关图片的关键词
    IRRELEVANT_PATTERNS = [
        r'logo', r'图标', r'avatar', r'头像',
        r'广告', r'advertisement', r'sponsor', r'品牌',
        r'水印', r'watermark', r'装饰', r'decoration',
    ]

    # 相关图片的关键词（与指标提取相关）
    RELEVANT_KEYWORDS = [
        r'图', r'figure', r'table', r'表', r'chart', r'图表',
        r'数据', r'data', r'结果', r'result', r'分析',
        r'趋势', r'对比', r'comparison', r'statis',
        r'panel', r'坐标', r'坐标轴', r'分布', r'曲线', r'热图',
        r'散点', r'柱状', r'折线', r'示意', r'流程', r'密度',
        r'能量', r'场', r'trajectory', r'colorbar',
    ]

    def __init__(self):
        self._stats = {"total": 0, "filtered": 0, "kept": 0}

    def _is_relevant_image(self, image_type: str, description: str) -> Tuple[bool, str]:
        """
        判断图片是否与指标提取相关

        Args:
            image_type: VL模型输出的图片类型
            description: VL模型对图片的描述

        Returns:
            (is_relevant, reason) - 是否相关及原因
        """
        type_lower = (image_type or "").lower()
        desc_lower = description.lower()

        # 科研场景下，只要模型认为是图表/表格/示意图，优先保留
        if type_lower in {"chart", "table", "diagram"}:
            return True, f"图片类型相关: {type_lower}"

        # 检查是否是不相关的类型
        for pattern in self.IRRELEVANT_PATTERNS:
            if re.search(pattern, desc_lower):
                return False, f"图片类型无关: 匹配模式 '{pattern}'"

        # 检查是否包含相关关键词
        for keyword in self.RELEVANT_KEYWORDS:
            if re.search(keyword, desc_lower):
                return True, f"图片与指标提取相关: 匹配关键词 '{keyword}'"

        # 如果图片有文字内容描述，检查是否包含数据/指标相关词汇
        if any(word in desc_lower for word in ['数据', '指标', '数值', '百分比', '%', 'count', 'number']):
            return True, "图片包含数据/指标相关描述"

        # 默认保留（宁可多保留也不漏掉）
        return True, "默认保留"

    def _call_vl_for_image_description(self, image_path: str, prompt: str = None) -> Tuple[str, str, str]:
        """
        调用 qwen3-vl-plus 解析单张图片

        Returns:
            (image_type, description, table_json_or_reason) - 图片类型、图片描述或表格JSON
        """
        default_prompt = """你是一个图片分析助手。请分析这张图片：
1. 如果是图表/表格/数据图，请描述图表内容并尽量逐行提取其中的结构化数据
2. 如果是示意图/流程图，请描述其含义
3. 如果是普通图片（logo/头像/装饰等），请说明图片类型
4. 如果图片中存在表格，请把每一行都作为 table_data.rows 的一个对象，尽量保留所有列名、单位、脚注和条件说明

请用JSON格式输出：
{
  "type": "chart/table/diagram/photo",
  "description": "图片描述",
  "table_data": {
    "caption": "表格或图表标题，没有则填NA",
    "columns": ["列名1", "列名2"],
    "rows": [
      {"列名1": "第1行值1", "列名2": "第1行值2"},
      {"列名1": "第2行值1", "列名2": "第2行值2"}
    ],
    "notes": "单位、脚注或实验条件，没有则填NA"
  }
}"""

        actual_prompt = prompt or default_prompt

        messages = [
            {"role": "system", "content": [{"text": "你是一个图片分析助手，只输出JSON格式的分析结果。"}]},
            {"role": "user", "content": [
                {"text": actual_prompt},
                {"image": f"file://{image_path}"}
            ]}
        ]

        try:
            rsp = MultiModalConversation.call(
                model=MODEL_VL,
                messages=messages,
                temperature=0,
                top_p=1,
                top_k=1,
                response_format={"type": "json_object"}
            )

            if rsp.status_code == 200:
                content = rsp.output.choices[0].message.content
                if isinstance(content, list) and content and "text" in content[0]:
                    json_str = content[0]["text"]
                    try:
                        result = json.loads(json_str)
                        img_type = result.get("type", "unknown")
                        description = result.get("description", "")
                        table_data = result.get("table_data")

                        if table_data and img_type in ["table", "chart"]:
                            try:
                                if isinstance(table_data, str):
                                    structured = json.loads(table_data)
                                else:
                                    structured = table_data
                                return img_type, description, json.dumps(structured, ensure_ascii=False)
                            except:
                                return img_type, description, table_data

                        return img_type, description, ""
                    except json.JSONDecodeError:
                        return "unknown", json_str, ""
                return "unknown", str(content), ""
            else:
                return "unknown", f"API错误: {rsp.message}", ""
        except Exception as e:
            return "unknown", f"异常: {str(e)}", ""

    def _call_vl_batch_description(self, image_paths: List[str], prompt: str = None) -> List[Dict[str, Any]]:
        """
        批量调用 qwen3-vl-plus 一次性理解一批图片（最多4张，一次会话）

        Args:
            image_paths: 图片路径列表（最多4张）

        Returns:
            每张图片的分析结果列表
        """
        if not image_paths:
            return []

        # 简洁的提示词，直接分析，不要思考过程，只输出结构化分析结果
        analysis_prompt = """分析以下图片，每张图片输出一行JSON（不要换行，不要有任何其他内容）：
[图片文件名]: 类型 | 描述 | 表格数据(有表格才填JSON，没有填-)

类型只能是: chart / table / diagram / photo / logo
描述: 简洁描述图片内容，不超过50字
表格数据: 如果有表格则提取核心行列数据（行以;分隔），否则填-

输出示例（每行对应一张图片，不要加任何标记）：
image1.jpg: chart | 材料性能对比柱状图 | 样品A:12.5%; 样品B:15.3%; 样品C:18.1%
image2.jpg: table | 实验条件参数表 | 温度:300K; 压力:1atm; 时间:2h
image3.jpg: photo | SEM扫描图像 | -
image4.jpg: logo | 公司Logo | -"""

        user_content = [{"text": analysis_prompt}]
        for img_path in image_paths:
            user_content.append({"image": f"file://{img_path}"})

        messages = [
            {"role": "system", "content": [{"text": "你是一个图片分析助手，直接输出分析结果，不要输出思考过程，不要解释，只输出JSON格式的一行分析。"}]},
            {"role": "user", "content": user_content}
        ]

        try:
            rsp = MultiModalConversation.call(
                model=MODEL_VL,
                messages=messages,
                temperature=0,
                top_p=1,
                top_k=1,
                # thought 设为 false 禁用思考过程（如果API支持）
            )

            results = []
            if rsp.status_code == 200:
                content = rsp.output.choices[0].message.content
                if isinstance(content, list) and content and "text" in content[0]:
                    json_str = content[0]["text"]

                    # 解析每行：filename: type | description | table_data
                    for line in json_str.strip().split('\n'):
                        line = line.strip()
                        if not line or line.startswith('{'):
                            continue
                        # 格式: filename: type | description | table_data
                        parts = line.split(': ')
                        if len(parts) < 2:
                            continue
                        img_name = parts[0].strip()
                        rest = parts[1].strip()
                        subparts = rest.split('|')
                        if len(subparts) >= 1:
                            img_type = subparts[0].strip()
                        if len(subparts) >= 2:
                            description = subparts[1].strip()
                        if len(subparts) >= 3:
                            table_data = subparts[2].strip() if subparts[2].strip() != '-' else ''
                        else:
                            description = rest
                            table_data = ''

                        results.append({
                            "path": img_name,
                            "type": img_type if 'img_type' in locals() else "unknown",
                            "description": description if 'description' in locals() else "",
                            "table_data": table_data if 'table_data' in locals() else ""
                        })

            return results

        except Exception as e:
            logger.error(f"批量图片理解失败: {e}")
            return []

    def filter_images(self, image_paths: List[str], extract_keywords: List[str] = None) -> List[Dict[str, Any]]:
        """
        过滤图片并获取理解结果 - 并行批量处理，每批最多4张图，使用线程池并行处理所有批次

        Args:
            image_paths: 图片路径列表
            extract_keywords: 提取指标相关的关键词（用于判断相关性）

        Returns:
            保留的图片信息列表，每项包含: path, description, table_data, is_table
        """
        self._stats["total"] += len(image_paths)
        relevant_keywords = list(self.RELEVANT_KEYWORDS)
        if extract_keywords:
            relevant_keywords.extend(extract_keywords)

        # 分批：每批4张图片
        batch_size = 4
        batches = []
        for i in range(0, len(image_paths), batch_size):
            batches.append(image_paths[i:i + batch_size])

        logger.info(f"🖼️ 共 {len(image_paths)} 张图片，分 {len(batches)} 批并行处理，每批 {batch_size} 张")

        # 使用线程池并行处理所有批次
        all_results = []
        with ThreadPoolExecutor(max_workers=len(batches)) as executor:
            futures = {executor.submit(self._call_vl_batch_description, batch): i for i, batch in enumerate(batches)}
            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_result = future.result()
                    all_results.extend(batch_result)
                    logger.info(f"✅ 第 {batch_idx + 1}/{len(batches)} 批完成")
                except Exception as e:
                    logger.error(f"❌ 第 {batch_idx + 1} 批失败: {e}")

        logger.info(f"📊 并行处理完成，共 {len(all_results)} 个结果")

        # 匹配结果到图片路径
        kept_images = []
        for img_path in sorted(image_paths):
            img_name = Path(img_path).name

            # 匹配结果
            description = ""
            table_data = ""
            img_type = "unknown"
            for result in all_results:
                if result.get("path") and (img_name in result["path"] or result["path"] in img_name):
                    img_type = result.get("type", "unknown")
                    description = result.get("description", "")
                    table_data = result.get("table_data", "")
                    break

            # 判断是否相关
            original_keywords = self.RELEVANT_KEYWORDS
            self.RELEVANT_KEYWORDS = relevant_keywords
            try:
                is_relevant, reason = self._is_relevant_image(img_type, description)
            finally:
                self.RELEVANT_KEYWORDS = original_keywords

            if is_relevant:
                kept_images.append({
                    "path": img_path,
                    "type": img_type,
                    "description": description,
                    "table_data": table_data,
                    "is_table": bool(table_data)
                })
                self._stats["kept"] += 1
            else:
                self._stats["filtered"] += 1

        logger.info(f"📊 图片过滤结果: 总计 {self._stats['total']}, 保留 {self._stats['kept']}, 过滤 {self._stats['filtered']}")
        return kept_images

    def get_stats(self) -> Dict[str, int]:
        return self._stats


# 全局图片过滤器实例
_image_filter = ImageFilter()


def filter_and_understand_images(image_paths: List[str], extract_keywords: List[str] = None) -> Tuple[List[Dict], List[str]]:
    """
    过滤图片并获取理解结果

    Returns:
        (kept_image_info, original_paths) - 保留的图片信息列表和原始路径列表
    """
    if not image_paths:
        return [], []

    kept_image_info = _image_filter.filter_images(image_paths, extract_keywords)
    original_paths = [img["path"] for img in kept_image_info]

    return kept_image_info, original_paths


# ============== 智能模型路由缓存 ==============
class ModelRouteCache:
    """智能模型路由缓存 - 缓存文档特征与模型选择的映射"""
    
    def __init__(self, cache_file: str = None):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cache_file = cache_file or str(Path(__file__).parent / ".model_route_cache.json")
        self._load_cache()
    
    def _load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"已加载模型路由缓存: {len(self._cache)} 条记录")
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
            self._cache = {}
    
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")
    
    def _compute_hash(self, text: str, image_count: int) -> str:
        """计算内容哈希（用于缓存键）"""
        # 使用文本前1000字符 + 图片数量生成哈希，减少计算量
        content = f"{text[:1000]}|{image_count}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get(self, text: str, image_count: int) -> Optional[Dict[str, Any]]:
        """获取缓存的路由决策"""
        content_hash = self._compute_hash(text, image_count)
        with self._lock:
            return self._cache.get(content_hash)
    
    def set(self, text: str, image_count: int, route_info: Dict[str, Any]):
        """缓存路由决策"""
        content_hash = self._compute_hash(text, image_count)
        with self._lock:
            self._cache[content_hash] = {
                **route_info,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_cache()
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        with self._lock:
            pro_count = sum(1 for v in self._cache.values() if v.get("model") == MODEL_PRO)
            long_count = sum(1 for v in self._cache.values() if v.get("model") == MODEL_LONG)
            return {
                "total": len(self._cache),
                "pro_model": pro_count,
                "long_model": long_count
            }


class ModelRouter:
    """智能模型路由器 - 根据文档特征选择最优模型"""
    
    # 图表相关的关键词模式
    FIGURE_PATTERNS = [
        r'Fig\.?\s*\d+',
        r'Figure\s*\d+',
        r'图\s*\d+',
        r'Table\s*\d+',
        r'表\s*\d+',
        r'Chart\s*\d+',
        r'图表\s*\d+',
        r'Abb\.?\s*\d+',
        r'Abbildung\s*\d+',  # 德语
    ]
    
    # 可能是图表的常见描述
    CHART_INDICATORS = [
        r'数据来源',
        r'source.*data',
        r'柱状图',
        r'饼图',
        r'折线图',
        r'scatter\s*plot',
        r'bar\s*chart',
        r'pie\s*chart',
        r'line\s*chart',
        r'histogram',
        r'热力图',
        r'heatmap',
    ]
    
    def __init__(self):
        self._cache = ModelRouteCache()
        self._stats = {"pro_calls": 0, "long_calls": 0, "cache_hits": 0}
        self._stats_lock = threading.Lock()
    
    def has_figures(self, text: str, image_paths: list) -> Tuple[bool, Dict[str, Any]]:
        """
        判断文档是否包含图表
        
        Returns:
            (has_figures, analysis_info) - 是否有图表，以及分析详情
        """
        analysis = {
            "text_length": len(text),
            "image_count": len(image_paths),
            "figure_mentions": [],
            "chart_indicators": [],
            "confidence": 0.0
        }
        
        # 1. 直接检查图片数量
        if len(image_paths) > 0:
            analysis["confidence"] = 0.9
            analysis["reason"] = "存在图片文件"
            return True, analysis
        
        # 2. 检查文本中的图表引用
        figure_mentions = []
        for pattern in self.FIGURE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                figure_mentions.extend(matches[:3])  # 每种模式最多记录3个
        
        analysis["figure_mentions"] = list(set(figure_mentions))
        
        # 3. 检查图表指示词
        chart_indicators = []
        for pattern in self.CHART_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                chart_indicators.append(pattern)
        
        analysis["chart_indicators"] = chart_indicators
        
        # 4. 计算置信度
        if figure_mentions:
            # 有图表引用，增加置信度
            analysis["confidence"] = min(0.5 + len(figure_mentions) * 0.1, 0.85)
            analysis["reason"] = f"文本中存在图表引用: {figure_mentions[:5]}"
            return True, analysis
        
        if chart_indicators:
            # 有图表指示词
            analysis["confidence"] = min(0.3 + len(chart_indicators) * 0.15, 0.75)
            analysis["reason"] = f"存在图表相关描述: {chart_indicators}"
            return True, analysis
        
        # 5. 无图表特征
        analysis["confidence"] = 0.9
        analysis["reason"] = "未检测到图表特征"
        return False, analysis
    
    def route(self, text: str, image_paths: list) -> Tuple[str, Dict[str, Any]]:
        """
        智能路由选择模型
        
        Returns:
            (model_name, route_info) - 选择的模型名和路由信息
        """
        # 1. 尝试从缓存获取
        cached = self._cache.get(text, len(image_paths))
        expected_model = MODEL_PRO if len(image_paths) > 0 else MODEL_LONG
        if cached and cached.get("model") == expected_model:
            with self._stats_lock:
                self._stats["cache_hits"] += 1
            logger.info(f"🎯 路由缓存命中: {cached['model']}")
            return cached["model"], cached
        if cached:
            logger.info(f"路由缓存包含旧模型 {cached.get('model')}，已忽略并重新计算")
        
        # 2. 分析文档特征
        has_fig, analysis = self.has_figures(text, image_paths)
        
        # 3. 选择模型：普通版只在实际存在图片输入时切到 qwen3.6-plus。
        has_image_assets = len(image_paths) > 0
        if has_image_assets:
            model = MODEL_PRO
            route_reason = f"检测到图片输入 → 使用主模型 {MODEL_PRO}（普通版不调用 qwen3-vl-plus）"
        else:
            model = MODEL_LONG
            route_reason = f"无图片输入 → 使用长文本模型 {MODEL_LONG}（正文中的图表文字引用仍按文本处理）"
        
        # 4. 构建路由信息
        route_info = {
            "model": model,
            "has_figures": has_fig,
            "has_image_assets": has_image_assets,
            "reason": route_reason,
            **analysis
        }
        
        # 5. 更新统计
        with self._stats_lock:
            if model == MODEL_PRO:
                self._stats["pro_calls"] += 1
            else:
                self._stats["long_calls"] += 1
        
        # 6. 缓存路由决策
        self._cache.set(text, len(image_paths), route_info)
        
        logger.info(f"🔀 智能路由: {route_reason}")
        return model, route_info
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        with self._stats_lock:
            return {
                **self._stats,
                "cache_stats": self._cache.get_stats()
            }


# 全局路由器实例
_model_router = ModelRouter()

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

def preprocess_context(context, model: str = MODEL_VL):
    """
    增强型文本预处理 - 移除不需要的部分
    
    Args:
        context: 原始文本
        model: 使用的模型，决定上下文长度限制
            - MODEL_VL: 限制 254K tokens
            - MODEL_LONG: 限制 1M tokens（几乎不截断）
            - MODEL_PRO: 限制 991K tokens（专业版）
    """
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
    
    # 根据模型类型决定截断长度
    if model == MODEL_LONG:
        max_length = MAX_CONTEXT_LENGTH_LONG
    elif model == MODEL_PRO:
        max_length = MAX_CONTEXT_LENGTH_PRO
    else:
        max_length = MAX_CONTEXT_LENGTH_VL
    
    if len(context) > max_length:
        logger.info(f"文本截断: {len(context)} → {max_length} (模型: {model})")
    
    return context[:max_length]

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
    """为多模态主模型构建消息格式 - 使用system角色传递提示词"""
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
    
    # 添加图片 - 普通版直接传原始图片，专业版传筛选后的图片
    for img_path in img_abs_paths:
        user_content.append({"image": f"file://{img_path}"})
    
    user_msg = {
        "role": "user", 
        "content": user_content
    }
    
    return [system_msg, user_msg]

def normalize_inference_config(inference_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """归一化推理参数，便于前后端统一传递。"""
    config = inference_config or {}
    normalized = {
        "temperature": float(config.get("temperature", 0) or 0),
        "top_p": float(config.get("topP", config.get("top_p", 1)) or 1),
        "top_k": int(config.get("topK", config.get("top_k", 1)) or 1),
        "max_tokens": int(config.get("maxTokens", config.get("max_tokens", 4096)) or 4096),
    }
    return normalized

def extract_once(md_file: str, prompt: str = None, model_mode: str = "normal",
                 inference_config: Optional[Dict[str, Any]] = None) -> tuple:
    """使用普通版/专业版链路进行提取
    
    Args:
        md_file: Markdown文件路径
        prompt: 动态提示词（可选，如果不提供则使用默认PROMPT_TXT）
        model_mode: 模型模式
            - "normal": 普通版 - 智能路由；无图片输入走 qwen-long，有图片输入走 qwen3.6-plus
            - "pro": 专业版 - qwen3-vl-plus 前置筛图/图表理解，再交给 qwen3.6-plus
    
    Returns:
        (status, result) 元组
    """
    try:
        inference_config = normalize_inference_config(inference_config)

        # 1. 读取原始文本（先不预处理，用于路由判断）
        raw_text = open(md_file, encoding="utf-8").read()
        
        # 2. 解析md中所有图片路径（不限数量）
        md_dir = Path(md_file).parent
        fig_imgs = []
        
        # 改进的正则表达式，更好地匹配图片和对应的Fig描述
        pattern = re.compile(
            r'!\[\]\(images/([^)]+)\)[\s\S]*?(Fig\.|Figure|图)\s?\d+[\.\d]*\..*?(\n|$)',
            re.IGNORECASE | re.MULTILINE
        )
        
        for m in pattern.finditer(raw_text):
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
                for p in sorted(img_dir.glob("*"), key=lambda item: item.name):
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".gif"} and "fig" in p.stem.lower():
                        fig_imgs.append(str(p.resolve()))
                        logger.info(f"添加文件名含'fig'的图片: {p.name}")
        
        # 不再限制图片数量，全部传入
        abs_imgs = sorted(fig_imgs)
        logger.info(f"🖼️ 共找到 {len(abs_imgs)} 张图片")

        # 3. 🚀 模型选择逻辑
        if model_mode not in {"normal", "pro"}:
            logger.warning(f"Unsupported model_mode={model_mode}, fallback to normal")
            model_mode = "normal"

        if model_mode == "pro":
            # 专业版：先过滤图片，再使用 qwen3.6-plus
            selected_model = MODEL_PRO

            # 🚀 调用筛选多模态模型 (qwen3-vl-plus) 进行图片过滤和理解
            logger.info(f"🔍 专业版：调用筛选模型 qwen3-vl-plus 进行图片过滤...")
            kept_image_info, filtered_imgs = filter_and_understand_images(abs_imgs)

            route_info = {
                "model": selected_model,
                "has_figures": len(filtered_imgs) > 0,
                "reason": "专业版模式 → 先用 qwen3-vl-plus 过滤图片，再用 qwen3.6-plus 提取",
                "images_understood": kept_image_info,  # 包含图片描述和表格数据
                "original_image_count": len(abs_imgs),
                "filtered_image_count": len(filtered_imgs)
            }
            logger.info(f"📊 专业版图片过滤: 原始 {len(abs_imgs)} 张 → 保留 {len(filtered_imgs)} 张")
            logger.info(f"📊 图片理解结果数量: {len(kept_image_info)}")
        else:
            # 普通版：保留智能路由；无图片输入走 qwen-long，有图片输入走 qwen3.6-plus。
            selected_model, route_info = _model_router.route(raw_text, abs_imgs)
            route_info.update({
                "original_image_count": len(abs_imgs),
                "filtered_image_count": len(abs_imgs),
                "images_understood": []
            })
            logger.info(f"📊 普通版智能路由: 模型={selected_model}, 原因={route_info.get('reason', 'N/A')}")
        
        # 4. 根据模型类型进行文本预处理（不同模型有不同的上下文限制）
        text = raw_text

        # 专业版：使用过滤后的图片，并添加图片理解结果到文本
        if model_mode == "pro":
            # 使用过滤后的图片
            abs_imgs = filtered_imgs
            logger.info(f"📊 使用过滤后图片数量: {len(abs_imgs)}")

            # 将图片理解结果添加到文本上下文中
            if kept_image_info:
                image_context = "\n\n=== 图片理解结果 ===\n"
                for i, img_info in enumerate(kept_image_info, 1):
                    image_name = Path(img_info.get("path", "")).name or f"image_{i}"
                    image_context += f"\n图片 {i} ({image_name}): {img_info['description']}"
                    if img_info.get('table_data'):
                        image_context += (
                            "\n表格数据（请在最终结果中按 rows 逐行展开为 mult-data 条目，"
                            "不要只做摘要）: "
                            f"{img_info['table_data']}"
                        )
                text = text + image_context
                logger.info(f"📝 已将图片理解结果添加到上下文中")

        text = preprocess_context(text, model=selected_model)
        logger.info(f"📄 文本长度: {len(text)} 字符 (模型: {selected_model})")

        # 5. 估算token
        if selected_model == MODEL_LONG:
            # 普通版纯文本/长文本路线。
            estimated_tokens = len(text) // 3.5
            logger.info(f"💰 qwen-long 纯文本估算: {estimated_tokens} tokens")
        elif selected_model == MODEL_PRO:
            # qwen3.6-plus 主模型：普通版图片路线使用原始图片，专业版使用筛选后图片。
            estimated_tokens = len(text) // 3.5 + len(abs_imgs) * 1000
            logger.info(f"💰 qwen3.6-plus 估算: 文本 {len(text)//3.5:.0f} + 图片 {len(abs_imgs)*1000} = {estimated_tokens:.0f} tokens")
        else:
            # qwen3-vl-plus
            estimated_tokens = len(text) // 3.5 + len(abs_imgs) * 1000
            logger.info(f"💰 qwen3-vl-plus 估算: 文本 {len(text)//3.5:.0f} + 图片 {len(abs_imgs)*1000} = {estimated_tokens:.0f} tokens")

        # 6. 调用模型 API
        return _call_cloud_model(text, abs_imgs, prompt, selected_model, route_info, estimated_tokens, inference_config)
            
    except Exception as e:
        logger.error(f"处理失败: {e}")
        return ("error", str(e))


def _call_cloud_model(text: str, abs_imgs: list, prompt: str, selected_model: str, 
                       route_info: dict, estimated_tokens: int, inference_config: dict) -> tuple:
    """调用云端模型（DashScope API）"""
    # 添加重试机制
    max_retries = 3
    rsp = None
    for attempt in range(max_retries):
        try:
            wait_for_tokens(estimated_tokens)
            
            # 根据模型类型构建不同的消息格式
            if selected_model == MODEL_LONG:
                # qwen-long 使用简单文本格式
                messages = build_messages_for_long(text, prompt=prompt)
            else:
                # qwen3.6-plus 使用多模态消息格式
                messages = build_messages(text, abs_imgs, prompt=prompt)
            
            rsp = MultiModalConversation.call(
                model=selected_model,
                messages=messages,
                temperature=inference_config.get("temperature", 0),
                top_p=inference_config.get("top_p", 1),
                top_k=inference_config.get("top_k", 1),
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
    
    # 解析返回
    content = rsp.output.choices[0].message.content
    if isinstance(content, list) and content and "text" in content[0]:
        json_str = content[0]["text"]
        
        # 先尝试直接解析
        try:
            result = json.loads(json_str)
            # 添加模型路由信息到结果
            result["_model_route"] = {
                "model": selected_model,
                "has_figures": route_info.get("has_figures"),
                "reason": route_info.get("reason"),
                "text_length": len(text)
            }
            result["_inference_config"] = inference_config
            return ("success", result)
        except json.JSONDecodeError:
            pass
        
        # 尝试修复
        repaired_obj = try_repair_json(json_str)
        if repaired_obj is not None:
            repaired_obj["_model_route"] = {
                "model": selected_model,
                "has_figures": route_info.get("has_figures"),
                "reason": route_info.get("reason"),
                "text_length": len(text)
            }
            repaired_obj["_inference_config"] = inference_config
            return ("success", repaired_obj)
        
        # 修复失败，返回原始响应
        return ("partial_data", json_str)
    else:
        return ("error", "API返回格式错误")


def build_messages_for_long(text: str, prompt: str = None) -> list:
    """为 qwen-long 构建消息格式（纯文本，无图片）"""
    actual_prompt = prompt if prompt else PROMPT_TXT
    if not actual_prompt or not actual_prompt.strip():
        actual_prompt = "你是一个能从文本信息提取指标为json的智能助手，只输出提取出的json信息。"
        logger.warning("使用默认提示词，因为未提供有效的提示词")
    return [
        {
            "role": "system",
            "content": actual_prompt
        },
        {
            "role": "user", 
            "content": text
        }
    ]

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

    logger.info(f"Qwen智能路由处理摘要: 成功 {success_count} 个, 失败 {error_count} 个, 跳过 {skipped_count} 个")
    
    # 输出路由统计
    stats = _model_router.get_stats()
    logger.info(
        f"📊 模型路由统计: qwen3.6-plus调用={stats.get('pro_calls', 0)}, "
        f"qwen-long调用={stats.get('long_calls', 0)}, 缓存命中={stats.get('cache_hits', 0)}"
    )
    logger.info(f"📦 缓存统计: {stats['cache_stats']}")

if __name__ == "__main__":
    main()
