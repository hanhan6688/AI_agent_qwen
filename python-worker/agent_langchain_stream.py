#!/usr/bin/env python3
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from dashscope import MultiModalConversation
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("MetricAgentLangChain")

load_dotenv()

AGENT_MODEL = os.getenv("AGENT_CHAT_MODEL", "qwen3.6-plus")
MAX_CONTEXT_CHARS = int(os.getenv("AGENT_CHAT_MAX_CONTEXT_CHARS", "28000"))

ROUTE_LABELS = {
    "document_extract": "文档解析",
    "field_schema": "字段/提示词设计",
    "export_data": "结果导出",
    "explain_result": "结果解释",
    "general_chat": "普通问答",
}

ROUTER_PROMPT = """你是“基于通义千问大模型的智能指标提取智能体”的 LangChain Router。

请判断用户当前请求应该进入哪个工具或回答链路。

intent 可选：
- document_extract：解析/抽取/分析 PDF、论文、图片、表格、指标。
- field_schema：生成字段配置、JSON schema、自然语言提示词。
- export_data：导出 CSV、Excel、表格化结果。
- explain_result：解释已有抽取结果、诊断失败、说明普通版/专业版差异。
- general_chat：普通问答。

tool 可选：
- document_parser
- field_schema_builder
- export_builder
- result_interpreter
- none

recommendedMode 可选：
- pro：复杂 PDF、图表/表格、多组对照、逐行展开、高准确率。
- normal：纯文本、简单提取、批量基线、效率优先。

只输出 JSON 对象，不要 Markdown：
{{
  "intent": "document_extract",
  "tool": "document_parser",
  "shouldEnterExtraction": true,
  "recommendedMode": "pro",
  "confidence": 0.92,
  "reason": "原因",
  "nextAction": "下一步"
}}
"""

BASE_SYSTEM_PROMPT = """你是“基于通义千问大模型的智能指标提取智能体”。

回答要求：
1. 使用中文，直接、专业、可执行。
2. 支持 Markdown 输出；如果用户明确要求 JSON，则只输出合法 JSON。
3. 不要编造文档中没有的信息；缺失信息填 NA 或说明未找到。
4. 如果提供了 PDF 内容，优先基于 PDF 上下文回答。
5. 对多组对照、表格多行、多个样品条件，尽量逐组展开，不要只总结最优结果。
6. 字段抽取结果应只保留用户要求的字段，方便导出 CSV/Excel。
"""

MODE_PROMPTS = {
    "normal": "当前模式：普通版。保留智能路由：无图片输入走 qwen-long，有图片输入走 qwen3.6-plus；PDF 原文和原始图片直接进入主模型，不执行 qwen3-vl-plus 前置筛图。",
    "pro": "当前模式：专业版。强调 qwen3-vl-plus 前置筛图/图表理解，qwen3.6-plus 主模型融合抽取。",
}


def emit(event: str, data: Dict[str, Any]) -> None:
    print(json.dumps({"event": event, "data": data}, ensure_ascii=False), flush=True)


def load_payload(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def normalize_mode(mode: Any) -> str:
    return "pro" if str(mode or "").strip().lower() == "pro" else "normal"


def get_api_key() -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY 未配置，无法调用通义千问。")
    return api_key


def to_dashscope_messages(messages: List[Any]) -> List[Dict[str, Any]]:
    converted: List[Dict[str, Any]] = []
    for message in messages:
        role = "user"
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, HumanMessage):
            role = "user"
        converted.append({"role": role, "content": [{"text": str(message.content)}]})
    return converted


def extract_response_text(response: Any) -> str:
    content = response.output.choices[0].message.content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return str(content or "")


def call_qwen_once(messages: List[Any], max_tokens: int = 1200) -> str:
    response = MultiModalConversation.call(
        model=AGENT_MODEL,
        messages=to_dashscope_messages(messages),
        api_key=get_api_key(),
        temperature=0,
        top_p=1,
        top_k=1,
        max_tokens=max_tokens,
        enable_thinking=False,
    )
    if response.status_code != 200:
        raise RuntimeError(getattr(response, "message", "通义千问调用失败"))
    return extract_response_text(response)


