import json

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPClient, MCPAgent

from configs.server import server_config


# SSE helper
def _sse(event: str | None = None, data: dict | str | None = None) -> str:
    """Build an SSE frame."""
    parts = []
    if event:
        parts.append(f"event: {event}")
    if data is not None:
        if not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False)
        parts.append(f"data: {data}")
    return "\n".join(parts) + "\n\n"


def _extract_labels(observation) -> list[str] | None:
    """
    Try to extract labels from any observation payload.
    Supports:
      - {"labels": [...]}  # new unified schema
      - {"top_labels": [{"label": "...", "confidence": ...}, ...]}  # legacy rich schema
    Accepts str (JSON) or dict.
    Returns list[str] or None.
    """
    try:
        obj = observation
        if isinstance(observation, str):
            obj = json.loads(observation)
        if not isinstance(obj, dict):
            return None

        if "labels" in obj and isinstance(obj["labels"], list):
            return [str(x) for x in obj["labels"] if isinstance(x, (str, int, float))]

        if "top_labels" in obj and isinstance(obj["top_labels"], list):
            out = []
            for item in obj["top_labels"]:
                if isinstance(item, dict) and "label" in item:
                    out.append(str(item["label"]))
            return out or None

        return None
    except Exception:
        return None


async def stream_mcp():
    load_dotenv()

    client = MCPClient.from_dict(server_config)
    llm = ChatOpenAI(model="gpt-4o", streaming=True)
    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    yield _sse(event="status", data={"message": "starting"})

    last_labels_only: list[str] | None = None

    try:
        async for chunk in agent.stream("Drone nông nghiệp có thể phun thuốc chính xác đến từng cây không?"):
            if isinstance(chunk, str):
                # Final model message. Prefer labels if we captured any.
                if last_labels_only:
                    yield _sse(event="final", data={"labels": last_labels_only})
                else:
                    yield _sse(event="final", data={"text": chunk})
            else:
                action, observation = chunk

                # Try to extract labels from ANY tool observation (no tool-name checks)
                labels = _extract_labels(observation)
                if labels:
                    last_labels_only = labels

                # Optional: forward step frames for debugging/telemetry
                yield _sse(
                    event="step",
                    data={
                        "tool": getattr(action, "tool", None),
                        "input": getattr(action, "tool_input", None),
                        "output": observation[:2000] if isinstance(observation, str) else observation,
                    },
                )

        # Stream termination sentinel
        yield _sse(data="[DONE]")

    except Exception as e:
        yield _sse(event="error", data={"message": str(e)})
        yield _sse(data="[DONE]")
