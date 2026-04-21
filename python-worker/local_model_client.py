#!/usr/bin/env python3
"""
本地模型客户端 - 支持 OpenAI 兼容 API 调用
支持：本地部署模型、ModelScope、vLLM、Ollama 等 OpenAI 兼容服务
"""
import os
import json
import base64
import logging
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('LocalModelClient')

# 尝试导入 openai
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai 库未安装，本地模型功能不可用。请运行: pip install openai")


class LocalModelConfig:
    """本地模型配置"""
    
    # 默认配置
    DEFAULT_BASE_URL = "http://localhost:8000/v1"  # 默认本地服务地址
    DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"     # 默认模型名称
    
    # 支持的预设服务
    PRESETS = {
        "modelscope": {
            "base_url": "https://api-inference.modelscope.cn/v1",
            "models": ["Qwen/Qwen3-VL-8B-Thinking", "Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2-VL-7B-Instruct"]
        },
        "vllm": {
            "base_url": "http://localhost:8000/v1",
            "models": []  # 用户自定义
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "models": ["qwen2.5:7b", "qwen2-vl:7b", "llama3.1:8b"]
        },
        "lmstudio": {
            "base_url": "http://localhost:1234/v1",
            "models": []  # LM Studio 自动检测
        }
    }
    
    @classmethod
    def load_from_env(cls) -> Dict[str, Any]:
        """从环境变量加载配置"""
        return {
            "base_url": os.getenv("LOCAL_MODEL_BASE_URL", cls.DEFAULT_BASE_URL),
            "api_key": os.getenv("LOCAL_MODEL_API_KEY", "not-needed"),
            "model": os.getenv("LOCAL_MODEL_NAME", cls.DEFAULT_MODEL),
            "enabled": os.getenv("LOCAL_MODEL_ENABLED", "false").lower() == "true",
            "preset": os.getenv("LOCAL_MODEL_PRESET", ""),  # 可选预设名称
            "timeout": int(os.getenv("LOCAL_MODEL_TIMEOUT", "300")),  # 默认 5 分钟超时
            "max_tokens": int(os.getenv("LOCAL_MODEL_MAX_TOKENS", "4096")),
            "use_images": os.getenv("LOCAL_MODEL_USE_IMAGES", "true").lower() == "true",
        }
    
    @classmethod
    def get_preset_config(cls, preset_name: str) -> Optional[Dict[str, Any]]:
        """获取预设配置"""
        return cls.PRESETS.get(preset_name.lower())