def extract_json_object(text: str) -> str:
    if not text:
        return "{}"
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def fallback_route(message: str, mode: str, has_files: bool) -> Dict[str, Any]:
    text = message.lower()
    has_document_word = has_files or any(w in text for w in ["pdf", "论文", "文档", "文件", "图片", "图表", "表格", "paper"])
    has_extract_word = any(w in text for w in ["提取", "抽取", "解析", "分析", "识别", "读取", "指标", "信息"])
    has_schema_word = any(w in text for w in ["字段", "schema", "json", "提示词", "prompt", "格式"])
    has_export_word = any(w in text for w in ["csv", "excel", "xlsx", "导出"])
    needs_pro = mode == "pro" or any(w in text for w in ["专业", "图表", "表格", "图片", "多组", "对照", "逐行", "复杂"])

    if has_document_word and (has_extract_word or has_files):
        recommended = "pro" if needs_pro else "normal"
        return {
            "intent": "document_extract",
            "intentLabel": ROUTE_LABELS["document_extract"],
            "tool": "document_parser",
            "shouldEnterExtraction": True,
            "recommendedMode": recommended,
            "confidence": 0.82,
            "reason": "检测到用户提供或提到 PDF/文档，并表达了解析或指标提取意图。",
            "nextAction": "基于已上传 PDF 内容直接回答；如需完整批量提取，可进入上传解析页创建任务。",
        }

    if has_export_word:
        intent, tool = "export_data", "export_builder"
    elif has_schema_word:
        intent, tool = "field_schema", "field_schema_builder"
    elif any(w in text for w in ["结果", "失败", "报错", "普通版", "专业版", "为什么"]):
        intent, tool = "explain_result", "result_interpreter"
    else:
        intent, tool = "general_chat", "none"

    return {
        "intent": intent,
        "intentLabel": ROUTE_LABELS[intent],
        "tool": tool,
        "shouldEnterExtraction": False,
        "recommendedMode": mode,
        "confidence": 0.62,
        "reason": "未检测到必须触发文档解析任务的请求，进入对话回答链路。",
        "nextAction": "继续对话回答。",
    }


def normalize_route(route: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    intent = str(route.get("intent") or fallback["intent"]).strip()
    if intent not in ROUTE_LABELS:
        intent = fallback["intent"]

    tool = str(route.get("tool") or fallback["tool"]).strip()
    if tool not in {"document_parser", "field_schema_builder", "export_builder", "result_interpreter", "none"}:
        tool = fallback["tool"]

    mode = str(route.get("recommendedMode") or fallback["recommendedMode"]).strip().lower()
    if mode not in {"normal", "pro"}:
        mode = fallback["recommendedMode"]

    try:
        confidence = float(route.get("confidence", fallback["confidence"]))
    except (TypeError, ValueError):
        confidence = fallback["confidence"]

    return {
        "intent": intent,
        "intentLabel": ROUTE_LABELS[intent],
        "tool": tool,
        "shouldEnterExtraction": bool(route.get("shouldEnterExtraction", fallback["shouldEnterExtraction"])),
        "recommendedMode": mode,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "reason": str(route.get("reason") or fallback["reason"]).strip(),
        "nextAction": str(route.get("nextAction") or fallback["nextAction"]).strip(),
    }


def route_intent(message: str, mode: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
    fallback = fallback_route(message, mode, bool(files))
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", ROUTER_PROMPT),
            ("human", "当前模式：{mode}\n是否上传文件：{has_files}\n用户消息：{message}"),
        ])
        raw = call_qwen_once(
            prompt.format_messages(mode=mode, has_files=bool(files), message=message),
            max_tokens=512,
        )
        route = normalize_route(json.loads(extract_json_object(raw)), fallback)
        if fallback["shouldEnterExtraction"] and not route["shouldEnterExtraction"]:
            return fallback
        return route
    except Exception as exc:
        logger.warning("LangChain Router 失败，使用规则兜底: %s", exc)
        return fallback


