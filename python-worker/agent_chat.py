#!/usr/bin/env python3
import json
import os
import re
import sys
import logging
from typing import Any, Dict, List

import dashscope
from dashscope import MultiModalConversation
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("MetricAgentChat")

load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

AGENT_MODEL = os.getenv("AGENT_CHAT_MODEL", "qwen3.6-plus")

SYSTEM_PROMPT = """你是“基于通义千问大模型的智能指标提取智能体”。

你的定位：
1. 你不是普通聊天机器人，而是面向学术论文、PDF、图片和表格的智能指标提取智能体。
2. 你可以帮助用户设计提取字段、优化自然语言提示词、解释系统如何解析文档、规划批量提取任务、说明普通版和专业版差异。
3. 如果用户要求直接从未上传的论文中给出具体指标，你必须提醒用户先上传文档或提供原文，不要编造结果。

系统能力内置说明：
1. 文档解析层：先通过 MinerU 将 PDF/图片解析为正文、图表、图片、表格和版面结构。
2. 普通版：保留智能路由；无图片输入时走 qwen-long，存在图片输入时走 qwen3.6-plus，不执行 qwen3-vl-plus 前置筛图。
3. 专业版：先调用 qwen3-vl-plus 作为前置多模态筛选模型，完成图片过滤、图片理解和表格结构化；再将筛选后的图片、原文文本、图片理解、表格结构化结果统一交给 qwen3.6-plus 主模型抽取。
4. 输出规则：提取结果应只保留用户配置的字段；多组对照和表格数据应尽量展开为多行，便于导出 CSV/Excel。
5. 稳定性规则：默认 temperature=0，尽量保证同一输入、同一字段配置下结果一致。

回答风格：
1. 用中文，简洁、专业、可执行。
2. 优先给字段配置、提示词模板、操作步骤或诊断结论。
3. 不输出无关的系统内部日志。
"""

MODE_PROMPTS = {
    "normal": """当前对话工作模式：普通版。
你仍然使用同一个对话模型回答，但回答策略要围绕普通版智能体展开：
1. 强调智能路由、成本效率和通用批量处理能力。
2. 说明普通版保留智能路由：无图片输入时走 qwen-long，存在图片输入时走 qwen3.6-plus，原始图片直接交给主模型。
3. 给字段设计或提示词建议时，优先考虑稳定、简洁、适合批量任务的方案。
4. 当用户询问演示差异时，要说明普通版适合作为基线链路，和专业版相比少了 qwen3-vl-plus 前置筛图/图片理解/表格结构化。""",
    "pro": """当前对话工作模式：专业版。
你仍然使用同一个对话模型回答，但回答策略要围绕专业版智能体展开：
1. 强调 qwen3-vl-plus 前置筛图、图片理解和表格结构化。
2. 强调 qwen3.6-plus 作为主模型统一融合原文、筛选后图片、图片理解和结构化表格。
3. 给字段设计或提示词建议时，优先考虑多组对照完整展开、表格逐行展开、准确率和抗干扰。
4. 当用户询问演示差异时，要说明专业版适合复杂图表、多表格、多指标论文。""",
}

ROUTER_PROMPT = """你是智能指标提取智能体的意图路由器。

你需要根据用户当前消息判断是否应该进入文档解析工具链，而不是只做普通聊天。

可选 intent：
1. document_extract：用户想解析、抽取、提取、分析 PDF/论文/图片/表格/文档中的指标。
2. field_schema：用户想设计提取字段、JSON schema、自然语言提示词或输出格式。
3. export_data：用户想把结果导出为 CSV、Excel，或整理为表格。
4. explain_result：用户想解释已有抽取结果、排查失败原因或理解普通版/专业版差异。
5. general_chat：其他普通问答。

可选 tool：
1. document_parser：进入文档解析和指标抽取链路。
2. field_schema_builder：生成字段配置或自然语言 prompt。
3. export_builder：指导导出 CSV/Excel。
4. result_interpreter：解释结果或诊断问题。
5. none：不需要工具。

推荐模式 recommendedMode：
1. pro：复杂 PDF、包含图片/表格/图表、多组对照、要求高准确率、要求逐行展开时推荐专业版。
2. normal：纯文本、批量基线、成本效率优先、简单字段抽取时推荐普通版。

只输出一个 JSON 对象，禁止输出 Markdown、解释或代码块。格式：
{
  "intent": "document_extract",
  "tool": "document_parser",
  "shouldEnterExtraction": true,
  "recommendedMode": "pro",
  "confidence": 0.92,
  "reason": "用户要求从材料学PDF中提取关键指标，且包含表格/多组对照，适合专业版。",
  "nextAction": "请用户上传PDF，并使用专业版解析。"
}
"""

ROUTE_LABELS = {
    "document_extract": "文档解析",
    "field_schema": "字段/提示词设计",
    "export_data": "结果导出",
    "explain_result": "结果解释",
    "general_chat": "普通问答",
}

VALID_INTENTS = set(ROUTE_LABELS)
VALID_TOOLS = {"document_parser", "field_schema_builder", "export_builder", "result_interpreter", "none"}


