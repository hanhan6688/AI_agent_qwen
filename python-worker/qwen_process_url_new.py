from __future__ import annotations

import os
import time
import json
import re
import logging
import hashlib
import threading
from dashscope import MultiModalConversation
from pathlib import Path
import dashscope
from dotenv import load_dotenv
from typing import Tuple, Optional, Dict, Any

# 导入本地模型客户端
try:
    from local_model_client import LocalModelClient, LocalModelConfig
    LOCAL_MODEL_AVAILABLE = True
except ImportError:
    LOCAL_MODEL_AVAILABLE = False

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
MODEL_VL = "qwen3-vl-plus"             # 视觉模型（带图表）- 普通版
MODEL_LONG = "qwen-long"              # 长文本模型（无图表）- 普通版
MODEL_PRO = "qwen3.5-plus"            # 专业版模型 - 更强大的推理能力

# qwen3-vl-plus 参数配置（普通版-视觉）
MAX_CONTEXT_LENGTH_VL = 254000        # qwen3-vl-plus 最大输入长度 254K
MAX_CONTEXT_LENGTH_LONG = 1000000     # qwen-long 支持超长上下文（1M tokens）

# qwen3.5-plus 参数配置（专业版）
MAX_CONTEXT_LENGTH_PRO = 991000       # qwen3.5-plus 最大输入长度 991K
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


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_generation_config(model_params: Optional[Dict[str, Any]],
                                 qwen_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    model_params = model_params or {}
    defaults = (qwen_config or {}).get("generationDefaults", {})

    config = {
        "temperature": _to_float(model_params.get("temperature"), _to_float(defaults.get("temperature"), 0.0)),
        "top_p": _to_float(
            model_params.get("top_p", model_params.get("topP")),
            _to_float(defaults.get("topP"), 0.9)
        ),
        "top_k": _to_int(
            model_params.get("top_k", model_params.get("topK")),
            _to_int(defaults.get("topK"), 20)
        ),
        "max_tokens": _to_int(
            model_params.get("max_tokens", model_params.get("maxTokens")),
            _to_int(defaults.get("maxTokens"), 2048)
        ),
        "repetition_penalty": _to_float(
            model_params.get("repetition_penalty", model_params.get("repetitionPenalty")),
            _to_float(defaults.get("repetitionPenalty"), 1.0)
        ),
        "presence_penalty": _to_float(
            model_params.get("presence_penalty", model_params.get("presencePenalty"))
        ),
        "frequency_penalty": _to_float(
            model_params.get("frequency_penalty", model_params.get("frequencyPenalty"))
        ),
        "seed": _to_int(model_params.get("seed")),
        "timeout": _to_int(model_params.get("timeout"), _to_int(defaults.get("timeout"), 600))
    }

    return {key: value for key, value in config.items() if value is not None}


def _normalize_local_model_config(model_params: Optional[Dict[str, Any]],
                                  qwen_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    model_params = model_params or {}
    local_defaults = (qwen_config or {}).get("localModelDefaults", {})
    generation_config = _normalize_generation_config(model_params, qwen_config)

    config = {
        "enabled": True,
        "base_url": model_params.get("baseUrl") or local_defaults.get("baseUrl"),
        "api_key": model_params.get("apiKey") or local_defaults.get("apiKey") or "EMPTY",
        "model": model_params.get("model") or local_defaults.get("model"),
        "provider": model_params.get("provider") or local_defaults.get("provider") or "openai-compatible",
        "vision_enabled": _to_bool(
            model_params.get("visionEnabled", local_defaults.get("visionEnabled")),
            True
        ),
    }
    config.update(generation_config)
    return config


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
            vl_count = sum(1 for v in self._cache.values() if v.get("model") == MODEL_VL)
            long_count = sum(1 for v in self._cache.values() if v.get("model") == MODEL_LONG)
            return {
                "total": len(self._cache),
                "vl_model": vl_count,
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
        self._stats = {"vl_calls": 0, "long_calls": 0, "cache_hits": 0}
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
        if cached:
            with self._stats_lock:
                self._stats["cache_hits"] += 1
            logger.info(f"🎯 路由缓存命中: {cached['model']}")
            return cached["model"], cached
        
        # 2. 分析文档特征
        has_fig, analysis = self.has_figures(text, image_paths)
        
        # 3. 选择模型
        if has_fig:
            model = MODEL_VL
            route_reason = f"检测到图表特征 → 使用视觉模型 {MODEL_VL}"
        else:
            model = MODEL_LONG
            route_reason = f"纯文本文档 → 使用长文本模型 {MODEL_LONG}（更快更经济）"
        
        # 4. 构建路由信息
        route_info = {
            "model": model,
            "has_figures": has_fig,
            "reason": route_reason,
            **analysis
        }
        
        # 5. 更新统计
        with self._stats_lock:
            if model == MODEL_VL:
                self._stats["vl_calls"] += 1
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

def extract_once(md_file: str, prompt: str = None, model_mode: str = "normal",
                 model_params: Optional[Dict[str, Any]] = None,
                 qwen_config: Optional[Dict[str, Any]] = None) -> tuple:
    """使用智能模型路由进行提取
    
    Args:
        md_file: Markdown文件路径
        prompt: 动态提示词（可选，如果不提供则使用默认PROMPT_TXT）
        model_mode: 模型模式
            - "normal": 普通版 - 智能路由（qwen3-vl-plus / qwen-long）
            - "pro": 专业版 - 统一使用 qwen3.5-plus（更强大，991K上下文）
            - "local": 本地模型 - 使用本地部署的模型（OpenAI 兼容 API）
    
    Returns:
        (status, result) 元组
    """
    try:
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
                for p in img_dir.glob("*"):
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".gif"} and "fig" in p.stem.lower():
                        fig_imgs.append(str(p.resolve()))
                        logger.info(f"添加文件名含'fig'的图片: {p.name}")
        
        # 不再限制图片数量，全部传入
        abs_imgs = fig_imgs
        logger.info(f"🖼️ 共找到 {len(abs_imgs)} 张图片")

        # 3. 🚀 模型选择逻辑
        if model_mode == "local":
            # 本地模型模式
            if not LOCAL_MODEL_AVAILABLE:
                raise RuntimeError("本地模型功能不可用，请确保 openai 库已安装: pip install openai")
            
            local_config = LocalModelConfig.load_from_env(
                defaults=(qwen_config or {}).get("localModelDefaults", {}),
                overrides=_normalize_local_model_config(model_params, qwen_config)
            )
            if not local_config.get("enabled"):
                logger.warning("本地模型未启用，将尝试加载配置...")
            
            selected_model = local_config.get("model", "local-model")
            generation_config = local_config.generation_config()
            route_info = {
                "model": selected_model,
                "has_figures": len(abs_imgs) > 0,
                "reason": f"本地模型模式 → 使用 {selected_model}（OpenAI 兼容 API）",
                "base_url": local_config.get("base_url"),
                "provider": local_config.get("provider")
            }
            logger.info(f"🖥️ 本地模型模式: {selected_model} @ {local_config.get('base_url')}")
        elif model_mode == "pro":
            # 专业版：统一使用 qwen3.5-plus
            selected_model = MODEL_PRO
            generation_config = _normalize_generation_config(model_params, qwen_config)
            route_info = {
                "model": selected_model,
                "has_figures": len(abs_imgs) > 0,
                "reason": "专业版模式 → 使用 qwen3.5-plus（更强推理能力，991K上下文）"
            }
            logger.info(f"📊 专业版模式: 使用 {selected_model}")
        else:
            # 普通版：智能路由
            selected_model, route_info = _model_router.route(raw_text, abs_imgs)
            generation_config = _normalize_generation_config(model_params, qwen_config)
            logger.info(f"📊 智能路由决策: 模型={selected_model}, 原因={route_info.get('reason', 'N/A')}")
        
        # 4. 根据模型类型进行文本预处理（不同模型有不同的上下文限制）
        # 本地模型不做预处理截断，由模型自己处理
        if model_mode == "local":
            text = raw_text  # 本地模型不截断
            estimated_tokens = len(text) // 3.5 + len(abs_imgs) * 1000
            logger.info(f"📄 本地模型文本长度: {len(text)} 字符")
            logger.info(f"💰 本地模型估算: 文本 {len(text)//3.5:.0f} + 图片 {len(abs_imgs)*1000} = {estimated_tokens:.0f} tokens")
        else:
            text = preprocess_context(raw_text, model=selected_model)
            logger.info(f"📄 文本长度: {len(text)} 字符 (模型: {selected_model})")
        
        # 5. 估算token
        if model_mode != "local":
            if selected_model == MODEL_LONG:
                # qwen-long 是纯文本模型，不计入图片token
                estimated_tokens = len(text) // 3.5
                logger.info(f"💰 qwen-long 纯文本估算: {estimated_tokens} tokens")
            elif selected_model == MODEL_PRO:
                # qwen3.5-plus 专业版
                estimated_tokens = len(text) // 3.5 + len(abs_imgs) * 1000
                logger.info(f"💰 qwen3.5-plus 估算: 文本 {len(text)//3.5:.0f} + 图片 {len(abs_imgs)*1000} = {estimated_tokens:.0f} tokens")
            else:
                # qwen3-vl-plus
                estimated_tokens = len(text) // 3.5 + len(abs_imgs) * 1000
                logger.info(f"💰 qwen3-vl-plus 估算: 文本 {len(text)//3.5:.0f} + 图片 {len(abs_imgs)*1000} = {estimated_tokens:.0f} tokens")
        
        # 6. 调用模型 API
        if model_mode == "local":
            # 本地模型调用
            return _call_local_model(text, abs_imgs, prompt, route_info, local_config)
        else:
            # 云端模型调用
            return _call_cloud_model(
                text, abs_imgs, prompt, selected_model, route_info, estimated_tokens, generation_config
            )
            
    except Exception as e:
        logger.error(f"处理失败: {e}")
        return ("error", str(e))


def _call_local_model(text: str, abs_imgs: list, prompt: str, route_info: dict,
                      local_config: LocalModelConfig) -> tuple:
    """调用本地模型"""
    try:
        client = LocalModelClient(local_config)
        
        logger.info(f"🚀 调用本地模型: {local_config.get('model')}")
        
        # 调用本地模型
        status, result = client.extract_json(
            text=text,
            image_paths=abs_imgs,
            prompt=prompt
        )
        
        if status == "success":
            # 添加模型路由信息
            result["_model_route"] = {
                "model": route_info.get("model"),
                "has_figures": route_info.get("has_figures"),
                "reason": route_info.get("reason"),
                "base_url": route_info.get("base_url"),
                "provider": route_info.get("provider"),
                "text_length": len(text)
            }
            result["generation_config"] = result.get("generation_config", client.generation_config_used())
            # 如果有思考内容，记录到日志
            if result.get("_local_model", {}).get("reasoning"):
                logger.info(f"💭 模型思考内容已记录")
            return ("success", result)
        elif status == "partial_data":
            # 尝试修复 JSON
            raw_content = result.get("raw_content", "")
            repaired_obj = try_repair_json(raw_content)
            if repaired_obj is not None:
                repaired_obj["_model_route"] = {
                    "model": route_info.get("model"),
                    "has_figures": route_info.get("has_figures"),
                    "reason": route_info.get("reason"),
                    "base_url": route_info.get("base_url"),
                    "provider": route_info.get("provider"),
                    "text_length": len(text)
                }
                repaired_obj["_local_model"] = {
                    "model": route_info.get("model"),
                    "base_url": route_info.get("base_url"),
                    "provider": route_info.get("provider"),
                    "reasoning": result.get("reasoning")
                }
                repaired_obj["generation_config"] = client.generation_config_used()
                return ("success", repaired_obj)
            return ("partial_data", result)
        else:
            return status, result
            
    except Exception as e:
        logger.error(f"本地模型调用失败: {e}")
        return ("error", str(e))


def _call_cloud_model(text: str, abs_imgs: list, prompt: str, selected_model: str,
                       route_info: dict, estimated_tokens: int,
                       generation_config: Optional[Dict[str, Any]] = None) -> tuple:
    """调用云端模型（DashScope API）"""
    # 添加重试机制
    max_retries = 3
    rsp = None
    generation_config = generation_config or {}
    for attempt in range(max_retries):
        try:
            wait_for_tokens(estimated_tokens)
            
            # 根据模型类型构建不同的消息格式
            if selected_model == MODEL_LONG:
                # qwen-long 使用简单文本格式
                messages = build_messages_for_long(text, prompt=prompt)
            else:
                # qwen-vl 使用多模态格式
                messages = build_messages(text, abs_imgs, prompt=prompt)
            
            call_kwargs = {
                "model": selected_model,
                "messages": messages,
                "temperature": generation_config.get("temperature", 0),
                "response_format": {"type": "json_object"}
            }
            if generation_config.get("top_p") is not None:
                call_kwargs["top_p"] = generation_config.get("top_p")
            if generation_config.get("max_tokens") is not None:
                call_kwargs["max_tokens"] = generation_config.get("max_tokens")

            rsp = MultiModalConversation.call(**call_kwargs)
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
            result["generation_config"] = generation_config
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
            repaired_obj["generation_config"] = generation_config
            return ("success", repaired_obj)
        
        # 修复失败，返回原始响应
        return ("partial_data", {
            "raw_content": json_str,
            "generation_config": generation_config
        })
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
    logger.info(f"📊 模型路由统计: VL模型调用={stats['vl_calls']}, Long模型调用={stats['long_calls']}, 缓存命中={stats['cache_hits']}")
    logger.info(f"📦 缓存统计: {stats['cache_stats']}")

if __name__ == "__main__":
    main()
