from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, HTMLResponse

from services.mcp_use import stream_mcp

router = APIRouter(tags=["root"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "text/event-stream",
}


@router.get("/root-stream", response_class=StreamingResponse)
async def root(question: str = Query(..., description="User question to send to stream_mcp")):
    return StreamingResponse(
        stream_mcp(question),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/ui", response_class=HTMLResponse)
async def ui():
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>SSE Demo</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --bg:#f7f7f7; --muted:#6b7280; --ink:#111827; --border:#e5e7eb; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: var(--ink); }
    form { display: flex; gap: .5rem; margin-bottom: 1rem; }
    input[type="text"] { flex: 1; padding: .6rem .8rem; border: 1px solid #ccc; border-radius: .5rem; }
    button { padding: .6rem .9rem; border: 0; border-radius: .5rem; cursor: pointer; }
    button.primary { background: #111827; color: white; }
    .status { font-size: .95rem; color: var(--muted); margin:.5rem 0 1rem; min-height: 1.2em; }
    .panes { display: grid; gap: 1rem; grid-template-columns: 1fr; }
    @media (min-width: 900px) { .panes { grid-template-columns: 1fr 1fr; } }
    .card { background: white; border: 1px solid var(--border); border-radius: .75rem; overflow: hidden; }
    .card h2 { margin: 0; padding: .75rem 1rem; border-bottom: 1px solid var(--border); font-size: 1rem; background: #fafafa; }
    .card .content { padding: 1rem; }
    .steps { width: 100%; border-collapse: collapse; }
    .steps th, .steps td { border-bottom: 1px solid var(--border); padding: .5rem .5rem; vertical-align: top; }
    .steps th { text-align: left; font-weight: 600; }
    details { border: 1px solid var(--border); border-radius: .5rem; padding: .5rem .75rem; background: #fcfcfc; }
    details + details { margin-top: .5rem; }
    summary { cursor: pointer; font-weight: 600; }
    pre { background: var(--bg); padding: .75rem; border-radius: .5rem; overflow: auto; max-height: 40vh; }
    .badge { display:inline-block; padding:.25rem .5rem; border-radius: .5rem; background:#eef2ff; color:#3730a3; font-size:.8rem; }
    .muted { color: var(--muted); }
  </style>
</head>
<body>
  <h1>Ask a question</h1>
  <div class="status" id="status">Idle.</div>

  <form id="form">
    <input id="question" type="text" placeholder="Type your question…" autocomplete="off" />
    <button class="primary" type="submit">Send</button>
    <button type="button" id="stop">Stop</button>
  </form>

  <div class="panes">
    <div class="card">
      <h2>Status</h2>
      <div class="content">
        <div id="statusLine"><span class="badge">waiting</span> <span class="muted">No activity yet.</span></div>
      </div>
    </div>

    <div class="card">
      <h2>Final</h2>
      <div class="content">
        <pre id="final">(final observation will appear here)</pre>
      </div>
    </div>

    <div class="card" style="grid-column: 1 / -1;">
      <h2>Steps</h2>
      <div class="content">
        <table class="steps" id="stepsTable">
          <thead>
            <tr>
              <th style="width: 12rem;">Tool</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody id="stepsBody">
            <!-- rows appended here -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const form = document.getElementById("form");
    const input = document.getElementById("question");
    const status = document.getElementById("status");
    const statusLine = document.getElementById("statusLine");
    const finalEl = document.getElementById("final");
    const stepsBody = document.getElementById("stepsBody");
    const stopBtn = document.getElementById("stop");

    let es = null;

    function prettyJSON(x) {
      try {
        if (typeof x === "string") {
          // Attempt to parse stringified JSON; if fails, show raw
          const parsed = JSON.parse(x);
          return JSON.stringify(parsed, null, 2);
        }
        return JSON.stringify(x, null, 2);
      } catch {
        return String(x);
      }
    }

    function clearUI() {
      status.textContent = "Connecting…";
      statusLine.innerHTML = '<span class="badge">connecting</span> <span class="muted">Opening SSE…</span>';
      finalEl.textContent = "";
      stepsBody.innerHTML = "";
    }

    function closeStream() {
      if (es) { es.close(); es = null; }
      status.textContent = "Disconnected.";
      statusLine.innerHTML = '<span class="badge">disconnected</span> <span class="muted">Stream closed.</span>';
    }

    function addStepRow(step) {
      const tr = document.createElement("tr");

      const toolCell = document.createElement("td");
      toolCell.textContent = step.tool || "(unknown)";
      tr.appendChild(toolCell);

      const detailsCell = document.createElement("td");
      const details = document.createElement("div");

      const inputBox = document.createElement("details");
      const inputSum = document.createElement("summary");
      inputSum.textContent = "input";
      inputBox.appendChild(inputSum);
      const inputPre = document.createElement("pre");
      inputPre.textContent = prettyJSON(step.input ?? {});
      inputBox.appendChild(inputPre);
      details.appendChild(inputBox);

      const outputBox = document.createElement("details");
      const outputSum = document.createElement("summary");
      outputSum.textContent = "output";
      outputBox.appendChild(outputSum);
      const outputPre = document.createElement("pre");
      outputPre.textContent = prettyJSON(step.output ?? {});
      outputBox.appendChild(outputPre);
      details.appendChild(outputBox);

      detailsCell.appendChild(details);
      tr.appendChild(detailsCell);

      stepsBody.appendChild(tr);
    }

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = (input.value || "").trim();
      if (!q) return;

      // Close any previous stream and clear UI
      closeStream();
      clearUI();

      // IMPORTANT: your SSE endpoint path here.
      // Keeping your existing example path `/root-stream`:
      const url = `/root-stream?question=${encodeURIComponent(q)}`;
      es = new EventSource(url);

      es.onopen = () => {
        status.textContent = "Connected. Streaming…";
        statusLine.innerHTML = '<span class="badge">connected</span> <span class="muted">Awaiting events…</span>';
      };

      // Default handler (e.g., bare "data: [DONE]")
      es.onmessage = (event) => {
        if (event.data === "[DONE]") {
          closeStream();
        }
      };

      // Named event: status
      es.addEventListener("status", (event) => {
        try {
          const payload = JSON.parse(event.data || "{}");
          const msg = payload.message ?? JSON.stringify(payload);
          statusLine.innerHTML = '<span class="badge">status</span> ' + msg;
        } catch (_) {
          statusLine.innerHTML = '<span class="badge">status</span> ' + (event.data || "");
        }
      });

      // Named event: step
      es.addEventListener("step", (event) => {
        try {
          const payload = JSON.parse(event.data || "{}");
          addStepRow({
            tool: payload.tool,
            input: payload.input,
            output: payload.output
          });
          statusLine.innerHTML = '<span class="badge">step</span> Received step for "' + (payload.tool || "unknown") + '"';
        } catch {
          addStepRow({ tool: "(parse error)", input: event.data, output: "" });
        }
      });

      // Named event: final
      es.addEventListener("final", (event) => {
        try {
          const payload = JSON.parse(event.data || "{}");
          const obs = payload.observation ?? payload;
          finalEl.textContent = prettyJSON(obs);
          statusLine.innerHTML = '<span class="badge">final</span> Done.';
        } catch {
          finalEl.textContent = event.data || "";
        }
      });

      es.onerror = () => {
        status.textContent = "Error. Connection closed.";
        statusLine.innerHTML = '<span class="badge">error</span> <span class="muted">See console for details.</span>';
        closeStream();
      };
    });

    stopBtn.addEventListener("click", () => {
      closeStream();
    });

    window.addEventListener("beforeunload", closeStream);
  </script>
</body>
</html>
        """
    )