def normalize_history(history: Any) -> List[Any]:
    if not isinstance(history, list):
        return []

    messages: List[Any] = []
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def load_pdf_context(files: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    remaining = MAX_CONTEXT_CHARS

    for file_info in files:
        path = Path(str(file_info.get("path", "")))
        name = str(file_info.get("name") or path.name)
        if not path.exists():
            blocks.append(f"## {name}\n[文件不存在，无法读取]\n")
            continue
        if path.suffix.lower() != ".pdf":
            blocks.append(f"## {name}\n[暂只支持 PDF 附件解析]\n")
            continue

        try:
            docs = PyPDFLoader(str(path)).load()
            page_texts = []
            for doc in docs:
                page = doc.metadata.get("page", "?")
                text = re.sub(r"\s+", " ", doc.page_content or "").strip()
                if not text:
                    continue
                page_texts.append(f"[page {page}] {text}")
            content = "\n".join(page_texts)
            if len(content) > remaining:
                content = content[:remaining] + "\n[PDF 内容过长，已截断用于对话上下文]"
            blocks.append(f"## {name}\n{content}\n")
            remaining -= len(content)
            if remaining <= 0:
                break
        except Exception as exc:
            logger.exception("读取 PDF 失败: %s", path)
            blocks.append(f"## {name}\n[读取失败：{exc}]\n")

    return "\n".join(blocks).strip()


def build_messages(payload: Dict[str, Any], route: Dict[str, Any], pdf_context: str) -> List[Any]:
    message = str(payload.get("message") or "").strip()
    mode = normalize_mode(payload.get("mode"))
    system_parts = [
        BASE_SYSTEM_PROMPT,
        MODE_PROMPTS[mode],
        "LangChain 路由结果：\n"
        f"- intent: {route['intentLabel']} ({route['intent']})\n"
        f"- tool: {route['tool']}\n"
        f"- recommendedMode: {route['recommendedMode']}\n"
        f"- reason: {route['reason']}",
    ]

    if pdf_context:
        system_parts.append("以下是用户上传 PDF 的文本上下文，请优先基于该内容回答：\n\n" + pdf_context)
    else:
        system_parts.append("当前没有可读取的 PDF 上下文；如果用户要求从论文中提取具体指标，请提醒上传 PDF，不要编造。")

    messages: List[Any] = [SystemMessage(content="\n\n".join(system_parts))]
    messages.extend(normalize_history(payload.get("history")))
    messages.append(HumanMessage(content=message or "请分析我上传的 PDF，并提取关键指标。"))
    return messages


def stream_answer(payload: Dict[str, Any]) -> None:
    message = str(payload.get("message") or "").strip()
    mode = normalize_mode(payload.get("mode"))
    files = payload.get("files") if isinstance(payload.get("files"), list) else []

    route = route_intent(message, mode, files)
    emit("meta", {
        "model": AGENT_MODEL,
        "mode": mode,
        "route": route,
        "attachments": [{"name": f.get("name"), "type": f.get("type"), "size": f.get("size")} for f in files],
    })

    pdf_context = load_pdf_context(files)
    messages = build_messages(payload, route, pdf_context)

    full_text = []
    stream = MultiModalConversation.call(
        model=AGENT_MODEL,
        messages=to_dashscope_messages(messages),
        api_key=get_api_key(),
        stream=True,
        incremental_output=True,
        temperature=0,
        top_p=1,
        top_k=1,
        max_tokens=2200,
        enable_thinking=False,
    )

    for chunk in stream:
        if chunk.status_code != 200:
            raise RuntimeError(getattr(chunk, "message", "通义千问流式调用失败"))
        text = extract_response_text(chunk)
        if not text:
            continue
        full_text.append(text)
        emit("delta", {"content": text})

    emit("done", {
        "reply": "".join(full_text).strip(),
        "model": AGENT_MODEL,
        "mode": mode,
        "route": route,
    })


def main() -> None:
    if len(sys.argv) != 2:
        emit("error", {"message": "需要输入请求 JSON 文件路径"})
        sys.exit(1)

    try:
        stream_answer(load_payload(sys.argv[1]))
    except Exception as exc:
        logger.exception("LangChain 流式智能体失败")
        emit("error", {"message": str(exc)})
        sys.exit(1)


if __name__ == "__main__":
    main()