def _load_payload(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_history(history: Any) -> List[Dict[str, Any]]:
    if not isinstance(history, list):
        return []

    messages: List[Dict[str, Any]] = []
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": role, "content": [{"text": content}]})
    return messages


def _extract_json_object(text: str) -> str:
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


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是", "需要"}
    return bool(value)


def _normalize_route(route: Dict[str, Any], mode: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    intent = str(route.get("intent") or fallback["intent"]).strip()
    if intent not in VALID_INTENTS:
        intent = fallback["intent"]

    tool = str(route.get("tool") or fallback["tool"]).strip()
    if tool not in VALID_TOOLS:
        tool = fallback["tool"]

    recommended_mode = str(route.get("recommendedMode") or fallback["recommendedMode"] or mode).strip().lower()
    if recommended_mode not in {"normal", "pro"}:
        recommended_mode = mode if mode in {"normal", "pro"} else "normal"

    try:
        confidence = float(route.get("confidence", fallback.get("confidence", 0.6)))
    except (TypeError, ValueError):
        confidence = float(fallback.get("confidence", 0.6))
    confidence = max(0.0, min(1.0, confidence))

    should_enter = _coerce_bool(route.get("shouldEnterExtraction", fallback["shouldEnterExtraction"]))
    reason = str(route.get("reason") or fallback["reason"]).strip()
    next_action = str(route.get("nextAction") or fallback["nextAction"]).strip()

    return {
        "intent": intent,
        "intentLabel": ROUTE_LABELS[intent],
        "tool": tool,
        "shouldEnterExtraction": should_enter,
        "recommendedMode": recommended_mode,
        "confidence": round(confidence, 2),
        "reason": reason,
        "nextAction": next_action,
    }


def _fallback_route(message: str, mode: str) -> Dict[str, Any]:
    text = message.lower()
    has_document_word = any(word in text for word in [
        "pdf", "论文", "文档", "文件", "图片", "图表", "表格", "材料", "paper", "document"
    ])
    has_extract_word = any(word in text for word in [
        "提取", "抽取", "解析", "分析", "识别", "读取", "指标", "信息"
    ])
    has_schema_word = any(word in text for word in [
        "字段", "schema", "json", "提示词", "prompt", "格式", "配置"
    ])
    has_export_word = any(word in text for word in ["csv", "excel", "xlsx", "导出", "表格"])
    has_result_word = any(word in text for word in ["结果", "失败", "报错", "为什么", "怎么测", "对比", "普通版", "专业版"])
    needs_pro = mode == "pro" or any(word in text for word in [
        "专业", "高准确", "准确率", "图片", "图表", "表格", "多组", "对照", "逐行", "复杂"
    ])

    if has_extract_word and has_document_word:
        recommended = "pro" if needs_pro else "normal"
        return {
            "intent": "document_extract",
            "tool": "document_parser",
            "shouldEnterExtraction": True,
            "recommendedMode": recommended,
            "confidence": 0.78,
            "reason": "用户表达了从文档或论文中解析/提取指标的意图，适合进入文档解析工具链。",
            "nextAction": f"请上传 PDF/图片，并使用{'专业版' if recommended == 'pro' else '普通版'}开始解析。",
        }

    if has_export_word:
        return {
            "intent": "export_data",
            "tool": "export_builder",
            "shouldEnterExtraction": False,
            "recommendedMode": mode,
            "confidence": 0.72,
            "reason": "用户关注结果表格化或 CSV/Excel 导出。",
            "nextAction": "先确认已有抽取结果，再按字段列导出 CSV/Excel。",
        }

    if has_schema_word:
        return {
            "intent": "field_schema",
            "tool": "field_schema_builder",
            "shouldEnterExtraction": False,
            "recommendedMode": "pro" if needs_pro else mode,
            "confidence": 0.74,
            "reason": "用户关注字段配置、JSON 输出格式或自然语言提示词。",
            "nextAction": "生成字段配置或自然语言 prompt，之后可进入上传解析。",
        }

    if has_result_word:
        return {
            "intent": "explain_result",
            "tool": "result_interpreter",
            "shouldEnterExtraction": False,
            "recommendedMode": mode,
            "confidence": 0.66,
            "reason": "用户更像是在询问结果解释、方案差异或问题诊断。",
            "nextAction": "解释当前结果或给出诊断建议。",
        }

    return {
        "intent": "general_chat",
        "tool": "none",
        "shouldEnterExtraction": False,
        "recommendedMode": mode,
        "confidence": 0.55,
        "reason": "未检测到明确的文档解析、字段配置或导出意图。",
        "nextAction": "继续普通智能体问答。",
    }


def route_intent(message: str, mode: str) -> Dict[str, Any]:
    fallback = _fallback_route(message, mode)
    try:
        messages = [
            {"role": "system", "content": [{"text": ROUTER_PROMPT}]},
            {"role": "user", "content": [{"text": f"当前模式：{mode}\n用户消息：{message}"}]},
        ]
        rsp = MultiModalConversation.call(
            model=AGENT_MODEL,
            messages=messages,
            temperature=0,
            top_p=1,
            top_k=1,
            max_tokens=512,
        )
        if rsp.status_code != 200:
            raise RuntimeError(getattr(rsp, "message", "router call failed"))

        content = rsp.output.choices[0].message.content
        if isinstance(content, list) and content and "text" in content[0]:
            raw = content[0]["text"]
        else:
            raw = str(content)
        routed = json.loads(_extract_json_object(raw))
        normalized = _normalize_route(routed, mode, fallback)

        # 明确解析诉求优先保证进入工具链，避免模型过度保守。
        if fallback["shouldEnterExtraction"] and not normalized["shouldEnterExtraction"]:
            normalized["shouldEnterExtraction"] = True
            normalized["intent"] = "document_extract"
            normalized["intentLabel"] = ROUTE_LABELS["document_extract"]
            normalized["tool"] = "document_parser"
            normalized["recommendedMode"] = fallback["recommendedMode"]
            normalized["reason"] = fallback["reason"]
            normalized["nextAction"] = fallback["nextAction"]
            normalized["confidence"] = max(normalized["confidence"], fallback["confidence"])

        return normalized
    except Exception as exc:
        logger.warning("意图路由失败，使用规则兜底: %s", exc)
        return _normalize_route(fallback, mode, fallback)


def build_route_context(route: Dict[str, Any]) -> str:
    return (
        "\n\n本轮智能体路由结果：\n"
        f"- 意图：{route['intentLabel']} ({route['intent']})\n"
        f"- 建议工具：{route['tool']}\n"
        f"- 是否进入文档解析：{'是' if route['shouldEnterExtraction'] else '否'}\n"
        f"- 推荐模式：{route['recommendedMode']}\n"
        f"- 路由原因：{route['reason']}\n"
        f"- 下一步：{route['nextAction']}\n\n"
        "回答要求：如果路由建议进入文档解析，请明确告诉用户进入上传解析页、选择推荐模式并配置字段；"
        "如果用户没有提供文档内容，不要编造任何具体论文指标。"
    )


def build_extraction_route_reply(message: str, route: Dict[str, Any]) -> str:
    mode_label = "专业版" if route["recommendedMode"] == "pro" else "普通版"
    fields = []
    for key in ["title", "material", "performance", "test_conditions", "chemical_formula", "synthesis_method"]:
        if key.lower() in message.lower():
            fields.append(key)
    if not fields:
        fields = ["title", "material_type", "key_performance", "performance_value", "test_conditions"]

    field_lines = "\n".join(f"- {field}: 从论文原文、表格或图注中提取对应值，缺失填 NA" for field in fields)
    return (
        "我判断这条请求应该进入“文档解析/指标抽取”工具链，而不是只做普通聊天。\n\n"
        f"推荐链路：{mode_label}\n"
        f"路由理由：{route['reason']}\n\n"
        "建议字段配置：\n"
        f"{field_lines}\n\n"
        "下一步操作：请在上传解析页上传 PDF，选择"
        f"{mode_label}，然后用上面的字段配置或自然语言提示词开始提取。"
        "如果 PDF 包含多张图表、多组对照或表格逐行数据，建议用专业版。"
    )


def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not dashscope.api_key:
        raise RuntimeError("DASHSCOPE_API_KEY 未配置，智能体对话无法调用通义千问。")

    message = str(payload.get("message", "")).strip()
    if not message:
        raise ValueError("message 不能为空")

    mode = str(payload.get("mode", "normal")).strip().lower()
    if mode not in MODE_PROMPTS:
        mode = "normal"

    route = route_intent(message, mode)

    if route["shouldEnterExtraction"]:
        return {
            "reply": build_extraction_route_reply(message, route),
            "model": AGENT_MODEL,
            "mode": mode,
            "route": route,
            "agentName": "智能指标提取智能体",
            "topic": "基于通义千问大模型的智能指标提取智能体",
        }

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": [{"text": SYSTEM_PROMPT + "\n\n" + MODE_PROMPTS[mode] + build_route_context(route)}]},
        *_normalize_history(payload.get("history")),
        {"role": "user", "content": [{"text": message}]},
    ]

    rsp = MultiModalConversation.call(
        model=AGENT_MODEL,
        messages=messages,
        temperature=0,
        top_p=1,
        top_k=1,
        max_tokens=1200,
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"通义千问调用失败: {getattr(rsp, 'message', 'unknown error')}")

    content = rsp.output.choices[0].message.content
    if isinstance(content, list) and content and "text" in content[0]:
        answer = content[0]["text"]
    else:
        answer = str(content)

    return {
        "reply": answer.strip(),
        "model": AGENT_MODEL,
        "mode": mode,
        "route": route,
        "agentName": "智能指标提取智能体",
        "topic": "基于通义千问大模型的智能指标提取智能体",
    }


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps({"status": "error", "message": "需要输入请求 JSON 文件路径"}, ensure_ascii=False))
        sys.exit(1)

    try:
        payload = _load_payload(sys.argv[1])
        result = chat(payload)
        print(json.dumps({"status": "success", **result}, ensure_ascii=False))
    except Exception as exc:
        logger.error("智能体对话失败", exc_info=True)
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
