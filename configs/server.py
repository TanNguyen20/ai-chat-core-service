server_config = {
    "mcpServers": {
        "superset": {
            # e.g. "C:\\Users\\NhatTan\\.local\\bin\\uv.EXE"
            "command": "C:Users/NhatTan/.local/bin/uv.EXE",
            "args": [
                "run",
                "--with", "fastapi",
                "--with", "httpx",
                "--with", "mcp[cli]",
                "--with", "python-dotenv",
                "--with", "uvicorn",
                "mcp", "run",
                "F:/ai-core-service/mcp-server/superset-mcp/main.py",
            ],
        },
        "VN-Tech-Classifier": {
            "command": "uv",
            "args": [
                "run",
                "--with",
                "fastmcp",
                "fastmcp",
                "run",
                "..\\mcp\\classification\\main.py"
            ]
        }
    }
}
