#!/usr/bin/env python3
"""MCP server exposing Itasca FLAC3D 7.0 as agent tools.

Transport: stdio, newline-delimited JSON-RPC 2.0.

Tools
-----
flac3d_info    installation and runner status
flac3d_run     run a .py / .f3dat script headlessly (gui=true for plots)
flac3d_outputs list files produced by a run

Paths are resolved from environment variables (see flac3d/runner.py) or
from the plugin layout, so the same code works from any checkout:

    FLAC3D_HOME    installation root, e.g. C:\\Program Files\\Itasca\\FLAC3D700
    FLAC3D_RUNNER  absolute path of flac3d/runner.py (default: ../flac3d/runner.py)

The runner path is spawned with the interpreter that runs this server.
"""

import json
import os
import subprocess
import sys

VERSION = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))


def _find_runner():
    """Locate flac3d/runner.py in both supported layouts.

    installed: <pkg>/mcp_flac3d.py + <pkg>/flac3d/runner.py
    repo:      plugin/mcp_flac3d.py + ../flac3d/runner.py
    """
    override = os.environ.get("FLAC3D_RUNNER")
    if override:
        return os.path.abspath(override)
    candidates = [
        os.path.join(HERE, "flac3d", "runner.py"),
        os.path.abspath(os.path.join(HERE, os.pardir, "flac3d", "runner.py")),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return candidates[0]


RUNNER = _find_runner()

TOOLS = [
    {
        "name": "flac3d_info",
        "description": (
            "Report the local FLAC3D 7.0 installation used by this machine: "
            "home directory, executable paths, bundled Python and runner. "
            "Call this first when a run fails with a path or licensing error."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "flac3d_run",
        "description": (
            "Run a FLAC3D 7.0 script headlessly and return a JSON result "
            "(status, duration, log path, error excerpt). The script can be a "
            "Python file that uses the embedded `itasca` module, or a .f3dat "
            "data file. Console mode is fast but cannot draw plots: set "
            "gui=true when the script creates plots or exports images. "
            "Do not call `model new` / `model restore` inside a Python script "
            "(they reset the interpreter namespace); pass them through `pre`."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "Absolute path of the .py/.f3dat script (relative paths resolve against the current working directory).",
                },
                "gui": {
                    "type": "boolean",
                    "description": "Use the GUI build instead of the console build (required for plot export).",
                },
                "timeout_sec": {
                    "type": "number",
                    "description": "Wall-clock limit in seconds. Default 600.",
                },
                "pre": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Commands executed before the script, e.g. [\"model restore 'out/cube'\"].",
                },
            },
            "required": ["script"],
            "additionalProperties": False,
        },
    },
    {
        "name": "flac3d_outputs",
        "description": "List files in a directory produced by a FLAC3D run (name, size, mtime).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to list. Default: current working directory.",
                }
            },
            "additionalProperties": False,
        },
    },
]


def send(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def reply(req_id, result):
    send({"jsonrpc": "2.0", "id": req_id, "result": result})


def reply_error(req_id, code, message):
    send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def text_result(payload, is_error=False):
    if not isinstance(payload, str):
        payload = json.dumps(payload, indent=2, ensure_ascii=False)
    return {"content": [{"type": "text", "text": payload}], "isError": is_error}


def resolve(path):
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.abspath(path)


def tool_info():
    env = {
        "FLAC3D_HOME": os.environ.get("FLAC3D_HOME"),
        "FLAC3D_CONSOLE": os.environ.get("FLAC3D_CONSOLE"),
        "FLAC3D_GUI": os.environ.get("FLAC3D_GUI"),
        "FLAC3D_PYTHON": os.environ.get("FLAC3D_PYTHON"),
    }
    return text_result(
        {
            "runner": RUNNER,
            "runner_present": os.path.isfile(RUNNER),
            "python": sys.executable,
            "environment": env,
            "cwd": os.getcwd(),
            "notes": [
                "The console build ignores stdin; the runner passes `call <script>` and appends `program exit`.",
                "PLOT commands only work in GUI mode (gui=true).",
                "Non-ASCII script paths are mapped through an ASCII junction automatically.",
            ],
        }
    )


def tool_run(args):
    script = args.get("script")
    if not script:
        return text_result({"error": "script is required"}, True)
    script = resolve(script)
    if not os.path.isfile(script):
        return text_result({"error": "script not found: %s" % script}, True)
    if not os.path.isfile(RUNNER):
        return text_result({"error": "runner not found: %s" % RUNNER}, True)

    timeout = float(args.get("timeout_sec") or 600.0)
    cmd = [sys.executable, RUNNER, script, "--timeout", str(timeout)]
    if args.get("gui"):
        cmd.append("--gui")
    for item in args.get("pre") or []:
        cmd.extend(["--pre", item])

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout + 120)
    except subprocess.TimeoutExpired:
        return text_result(
            {"status": "timeout", "detail": "runner exceeded %.0f s" % (timeout + 120)},
            True,
        )

    out = proc.stdout.decode("utf-8", "replace").strip()
    err = proc.stderr.decode("utf-8", "replace").strip()
    try:
        parsed = json.loads(out)
    except Exception:
        parsed = {"status": "error", "stdout": out[-4000:], "stderr": err[-4000:]}
    parsed["returncode"] = proc.returncode
    return text_result(parsed, parsed.get("status") != "ok")


def tool_outputs(args):
    directory = resolve(args.get("directory") or os.getcwd())
    if not os.path.isdir(directory):
        return text_result({"error": "not a directory: %s" % directory}, True)
    items = []
    for name in sorted(os.listdir(directory)):
        full = os.path.join(directory, name)
        stat = os.stat(full)
        items.append(
            {
                "name": name,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "dir": os.path.isdir(full),
            }
        )
    return text_result({"directory": directory, "entries": items})


def dispatch(req):
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}
    if req_id is None:
        return  # notification

    if method == "initialize":
        reply(
            req_id,
            {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "flac3d", "version": VERSION},
            },
        )
    elif method == "ping":
        reply(req_id, {})
    elif method == "tools/list":
        reply(req_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "flac3d_info":
                reply(req_id, tool_info())
            elif name == "flac3d_run":
                reply(req_id, tool_run(arguments))
            elif name == "flac3d_outputs":
                reply(req_id, tool_outputs(arguments))
            else:
                reply_error(req_id, -32602, "unknown tool: %s" % name)
        except Exception as exc:
            reply(req_id, text_result({"error": "%s: %s" % (type(exc).__name__, exc)}, True))
    elif method == "resources/list":
        reply(req_id, {"resources": []})
    elif method == "prompts/list":
        reply(req_id, {"prompts": []})
    else:
        reply_error(req_id, -32601, "method not found: %s" % method)


def main():
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except Exception:
            continue
        try:
            dispatch(request)
        except Exception as exc:
            sys.stderr.write("dispatch error: %s\n" % exc)
            sys.stderr.flush()


if __name__ == "__main__":
    main()
