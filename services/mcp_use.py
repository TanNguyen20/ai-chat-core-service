import json

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPClient, MCPAgent

from configs.server import server_config


# ========= SSE helper =========
def _sse(event: str | None = None, data: dict | str | list | None = None) -> str:
    """Build an SSE frame (UTF-8, no ASCII escaping)."""
    parts = []
    if event:
        parts.append(f"event: {event}")
    if data is not None:
        if not isinstance(data, str):
            try:
                data = json.dumps(data, ensure_ascii=False, default=_json_fallback)
            except Exception:
                # As a last resort, stringify
                data = str(data)
        parts.append(f"data: {data}")
    return "\n".join(parts) + "\n\n"


def _json_fallback(o):
    """Fallback serializer for non-JSON-serializable objects."""
    try:
        return dict(o)
    except Exception:
        return repr(o)


# ========= Main streamer =========
async def stream_mcp(question: str):
    """
    Streams MCP agent steps. Final event returns the *original* last observation:
      {"observation": <raw observation from tool>}
    """
    load_dotenv()

    client = MCPClient.from_dict(server_config)
    llm = ChatOpenAI(model="gpt-4o", streaming=True)
    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    yield _sse(event="status", data={"message": "starting"})

    last_observation = None  # store the most recent raw observation we see

    try:
        async for chunk in agent.stream(question):
            if isinstance(chunk, str):
                # Final LLM message. Prefer returning the raw observation if we have any.
                if last_observation is not None:
                    yield _sse(event="final", data={"observation": last_observation})
                else:
                    yield _sse(event="final", data={"text": chunk})
            else:
                action, observation = chunk
                last_observation = observation  # keep the raw, unmodified observation

                # Forward step frames for debugging/telemetry
                yield _sse(
                    event="step",
                    data={
                        "tool": getattr(action, "tool", None),
                        "input": getattr(action, "tool_input", None),
                        "output": observation,  # raw observation (dict/list/str), serialized via _sse
                    },
                )

        # Stream termination sentinel
        yield _sse(data="[DONE]")

    except Exception as e:
        yield _sse(event="error", data={"message": str(e)})
        yield _sse(data="[DONE]")
