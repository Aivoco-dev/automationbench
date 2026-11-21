"""Expose only Zapier's simulated API tools to OpenCode over MCP stdio."""

import json
import sys
from urllib.request import Request, urlopen

TOOLS = [
    {
        "name": "api_search",
        "description": "Discover simulated app API endpoints by a textual query.",
        "inputSchema": {
            "type": "object", "required": ["query"],
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}},
        },
    },
    {
        "name": "api_fetch",
        "description": "Call a discovered endpoint against the simulated company. Use the URL from api_search.",
        "inputSchema": {
            "type": "object", "required": ["method", "url"], "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                "url": {"type": "string"}, "params": {"type": "string", "description": "JSON query parameters"},
                "body": {"type": "string", "description": "JSON request body"},
            },
        },
    },
    {
        "name": "base64_encode",
        "description": "Base64-encode a text value when a simulated endpoint requires it.",
        "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
    },
]


def serve(url, token):
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        reply = {"jsonrpc": "2.0", "id": request["id"]}
        method = request["method"]
        if method == "initialize":
            reply["result"] = {
                "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "automationbench", "version": "1"},
            }
        elif method == "ping":
            reply["result"] = {}
        elif method == "tools/list":
            reply["result"] = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                call = Request(url, json.dumps(request["params"]).encode(), {
                    "Content-Type": "application/json", "Authorization": "Bearer " + token,
                })
                with urlopen(call, timeout=90) as response:
                    reply["result"] = json.load(response)
            except (OSError, ValueError):
                reply["result"] = {"isError": True, "content": [{"type": "text", "text": "Simulator call failed"}]}
        else:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    serve(sys.argv[1], sys.argv[2])
