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
    description="Phân loại câu hỏi vào 14 lĩnh vực công nghệ VN.",
    tags={"public", "classification"},
)
def classify_tech(
    query: str,
    top_k: int = 3,
    language: str = "vi",
    labels_only: bool = True,  # <-- default: labels-only
):
    top_k = max(1, min(5, int(top_k)))

    system_prompt = f"""
Bạn là bộ phân loại nội dung theo 14 lĩnh vực công nghệ (Việt Nam).
Chỉ chọn nhãn từ danh sách: {CATEGORIES}
Nếu 'labels_only' là true: chỉ trả JSON {{ "labels": [<nhãn> ...] }}.
Nếu false: trả JSON đầy đủ theo schema mở rộng.
Ngôn ngữ giải thích = '{language}'.
"""

    # ---- Two schemas: tiny labels-only (default) or full ----
    if labels_only:
        json_schema = {
            "name": "labels_only_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "labels": {
                        "type": "array",
                        "items": {"type": "string", "enum": CATEGORIES},
                        "minItems": 1,
                        "maxItems": 5
                    }
                },
                "required": ["labels"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    else:
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
                    },
                    "rationale": {"type": "string"},
                    "suggested_next_actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                        "default": []
                    },
                },
                "required": ["query", "top_labels", "rationale", "suggested_next_actions"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    # --- Responses API call (with fallback as you already had) ---
    def _call_responses_api():
        return client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {
                    "role": "user",
                    "content": [{"type": "text", "text": f"labels_only={labels_only}\n\n{query}"}],
                },
            ],
            response_format={"type": "json_schema", "json_schema": json_schema},
            temperature=0,
        )

    def _extract_json_from_responses(resp) -> str:
        data = getattr(resp, "output_text", None)
        if data:
            return data
        for item in getattr(resp, "output", []) or []:
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", "") == "output_text" and getattr(c, "text", None):
                    return c.text
        raise RuntimeError("No JSON text found in Responses output")

    try:
        resp = _call_responses_api()
        data = _extract_json_from_responses(resp)
    except TypeError:
        # Fallback for older SDKs
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"labels_only={labels_only}\n\n{query}"},
            ],
            response_format={"type": "json_schema", "json_schema": json_schema},
            temperature=0,
        )
        data = resp.choices[0].message.content or "{}"

    import json as _json
    parsed = _json.loads(data)

    if labels_only:
        # Ensure at most top_k labels
        labels = parsed.get("labels", [])
        parsed = {"labels": labels[:top_k]}
    else:
        parsed["query"] = query
        parsed["top_labels"] = parsed.get("top_labels", [])[:top_k]
        parsed.setdefault("suggested_next_actions", [])

    return parsed

if __name__ == "__main__":
    # Default: STDIO transport (works with MCP-compatible clients)
    mcp.run()
    # To expose HTTP, replace the line above with:
    # mcp.run(transport="http", host="0.0.0.0", port=9000)
