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
        # SSE allows multiple data lines; keep it simple:
        parts.append(f"data: {data}")
    return "\n".join(parts) + "\n\n"


async def stream_mcp():
    load_dotenv()

    client = MCPClient.from_dict(server_config)
    llm = ChatOpenAI(model="gpt-4o", streaming=True)
    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    yield _sse(event="status", data={"message": "starting"})

    last_labels_only = None  # <--- capture labels from tool

    try:
        async for chunk in agent.stream("Drone nông nghiệp có thể phun thuốc chính xác đến từng cây không?"):
            if isinstance(chunk, str):
                # Instead of forwarding the LLM prose, prefer labels if we have them
                if last_labels_only is not None:
                    yield _sse(event="final", data={"labels": last_labels_only})
                else:
                    yield _sse(event="final", data={"text": chunk})
            else:
                action, observation = chunk

                # Try to capture labels from classify_tech output
                if action.tool == "classify_tech" and isinstance(observation, str):
                    try:
                        obj = json.loads(observation)
                        top = obj.get("top_labels", [])
                        last_labels_only = [item["label"] for item in top if "label" in item]
                    except Exception:
                        pass  # keep streaming anyway

                # Optional: keep sending step frames for debugging
                yield _sse(
                    event="step",
                    data={
                        "tool": action.tool,
                        "input": action.tool_input,
                        "output": observation[:2000] if isinstance(observation, str) else observation,
                    },
                )

        yield _sse(data="[DONE]")
    except Exception as e:
        yield _sse(event="error", data={"message": str(e)})
        yield _sse(data="[DONE]")
