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

async def stream_superset_dashboards():
    """
    Async generator that yields SSE frames while the MCP agent runs.
    - Emits `event: step` for each (action, observation)
    - Emits `event: final` once with the final answer
    - Ends with a [DONE] sentinel
    """
    load_dotenv()

    client = MCPClient.from_dict(server_config)
    llm = ChatOpenAI(model="gpt-4o", streaming=True)
    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    # optional: notify client we've started
    yield _sse(event="status", data={"message": "starting"})

    try:
        async for chunk in agent.stream("List all Superset dashboard for me"):
            if isinstance(chunk, str):
                # Final answer from the agent
                yield _sse(event="final", data={"text": chunk})
            else:
                action, observation = chunk
                yield _sse(
                    event="step",
                    data={
                        "tool": action.tool,
                        "input": action.tool_input,
                        # Truncate long outputs to keep the stream snappy
                        "output": observation[:2000] if isinstance(observation, str) else observation,
                    },
                )
        # Matching many streaming APIs, send a termination signal
        yield _sse(data="[DONE]")
    except Exception as e:
        # Send an error frame so the client can handle it gracefully
        yield _sse(event="error", data={"message": str(e)})
        # Also send a DONE to close out nicely
        yield _sse(data="[DONE]")
    # If MCPClient exposes explicit close methods, you could call them here.
