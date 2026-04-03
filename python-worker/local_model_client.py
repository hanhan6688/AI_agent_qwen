import base64
import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


logger = logging.getLogger("LocalModelClient")


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class LocalModelConfig(dict):
    DEFAULTS = {
        "enabled": True,
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key": "EMPTY",
        "model": "Qwen/Qwen2.5-VL-7B-Instruct",
        "provider": "openai-compatible",
        "vision_enabled": True,
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 20,
        "max_tokens": 2048,
        "repetition_penalty": 1.0,
        "presence_penalty": None,
        "frequency_penalty": None,
        "seed": None,
        "timeout": 600,
    }

    @classmethod
    def load_from_env(
        cls,
        defaults: Optional[Dict[str, Any]] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> "LocalModelConfig":
        env_config = {
            "enabled": _to_bool(os.getenv("LOCAL_MODEL_ENABLED"), True),
            "base_url": os.getenv("LOCAL_MODEL_BASE_URL"),
            "api_key": os.getenv("LOCAL_MODEL_API_KEY"),
            "model": os.getenv("LOCAL_MODEL_NAME"),
            "provider": os.getenv("LOCAL_MODEL_PROVIDER"),
            "vision_enabled": os.getenv("LOCAL_MODEL_VISION_ENABLED"),
            "temperature": os.getenv("LOCAL_MODEL_TEMPERATURE"),
            "top_p": os.getenv("LOCAL_MODEL_TOP_P"),
            "top_k": os.getenv("LOCAL_MODEL_TOP_K"),
            "max_tokens": os.getenv("LOCAL_MODEL_MAX_TOKENS"),
            "repetition_penalty": os.getenv("LOCAL_MODEL_REPETITION_PENALTY"),
            "presence_penalty": os.getenv("LOCAL_MODEL_PRESENCE_PENALTY"),
            "frequency_penalty": os.getenv("LOCAL_MODEL_FREQUENCY_PENALTY"),
            "seed": os.getenv("LOCAL_MODEL_SEED"),
            "timeout": os.getenv("LOCAL_MODEL_TIMEOUT"),
        }

        merged = dict(cls.DEFAULTS)
        if defaults:
            merged.update(defaults)
        merged.update({k: v for k, v in env_config.items() if v not in (None, "")})
        if overrides:
            merged.update({k: v for k, v in overrides.items() if v not in (None, "")})

        merged["enabled"] = _to_bool(merged.get("enabled"), True)
        merged["vision_enabled"] = _to_bool(merged.get("vision_enabled"), True)
        merged["temperature"] = _to_float(merged.get("temperature"), 0.1)
        merged["top_p"] = _to_float(merged.get("top_p"), 0.9)
        merged["top_k"] = _to_int(merged.get("top_k"), 20)
        merged["max_tokens"] = _to_int(merged.get("max_tokens"), 2048)
        merged["repetition_penalty"] = _to_float(merged.get("repetition_penalty"), 1.0)
        merged["presence_penalty"] = _to_float(merged.get("presence_penalty"))
        merged["frequency_penalty"] = _to_float(merged.get("frequency_penalty"))
        merged["seed"] = _to_int(merged.get("seed"))
        merged["timeout"] = _to_int(merged.get("timeout"), 600)

        if not merged.get("base_url"):
            raise RuntimeError("LOCAL_MODEL_BASE_URL 未配置")
        if not merged.get("model"):
            raise RuntimeError("LOCAL_MODEL_NAME 未配置")
        if not merged.get("api_key"):
            merged["api_key"] = "EMPTY"

        return cls(merged)

    def generation_config(self) -> Dict[str, Any]:
        return {
            "temperature": self.get("temperature"),
            "top_p": self.get("top_p"),
            "top_k": self.get("top_k"),
            "max_tokens": self.get("max_tokens"),
            "repetition_penalty": self.get("repetition_penalty"),
            "presence_penalty": self.get("presence_penalty"),
            "frequency_penalty": self.get("frequency_penalty"),
            "seed": self.get("seed"),
            "timeout": self.get("timeout"),
        }


class LocalModelClient:
    def __init__(self, config: LocalModelConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.get("api_key", "EMPTY"),
            base_url=str(config.get("base_url")).rstrip("/"),
            timeout=config.get("timeout", 600)
        )

    def extract_json(self, text: str, image_paths: List[str], prompt: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        messages = self._build_messages(text, image_paths, prompt)
        response = self._create_completion(messages)
        message = response.choices[0].message
        content = self._message_text(message)
        reasoning = self._message_reasoning(message)

        parsed = self._parse_json(content)
        metadata = {
            "_local_model": {
                "model": self.config.get("model"),
                "base_url": self.config.get("base_url"),
                "provider": self.config.get("provider"),
                "generation_config": self.generation_config_used(),
                "reasoning": reasoning
            },
            "generation_config": self.generation_config_used()
        }

        if parsed is not None:
            if isinstance(parsed, dict):
                parsed.update(metadata)
                return "success", parsed
            return "success", {"data": parsed, **metadata}

        return "partial_data", {
            "raw_content": content,
            "reasoning": reasoning,
            **metadata
        }

    def generation_config_used(self) -> Dict[str, Any]:
        return {k: v for k, v in self.config.generation_config().items() if v is not None}

    def _build_messages(self, text: str, image_paths: List[str], prompt: Optional[str]) -> List[Dict[str, Any]]:
        system_prompt = (prompt or "").strip()
        if not system_prompt:
            system_prompt = "你是一个信息抽取助手。只输出一个 JSON 对象，不要输出解释。"
        if "JSON" not in system_prompt.upper():
            system_prompt += "\n\n请只输出一个 JSON 对象，不要输出额外说明。"

        user_content: List[Dict[str, Any]] = [{"type": "text", "text": text}]

        if image_paths and self.config.get("vision_enabled", True):
            for image_path in image_paths:
                data_url = self._image_to_data_url(image_path)
                if data_url:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    })
        elif image_paths:
            user_content.append({
                "type": "text",
                "text": f"附加说明：原文中还包含 {len(image_paths)} 张图片，但当前本地模型按纯文本模式处理。"
            })

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

    def _create_completion(self, messages: List[Dict[str, Any]]):
        request_kwargs: Dict[str, Any] = {
            "model": self.config.get("model"),
            "messages": messages,
            "temperature": self.config.get("temperature"),
            "top_p": self.config.get("top_p"),
            "max_tokens": self.config.get("max_tokens"),
            "presence_penalty": self.config.get("presence_penalty"),
            "frequency_penalty": self.config.get("frequency_penalty"),
            "seed": self.config.get("seed"),
        }
        request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}

        extra_body = {}
        if self.config.get("top_k") is not None:
            extra_body["top_k"] = self.config.get("top_k")
        if self.config.get("repetition_penalty") is not None:
            extra_body["repetition_penalty"] = self.config.get("repetition_penalty")
        if extra_body:
            request_kwargs["extra_body"] = extra_body

        attempts = [
            request_kwargs,
            {k: v for k, v in request_kwargs.items() if k != "extra_body"},
            {k: v for k, v in request_kwargs.items() if k not in {"extra_body", "seed", "presence_penalty", "frequency_penalty"}}
        ]

        last_error = None
        for kwargs in attempts:
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_error = exc
                logger.warning("本地模型请求失败，尝试降级参数: %s", exc)

        raise RuntimeError(f"本地模型调用失败: {last_error}")

    def _image_to_data_url(self, image_path: str) -> Optional[str]:
        try:
            image_file = Path(image_path)
            mime_type = mimetypes.guess_type(image_file.name)[0] or "image/png"
            data = base64.b64encode(image_file.read_bytes()).decode("utf-8")
            return f"data:{mime_type};base64,{data}"
        except Exception as exc:
            logger.warning("读取图片失败，已跳过 %s: %s", image_path, exc)
            return None

    def _message_text(self, message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(parts).strip()
        return str(content)

    def _message_reasoning(self, message: Any) -> Optional[str]:
        for attr in ("reasoning_content", "reasoning", "reasoning_text"):
            value = getattr(message, attr, None)
            if value:
                return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return None

    def _parse_json(self, content: str) -> Optional[Any]:
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            candidate = match.group(0)
            try:
                return json.loads(candidate)
            except Exception:
                pass

        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            candidate = match.group(0)
            try:
                return json.loads(candidate)
            except Exception:
                pass

        return None


def create_client(config: Optional[Dict[str, Any]] = None) -> LocalModelClient:
    return LocalModelClient(LocalModelConfig.load_from_env(overrides=config))
