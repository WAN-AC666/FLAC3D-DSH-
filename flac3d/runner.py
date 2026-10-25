"""Headless runner for Itasca FLAC3D 7.0.

Runs a FLAC3D script (Python `.py` using the embedded `itasca` module, or a
`.f3dat` data file) without touching the GUI, captures the console output,
detects errors and enforces a timeout.

Why the wrapper
---------------
`flac3d700_console.exe` ignores redirected stdin: it only executes commands
given on its command line, e.g. `flac3d700_console.exe call script.py`, and
then waits at an interactive prompt.  The runner therefore writes a tiny
data file next to the script::

    program call '<ascii path of script>'
    program exit

and launches the console with that wrapper.

Non-ASCII paths
---------------
FLAC3D converts command-line arguments with the ANSI code page, so a path
such as ``G:\\FLAC接入DSH\\...`` reaches the program as ``????``.  When the
script directory contains non-ASCII characters the runner creates an ASCII
junction under the temp directory and hands FLAC3D that path instead.

Environment
-----------
FLAC3D_HOME     installation root (default: auto-detect, e.g.
                ``C:\\Program Files\\Itasca\\FLAC3D700``)
FLAC3D_CONSOLE  console executable (default ``<home>/exe64/flac3d700_console.exe``)
FLAC3D_GUI      GUI executable (default ``<home>/exe64/flac3d700_gui.exe``)
FLAC3D_PYTHON   Python shipped with FLAC3D (default ``<home>/exe64/python36/python.exe``)
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ANSI = "gbk"


def _registry_home():
    if os.name != "nt":
        return None
    try:
        import winreg

        for hive, key in (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Itasca\Flac3d700"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Itasca\Flac3d700"),
        ):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    value, _ = winreg.QueryValueEx(handle, "installdir64")
                    if value and os.path.isdir(value):
                        return value.rstrip("\\/")
            except OSError:
                continue
    except Exception:
        pass
    return None


def flac3d_home():
    home = os.environ.get("FLAC3D_HOME") or _registry_home()
    if not home:
        for guess in (
            r"C:\Program Files\Itasca\FLAC3D700",
            r"C:\Program Files\Itasca\FLAC3D 7.0",
            r"C:\Program Files (x86)\Itasca\FLAC3D700",
        ):
            if os.path.isdir(guess):
                home = guess
                break
    if not home:
        raise SystemExit(
            "FLAC3D not found: set FLAC3D_HOME to the installation directory"
        )
    return home


def exe_path(gui=False):
    if gui:
        return os.environ.get("FLAC3D_GUI") or os.path.join(
            flac3d_home(), "exe64", "flac3d700_gui.exe"
        )
    return os.environ.get("FLAC3D_CONSOLE") or os.path.join(
        flac3d_home(), "exe64", "flac3d700_console.exe"
    )


def flac3d_python():
    return os.environ.get("FLAC3D_PYTHON") or os.path.join(
        flac3d_home(), "exe64", "python36", "python.exe"
    )


def is_ascii(text):
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def ascii_dir(path):
    """Return an ASCII-only path that resolves to *path*."""
    path = os.path.abspath(path)
    if is_ascii(path):
        return path
    digest = hashlib.md5(path.lower().encode("utf-8")).hexdigest()[:10]
    link = os.path.join(tempfile.gettempdir(), "flac3d-ascii", digest)
    if os.path.isdir(link):
        return link
    os.makedirs(os.path.dirname(link), exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", link, path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.symlink(path, link)
        except OSError:
            return path
    return link if os.path.isdir(link) else path


def decode(raw):
    for encoding in (ANSI, "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode(ANSI, "replace")


def is_error(line):
    """FLAC3D marks real failures with '***'; 'Warning' lines are not fatal."""
    if "Warning" in line:
        return False
    stripped = line.lstrip()
    return stripped.startswith("***") or stripped.startswith("While processing line")


def run(script, timeout=600.0, gui=False, pre=None, verbose=False):
    script = os.path.abspath(script)
    if not os.path.isfile(script):
        raise SystemExit("script not found: %s" % script)

    script_dir = os.path.dirname(script)
    run_dir = ascii_dir(script_dir)
    script_arg = os.path.join(run_dir, os.path.basename(script)).replace("\\", "/")

    wrapper = os.path.join(run_dir, "_flac_run.f3dat")
    with open(wrapper, "w", encoding="ascii") as handle:
        for command in pre or []:
            handle.write("%s\n" % command)
        handle.write("program call '%s'\n" % script_arg)
        handle.write("program exit\n")

    log_path = os.path.join(script_dir, "_flac_run.log")
    started = time.time()
    executable = exe_path(gui)

    if not os.path.isfile(executable):
        raise SystemExit("executable not found: %s" % executable)

    process = subprocess.Popen(
        [executable, "call", os.path.join(run_dir, os.path.basename(wrapper))],
        cwd=run_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    lines = []
    status = "ok"
    error_at = None

    if gui:
        # The GUI detaches from the console; process exit is the only signal.
        try:
            process.wait(timeout=timeout)
            status = "ok" if process.returncode == 0 else "nonzero-exit"
        except subprocess.TimeoutExpired:
            status = "timeout"
            process.kill()
            process.wait()
        lines = decode(process.stdout.read()).splitlines()
    else:
        deadline = started + timeout
        try:
            for raw in iter(process.stdout.readline, b""):
                line = decode(raw).rstrip("\r\n")
                lines.append(line)
                if verbose:
                    print(line)
                if is_error(line):
                    status = "error"
                    error_at = len(lines)
                    process.kill()
                    for extra in decode(process.stdout.read()).splitlines():
                        lines.append(extra)
                    break
                if time.time() > deadline:
                    status = "timeout"
                    break
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()

    with open(log_path, "w", encoding="utf-8", errors="replace") as handle:
        handle.write("\n".join(lines))

    context = ""
    if error_at:
        context = "\n".join(lines[max(0, error_at - 12):error_at + 12])

    return {
        "status": status,
        "script": script,
        "mode": "gui" if gui else "console",
        "log": log_path,
        "seconds": round(time.time() - started, 1),
        "returncode": process.returncode,
        "error": context,
        "lines": len(lines),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a FLAC3D 7.0 script headlessly.")
    parser.add_argument("script")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--gui", action="store_true", help="use the GUI build (for plots)")
    parser.add_argument("--pre", action="append", default=[],
                        help="data-file command executed before the script")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    result = run(args.script, timeout=args.timeout, gui=args.gui,
                 pre=args.pre, verbose=args.verbose)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
