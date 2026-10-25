"""Protocol smoke test for the FLAC3D MCP server (no pytest required).

    python tests/test_mcp_protocol.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, os.pardir, "plugin", "mcp_flac3d.py")

MESSAGES = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "flac3d_info", "arguments": {}}},
]


def main():
    payload = "".join(json.dumps(m) + "\n" for m in MESSAGES)
    proc = subprocess.run([sys.executable, SERVER], input=payload.encode("utf-8"),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    replies = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]
    by_id = {r.get("id"): r for r in replies}

    assert by_id[1]["result"]["capabilities"]["tools"] == {}
    names = [t["name"] for t in by_id[2]["result"]["tools"]]
    assert names == ["flac3d_info", "flac3d_run", "flac3d_outputs"], names
    info = json.loads(by_id[3]["result"]["content"][0]["text"])
    assert "runner" in info
    print("ok:", names)
    print("runner present:", info["runner_present"])


if __name__ == "__main__":
    main()