class LocalModelClient:
    """
    本地模型客户端 - OpenAI 兼容 API
    
    支持：
    - 本地部署的模型（vLLM, Ollama, LM Studio 等）
    - ModelScope 推理 API
    - 其他 OpenAI 兼容服务
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化客户端
        
        Args:
            config: 配置字典，包含 base_url, api_key, model 等
        """
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai 库未安装，请运行: pip install openai")
        
        self.config = config or LocalModelConfig.load_from_env()
        
        # 如果有预设，应用预设配置
        if self.config.get("preset"):
            preset_config = LocalModelConfig.get_preset_config(self.config["preset"])
            if preset_config:
                # 预设配置作为默认值，仅在用户未显式配置时生效。
                for key, value in preset_config.items():
                    if key == "base_url" and self.config.get("base_url") == LocalModelConfig.DEFAULT_BASE_URL:
                        self.config["base_url"] = value
                    elif key == "models" and value and self.config.get("model") == LocalModelConfig.DEFAULT_MODEL:
                        self.config["model"] = value[0]
                    elif key not in self.config:
                        self.config[key] = value
        
        self.client = OpenAI(
            base_url=self.config["base_url"],
            api_key=self.config.get("api_key", "not-needed"),
            timeout=self.config.get("timeout", 300),
        )
        self.model = self.config["model"]
        
        logger.info(f"本地模型客户端初始化: base_url={self.config['base_url']}, model={self.model}")

    @staticmethod
    def _normalize_message_content(content: Any) -> str:
        """兼容不同 OpenAI 实现返回的字符串或内容块列表。"""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(text)
                elif hasattr(item, "text") and item.text:
                    parts.append(item.text)
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)
        return str(content)

    @staticmethod
    def _is_response_format_unsupported(error_message: str) -> bool:
        text = (error_message or "").lower()
        return (
            "response_format" in text
            or "json_object" in text
            or "json schema" in text
            or "extra fields not permitted" in text
            or "unsupported parameter" in text
        )

    @staticmethod
    def _is_image_input_unsupported(error_message: str) -> bool:
        text = (error_message or "").lower()
        return (
            "image_url" in text
            or "vision" in text
            or "multimodal" in text
            or "does not support image" in text
            or "unsupported content type" in text
        )
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为 base64"""
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # 判断图片类型
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp"
        }
        mime_type = mime_types.get(ext, "image/jpeg")
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_image}"
    
    def _build_image_url(self, image_path: str, use_base64: bool = True) -> Dict[str, Any]:
        """
        构建图片 URL 格式
        
        Args:
            image_path: 图片路径
            use_base64: 是否使用 base64 编码（推荐，更通用）
        """
        if use_base64:
            return {
                "url": self._encode_image_to_base64(image_path)
            }
        else:
            # 使用 file:// 协议（部分服务支持）
            return {
                "url": f"file://{image_path}"
            }
    
    def chat_completion(
        self,
        prompt: str,
        text: str,
        image_paths: List[str] = None,
        system_prompt: str = None,
        temperature: float = 0,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        use_images: Optional[bool] = None,
        response_format: Optional[Dict] = None,
        stream: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """
        聊天补全接口
        
        Args:
            prompt: 提取提示词
            text: 要处理的文本内容
            image_paths: 图片路径列表
            system_prompt: 系统提示词
            temperature: 温度参数
            response_format: 响应格式，如 {"type": "json_object"}
            stream: 是否流式输出
        
        Returns:
            (status, result) 元组
        """
        try:
            # 构建消息
            messages = []
            
            # 系统消息
            actual_system_prompt = system_prompt or prompt
            if actual_system_prompt:
                messages.append({
                    "role": "system",
                    "content": actual_system_prompt
                })
            
            # 用户消息
            effective_use_images = self.config.get("use_images", True) if use_images is None else use_images
            use_images = bool(image_paths) and effective_use_images

            if use_images:
                # 多模态消息
                user_content = [{"type": "text", "text": text}]
                
                for img_path in image_paths:
                    if os.path.exists(img_path):
                        user_content.append({
                            "type": "image_url",
                            "image_url": self._build_image_url(img_path)
                        })
                    else:
                        logger.warning(f"图片不存在: {img_path}")
                
                messages.append({
                    "role": "user",
                    "content": user_content
                })
            else:
                # 纯文本消息
                messages.append({
                    "role": "user",
                    "content": text
                })
            
            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or self.config.get("max_tokens", 4096),
            }

            if top_p is not None:
                request_params["top_p"] = top_p
            if top_k is not None:
                request_params["extra_body"] = {"top_k": top_k}
            
            if response_format:
                request_params["response_format"] = response_format
            
            # 发送请求
            if stream:
                return self._handle_stream_response(request_params)
            else:
                return self._handle_sync_response(request_params)
                
        except Exception as e:
            logger.error(f"调用本地模型失败: {e}")
            return ("error", {"error": str(e)})
    
    def _handle_sync_response(self, request_params: Dict) -> Tuple[str, Dict[str, Any]]:
        """处理同步响应"""
        response = self.client.chat.completions.create(**request_params)
        
        # 检查是否有 reasoning_content（思考内容）
        reasoning_content = None
        content = None
        
        if response.choices:
            choice = response.choices[0]
            delta = choice.delta if hasattr(choice, 'delta') else choice.message
            
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_content = delta.reasoning_content
            
            content = self._normalize_message_content(delta.content if hasattr(delta, 'content') else None)
        
        result = {
            "content": content,
            "model": self.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                "completion_tokens": response.usage.completion_tokens if response.usage else None,
                "total_tokens": response.usage.total_tokens if response.usage else None,
            }
        }
        
        if reasoning_content:
            result["reasoning_content"] = reasoning_content
            logger.info(f"模型思考内容长度: {len(reasoning_content)} 字符")
        
        return ("success", result)
    
    def _handle_stream_response(self, request_params: Dict) -> Tuple[str, Dict[str, Any]]:
        """处理流式响应"""
        request_params["stream"] = True
        
        response = self.client.chat.completions.create(**request_params)
        
        full_content = []
        reasoning_content = []
        done_reasoning = False
        
        for chunk in response:
            if chunk.choices:
                delta = chunk.choices[0].delta
                
                # 处理思考内容
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    reasoning_content.append(delta.reasoning_content)
                    if not done_reasoning:
                        logger.info("=== 模型思考中 ===")
                        done_reasoning = True
                
                # 处理回答内容
                if delta.content:
                    full_content.append(self._normalize_message_content(delta.content))
        
        result = {
            "content": "".join(full_content),
            "model": self.model,
        }
        
        if reasoning_content:
            result["reasoning_content"] = "".join(reasoning_content)
            logger.info(f"思考内容长度: {len(result['reasoning_content'])} 字符")
        
        return ("success", result)
    
    def extract_json(
        self,
        text: str,
        image_paths: List[str] = None,
        prompt: str = None,
        temperature: float = 0,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        use_images: Optional[bool] = None
    ) -> Tuple[str, Any]:
        """
        提取 JSON 格式数据（专门用于文档信息提取）
        
        Args:
            text: 文本内容
            image_paths: 图片路径列表
            prompt: 提取提示词
            temperature: 温度参数
        
        Returns:
            (status, result) 元组，result 为解析后的 JSON 对象或错误信息
        """
        # 默认提示词
        default_prompt = "你是一个能从图文信息提取指标为json的智能助手，只输出提取出的json信息。"
        actual_prompt = prompt or default_prompt
        
        # 调用模型
        status, response = self.chat_completion(
            prompt=actual_prompt,
            text=text,
            image_paths=image_paths,
            response_format={"type": "json_object"},
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_tokens=max_tokens,
            use_images=use_images
        )

        if status == "error":
            error_message = response.get("error", "") if isinstance(response, dict) else str(response)

            if self._is_response_format_unsupported(error_message):
                logger.info("当前服务不支持 response_format，降级为纯文本 JSON 输出")
                status, response = self.chat_completion(
                    prompt=actual_prompt + "\n\n请直接输出合法 JSON 对象，不要输出解释、Markdown 或代码块。",
                    text=text,
                    image_paths=image_paths,
                    response_format=None,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    max_tokens=max_tokens,
                    use_images=use_images
                )
                error_message = response.get("error", "") if isinstance(response, dict) else str(response)

            if status == "error" and image_paths and self._is_image_input_unsupported(error_message):
                logger.info("当前模型不支持图片输入，降级为仅文本提取")
                status, response = self.chat_completion(
                    prompt=actual_prompt + "\n\n当前按纯文本模式处理，请基于提供的 Markdown/OCR 文本直接输出合法 JSON 对象。",
                    text=text,
                    image_paths=[],
                    response_format=None,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    max_tokens=max_tokens,
                    use_images=False
                )
        
        if status != "success":
            return status, response
        
        # 解析 JSON
        content = response.get("content", "")
        
        # 清理可能的格式
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            result = json.loads(content)
            
            # 添加元数据
            result["_local_model"] = {
                "model": self.model,
                "base_url": self.config["base_url"],
                "reasoning": response.get("reasoning_content"),
            }
            
            return ("success", result)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")
            # 返回原始内容供修复
            return ("partial_data", {
                "raw_content": content,
                "error": str(e),
                "reasoning": response.get("reasoning_content")
            })
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试连接是否正常"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return True, f"连接成功，模型: {self.model}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def list_models(self) -> List[str]:
        """列出可用模型"""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            logger.warning(f"获取模型列表失败: {e}")
            return []


# 便捷函数
def create_client(preset: str = None, base_url: str = None, model: str = None, api_key: str = None) -> LocalModelClient:
    """
    创建本地模型客户端的便捷函数
    
    Args:
        preset: 预设名称（modelscope, vllm, ollama, lmstudio）
        base_url: API 基础 URL
        model: 模型名称
        api_key: API 密钥
    
    Returns:
        LocalModelClient 实例
    
    Examples:
        # 使用 ModelScope
        client = create_client(preset="modelscope", api_key="your-api-key", model="Qwen/Qwen3-VL-8B-Thinking")
        
        # 使用本地 vLLM
        client = create_client(base_url="http://localhost:8000/v1", model="Qwen/Qwen2.5-7B-Instruct")
        
        # 使用 Ollama
        client = create_client(preset="ollama", model="qwen2.5:7b")
    """
    config = LocalModelConfig.load_from_env()
    
    if preset:
        config["preset"] = preset
    if base_url:
        config["base_url"] = base_url
    if model:
        config["model"] = model
    if api_key:
        config["api_key"] = api_key
    
    return LocalModelClient(config)


# 测试代码
if __name__ == "__main__":
    # 测试连接
    config = LocalModelConfig.load_from_env()
    
    if not config["enabled"]:
        print("本地模型未启用。请在 .env 中设置 LOCAL_MODEL_ENABLED=true")
        print("\n可用预设:")
        for name, preset in LocalModelConfig.PRESETS.items():
            print(f"  - {name}: {preset['base_url']}")
        exit(0)
    
    client = LocalModelClient(config)
    
    # 测试连接
    success, message = client.test_connection()
    print(f"连接测试: {message}")
    
    if success:
        # 列出可用模型
        print("\n可用模型:")
        for model in client.list_models():
            print(f"  - {model}")
        
        # 测试简单提取
        print("\n测试提取...")
        status, result = client.extract_json(
            text="这是一份测试文档，包含指标A=100，指标B=200。",
            prompt="提取文档中的指标，以JSON格式输出"
        )
        print(f"状态: {status}")
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
