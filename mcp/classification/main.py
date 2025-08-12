# server.py
# MCP server that classifies user queries into 14 VN tech domains
# Requires: fastmcp, openai>=1.40.0
#   pip install fastmcp "openai>=1.40.0"
# Run (STDIO): python server.py
# Optional (HTTP): edit bottom to run(transport="http", host="0.0.0.0", port=9000)

import os
import json
from typing import List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from fastmcp import FastMCP
from openai import OpenAI

# ====== Config ======
load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")  # adjust if needed
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== 14 fixed categories ======
CATEGORIES: List[str] = [
    "Công nghệ số",
    "Hành chính công",
    "Đô thị thông minh",
    "Y tế số",
    "Giáo dục thông minh",
    "Nông nghiệp công nghệ cao",
    "Tài chính số",
    "Du lịch thông minh",
    "An ninh mạng",
    "Công nghệ viễn thám",
    "Cơ khí - tự động hóa",
    "Công nghệ sinh học",
    "Môi trường – năng lượng",
    "Vật liệu mới",
]

# ====== Typed results ======
class LabelScore(TypedDict):
    label: Literal[
        "Công nghệ số",
        "Hành chính công",
        "Đô thị thông minh",
        "Y tế số",
        "Giáo dục thông minh",
        "Nông nghiệp công nghệ cao",
        "Tài chính số",
        "Du lịch thông minh",
        "An ninh mạng",
        "Công nghệ viễn thám",
        "Cơ khí - tự động hóa",
        "Công nghệ sinh học",
        "Môi trường – năng lượng",
        "Vật liệu mới",
    ]
    confidence: float  # 0.0 - 1.0

class ClassifyResult(TypedDict):
    query: str
    top_labels: List[LabelScore]
    suggested_next_actions: Optional[List[str]]

# ====== MCP server ======
mcp = FastMCP(
    name="VN-Tech-Classifier",
    instructions="""
    Phân loại câu hỏi người dùng vào 14 lĩnh vực công nghệ (Việt Nam).
    Dùng tool 'classify_tech' để nhận nhãn + confidence + giải thích ngắn.
    """
)

# ====== Tool ======
@mcp.tool(
    name="classify_tech",
    description="Phân loại câu hỏi vào 14 lĩnh vực công nghệ VN, trả về top-k nhãn với confidence.",
    tags={"public", "classification"},
)
def classify_tech(query: str, top_k: int = 3, language: str = "vi") -> ClassifyResult:
    """
    Parameters
    ----------
    query : Nội dung người dùng (tiếng Việt hoặc ngôn ngữ khác).
    top_k : Số nhãn muốn lấy (1..5).
    language : Ngôn ngữ phần giải thích ('vi'/'en').

    Returns
    -------
    ClassifyResult
    """
    top_k = max(1, min(5, int(top_k)))

    system_prompt = f"""
Bạn là bộ phân loại nội dung theo 14 lĩnh vực công nghệ (Việt Nam).
Chỉ chọn từ danh sách cố định dưới đây, có thể nhiều nhãn nếu hợp lý.
Trả JSON đúng schema yêu cầu.

DANH SÁCH NHÃN HỢP LỆ (14):
{CATEGORIES}

Nguyên tắc:
- Cho điểm "confidence" (0.0-1.0) cho từng nhãn.
- Sắp xếp nhãn theo độ phù hợp giảm dần.
- 'suggested_next_actions' tối đa 3 gợi ý ngắn (tùy chọn).
"""

    # ---- FIXED SCHEMA (strict + required includes every property) ----
    json_schema = {
        "name": "classification_schema",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_labels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "enum": CATEGORIES},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["label", "confidence"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                    "maxItems": 5,
                }
            },
            # strict: True requires every property to be listed here:
            "required": ["query", "top_labels"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    # --- Helpers for Responses API path ---
    def _call_responses_api():
        return client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user",   "content": [{"type": "text", "text": query}]},
            ],
            response_format={"type": "json_schema", "json_schema": json_schema},
            temperature=0,
        )

    def _extract_json_from_responses(resp) -> str:
        # Prefer convenience property if present
        data = getattr(resp, "output_text", None)
        if data:
            return data
        # Walk output blocks (SDK internal structure)
        for item in getattr(resp, "output", []) or []:
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", "") == "output_text" and getattr(c, "text", None):
                    return c.text
        raise RuntimeError("No JSON text found in Responses output")

    # --- Main call with graceful fallback to Chat Completions if needed ---
    try:
        resp = _call_responses_api()
        data = _extract_json_from_responses(resp)
    except TypeError:
        # Environment still on older SDK: use Chat Completions with structured outputs
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_schema", "json_schema": json_schema},
            temperature=0,
        )
        data = resp.choices[0].message.content or "{}"

    # --- Parse + post-process ---
    parsed = json.loads(data)
    parsed["query"] = query
    parsed["top_labels"] = parsed.get("top_labels", [])[:top_k]
    parsed.setdefault("suggested_next_actions", [])  # extra safety
    return parsed  # FastMCP will serialize as JSON

if __name__ == "__main__":
    # Default: STDIO transport (works with MCP-compatible clients)
    mcp.run()
    # To expose HTTP, replace the line above with:
    # mcp.run(transport="http", host="0.0.0.0", port=9000)
