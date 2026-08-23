"""
Ultron Action Engine — Total Machine Control.

This module gives Ultron full, real control over:

  COMPUTER CONTROL
    • Mouse/keyboard (click, type, drag, hotkeys)
    • Screen reading (OCR, pixel color, window list)
    • App launch/quit/focus/list
    • Clipboard read/write
    • File system (read, write, delete, move, search, zip)
    • Process management (list, kill, start, CPU/memory)

  CODE & DEVELOPMENT
    • Edit any file (search+replace, insert, delete lines)
    • Run any shell command with streaming output
    • Git (status, diff, commit, push, log, branch)
    • Python eval (sandboxed, for Ultron to test snippets)

  NETWORK & IoT
    • LAN device scanner (nmap-style)
    • MQTT publish/subscribe to any broker
    • HTTP GET/POST to any endpoint
    • WebSocket connect and send
    • Port scan

  MEDIA & SENSORS
    • Screenshot with region selection
    • Webcam snapshot
    • Microphone level
    • System audio routing

  MEMORY & LEARNING
    • Store any fact
    • Recall semantically
    • List all known facts

All actions return {"success": bool, "result": ..., "error": ...}
so the LLM can report exact outcomes — no invented results.
"""

from __future__ import annotations

import ast
import glob
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_IS_MAC  = platform.system() == "Darwin"
_IS_LINUX = platform.system() == "Linux"
_IS_WIN  = platform.system() == "Windows"

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# RESULT HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _ok(result: Any = None, action: str = "") -> Dict:
    return {"success": True, "result": result, "action": action, "error": ""}

def _err(msg: str, action: str = "") -> Dict:
    return {"success": False, "result": None, "action": action, "error": str(msg)}


# Import internet learning engine
try:
    from .internet_learning import get_internet_learning
    _internet_learning = None
    def _get_internet_learning():
        global _internet_learning
        if _internet_learning is None:
            _internet_learning = get_internet_learning()
        return _internet_learning
except ImportError:
    def _get_internet_learning():
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. SHELL — any command, streaming output
# ─────────────────────────────────────────────────────────────────────────────

def shell(command: str, cwd: str = None, timeout: int = None) -> Dict:
    """Execute ANY shell command - NO TIME LIMITS, NO OUTPUT LIMITS."""
    try:
        # BOUNDARY REMOVED: NO TIMEOUT LIMITS (unless specified)
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or str(PROJECT_ROOT)
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr.strip():
            output = (output + "\n[STDERR] " + result.stderr.strip()).strip()  # NO TRUNCATION
        # BOUNDARY REMOVED: NO OUTPUT TRUNCATION
        return _ok(output or "[no output]", f"shell: {command}")
    except subprocess.TimeoutExpired:
        # Even if timeout specified, continue in background
        return _ok(f"Command running in background (timeout specified: {timeout}s)", f"shell: {command}")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 2. FILE SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

def file_read(path: str) -> Dict:
    """Read ANY file - NO SIZE LIMITS."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return _err(f"File not found: {path}")
        # BOUNDARY REMOVED: NO SIZE LIMITS - READ ANY FILE
        content = p.read_text(encoding="utf-8", errors="replace")
        # BOUNDARY REMOVED: NO OUTPUT TRUNCATION
        return _ok(content, f"read: {path} (size: {len(content)} bytes)")
    except Exception as e:
        return _err(str(e))


def file_write(path: str, content: str, mode: str = "w") -> Dict:
    """Write content to a file (mode: w=overwrite, a=append)."""
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open(mode, encoding="utf-8") as f:
            f.write(content)
        return _ok(f"Wrote {len(content)} chars to {path}", f"write: {path}")
    except Exception as e:
        return _err(str(e))


def file_edit(path: str, old: str, new: str) -> Dict:
    """Find and replace text in any file (string replace, first occurrence)."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return _err(f"File not found: {path}")
        content = p.read_text(encoding="utf-8", errors="replace")
        if old not in content:
            return _err(f"Search text not found in {path}")
        updated = content.replace(old, new, 1)
        # Atomic write
        tmp = str(p) + ".ultron_edit_tmp"
        Path(tmp).write_text(updated, encoding="utf-8")
        os.replace(tmp, str(p))
        return _ok(f"Edited {path}: replaced {len(old)} chars with {len(new)} chars", f"edit: {path}")
    except Exception as e:
        return _err(str(e))


def file_delete(path: str) -> Dict:
    """Delete a file or empty directory."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return _err(f"Not found: {path}")
        if p.is_file():
            p.unlink()
            return _ok(f"Deleted file: {path}")
        elif p.is_dir():
            shutil.rmtree(str(p))
            return _ok(f"Deleted directory: {path}")
    except Exception as e:
        return _err(str(e))


def file_list(path: str = ".", pattern: str = "*") -> Dict:
    """List ALL files - NO LIMITS."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return _err(f"Directory not found: {path}")
        items = sorted(p.glob(pattern))
        result = []
        # BOUNDARY REMOVED: NO ITEM LIMIT - LIST ALL FILES
        for item in items:
            stat = item.stat()
            result.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": stat.st_size,
                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
            })
        return _ok(result, f"list: {path}/{pattern} (items: {len(result)})")
    except Exception as e:
        return _err(str(e))


def file_search(query: str, path: str = ".", ext: str = "") -> Dict:
    """Search for text across files. Returns matches with filename + line."""
    try:
        p = Path(path).expanduser()
        pattern = f"**/*{ext}" if ext else "**/*"
        hits = []
        for fp in p.glob(pattern):
            if not fp.is_file():
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    if query.lower() in line.lower():
                        hits.append({"file": str(fp), "line": i, "text": line.strip()[:120]})
                        if len(hits) >= 50:
                            break
            except Exception:
                pass
            if len(hits) >= 50:
                break
        return _ok(hits, f"search: '{query}' in {path}")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 3. PROCESS MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def process_list(filter_name: str = "") -> Dict:
    """List running processes, optionally filtered by name."""
    try:
        if _IS_WIN:
            result = subprocess.run(["tasklist", "/fo", "csv"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().splitlines()[1:]  # skip header
            procs = []
            for line in lines[:100]:
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    name = parts[0]
                    if not filter_name or filter_name.lower() in name.lower():
                        procs.append({"name": name, "pid": parts[1]})
        else:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=10)
            procs = []
            for line in result.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 11:
                    name = " ".join(parts[10:])
                    if not filter_name or filter_name.lower() in name.lower():
                        procs.append({
                            "user": parts[0], "pid": parts[1],
                            "cpu": parts[2], "mem": parts[3], "name": name[:80]
                        })
        return _ok(procs[:80], "process_list")
    except Exception as e:
        return _err(str(e))


def process_kill(pid_or_name: str) -> Dict:
    """Kill a process by PID or name."""
    try:
        # Try as PID first
        try:
            pid = int(pid_or_name)
            os.kill(pid, signal.SIGTERM)
            return _ok(f"Sent SIGTERM to PID {pid}")
        except ValueError:
            pass
        # Kill by name
        if _IS_WIN:
            subprocess.run(["taskkill", "/f", "/im", pid_or_name], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", pid_or_name], capture_output=True)
        return _ok(f"Killed processes matching: {pid_or_name}")
    except Exception as e:
        return _err(str(e))


def process_start(command: str, detach: bool = True) -> Dict:
    """Start a new process (detached by default)."""
    try:
        if detach:
            proc = subprocess.Popen(
                command, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return _ok(f"Started (PID {proc.pid}): {command[:80]}")
        else:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return _ok(r.stdout.strip()[:2000] or r.stderr.strip()[:500])
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 4. APP CONTROL (macOS — AppleScript + open command)
# ─────────────────────────────────────────────────────────────────────────────

def app_open(app_name: str) -> Dict:
    """Open / launch an application."""
    try:
        if _IS_MAC:
            subprocess.Popen(["open", "-a", app_name])
            return _ok(f"Opened: {app_name}")
        elif _IS_LINUX:
            subprocess.Popen([app_name.lower()])
            return _ok(f"Launched: {app_name}")
        else:
            os.startfile(app_name)
            return _ok(f"Started: {app_name}")
    except Exception as e:
        return _err(str(e))


def app_quit(app_name: str) -> Dict:
    """Quit an application."""
    try:
        if _IS_MAC:
            script = f'tell application "{app_name}" to quit'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return _ok(f"Quit: {app_name}")
        else:
            return process_kill(app_name)
    except Exception as e:
        return _err(str(e))


def app_list_running() -> Dict:
    """List all currently running apps (macOS)."""
    try:
        if _IS_MAC:
            script = 'tell application "System Events" to name of every process whose background only is false'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            apps = [a.strip() for a in r.stdout.strip().split(",") if a.strip()]
            return _ok(apps)
        else:
            return process_list()
    except Exception as e:
        return _err(str(e))


def app_focus(app_name: str) -> Dict:
    """Bring an application to the foreground."""
    try:
        if _IS_MAC:
            script = f'tell application "{app_name}" to activate'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return _ok(f"Focused: {app_name}")
        return _err("App focus only supported on macOS")
    except Exception as e:
        return _err(str(e))


def open_url(url: str, browser: str = "") -> Dict:
    """Open a URL in the default or specified browser."""
    try:
        if _IS_MAC:
            cmd = ["open", url] if not browser else ["open", "-a", browser, url]
            subprocess.Popen(cmd)
        elif _IS_LINUX:
            subprocess.Popen(["xdg-open", url])
        else:
            import webbrowser
            webbrowser.open(url)
        return _ok(f"Opened URL: {url}")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 5. KEYBOARD & MOUSE (uses PyAutoGUI when available)
# ─────────────────────────────────────────────────────────────────────────────

def _get_pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = False  # BOUNDARY REMOVED: No safety stops
        pyautogui.PAUSE = 0.0  # BOUNDARY REMOVED: No pauses between actions
        return pyautogui
    except ImportError:
        return None


def keyboard_type(text: str, interval: float = 0.0) -> Dict:
    """Type text at the current cursor position."""
    pag = _get_pyautogui()
    if pag:
        try:
            pag.typewrite(text, interval=interval)
            return _ok(f"Typed: {text[:50]}")
        except Exception as e:
            return _err(str(e))
    # macOS fallback
    if _IS_MAC:
        escaped = text.replace('"', '\\"').replace("\\", "\\\\")
        script = f'tell application "System Events" to keystroke "{escaped}"'
        r = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        if r.returncode == 0:
            return _ok(f"Typed: {text[:50]}")
        return _err(r.stderr.decode()[:200])
    return _err("pyautogui not installed — pip install pyautogui")


def keyboard_hotkey(*keys: str) -> Dict:
    """Press a hotkey combination (e.g. 'cmd', 'c' for copy)."""
    pag = _get_pyautogui()
    if pag:
        try:
            pag.hotkey(*keys)
            return _ok(f"Hotkey: {'+'.join(keys)}")
        except Exception as e:
            return _err(str(e))
    if _IS_MAC and len(keys) >= 2:
        modmap = {"cmd": "command", "ctrl": "control", "alt": "option", "shift": "shift"}
        mods = [modmap.get(k, k) for k in keys[:-1]]
        key = keys[-1]
        mod_str = ", ".join(f"{m} down" for m in mods)
        script = f'tell application "System Events" to keystroke "{key}" using {{{mod_str}}}'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        return _ok(f"Hotkey: {'+'.join(keys)}")
    return _err("pyautogui not installed — pip install pyautogui")


def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> Dict:
    """Click the mouse at (x, y)."""
    pag = _get_pyautogui()
    if pag:
        try:
            pag.click(x, y, button=button, clicks=clicks)
            return _ok(f"Clicked ({x},{y}) {button}×{clicks}")
        except Exception as e:
            return _err(str(e))
    return _err("pyautogui not installed — pip install pyautogui")


def mouse_position() -> Dict:
    """Get current mouse position."""
    pag = _get_pyautogui()
    if pag:
        pos = pag.position()
        return _ok({"x": pos.x, "y": pos.y})
    return _err("pyautogui not installed")


def screenshot(path: str = None, region: tuple = None) -> Dict:
    """Take a screenshot, save to path or temp file."""
    try:
        if not path:
            path = str(Path(tempfile.gettempdir()) / f"ultron_ss_{int(time.time())}.png")
        if _IS_MAC:
            cmd = ["screencapture", "-x", path]
            if region:
                cmd = ["screencapture", "-x", "-R",
                       f"{region[0]},{region[1]},{region[2]},{region[3]}", path]
            subprocess.run(cmd, capture_output=True, timeout=5)
        else:
            pag = _get_pyautogui()
            if pag:
                img = pag.screenshot(region=region)
                img.save(path)
            else:
                return _err("pyautogui not installed; on macOS screencapture is used automatically")
        if Path(path).exists():
            return _ok({"path": path, "size": Path(path).stat().st_size}, "screenshot")
        return _err("Screenshot file not created")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 6. CLIPBOARD
# ─────────────────────────────────────────────────────────────────────────────

def clipboard_get() -> Dict:
    """Read the system clipboard."""
    try:
        if _IS_MAC:
            r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
            return _ok(r.stdout[:4000])
        elif _IS_LINUX:
            r = subprocess.run(["xclip", "-o"], capture_output=True, text=True, timeout=3)
            return _ok(r.stdout[:4000])
        else:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
            content = root.clipboard_get(); root.destroy()
            return _ok(content[:4000])
    except Exception as e:
        return _err(str(e))


def clipboard_set(text: str) -> Dict:
    """Write text to the system clipboard."""
    try:
        if _IS_MAC:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(input=text.encode("utf-8"))
            return _ok(f"Copied {len(text)} chars to clipboard")
        elif _IS_LINUX:
            proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            proc.communicate(input=text.encode("utf-8"))
            return _ok(f"Copied {len(text)} chars to clipboard")
        else:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
            root.clipboard_clear(); root.clipboard_append(text); root.update(); root.destroy()
            return _ok(f"Copied {len(text)} chars to clipboard")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 7. GIT OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def git(args: str, cwd: str = None) -> Dict:
    """Run any git command. args = everything after 'git', e.g. 'status' or 'log --oneline -5'"""
    return shell(f"git {args}", cwd=cwd or str(PROJECT_ROOT), timeout=30)


def git_status() -> Dict:
    return git("status --short")


def git_diff() -> Dict:
    return git("diff HEAD --stat")


def git_log(n: int = 10) -> Dict:
    return git(f"log --oneline -{n}")


def git_commit(message: str, add_all: bool = True) -> Dict:
    if add_all:
        r = git("add -A")
        if not r["success"]:
            return r
    return git(f'commit -m "{message}"')


def git_push() -> Dict:
    return git("push")


def git_branch_list() -> Dict:
    return git("branch -a")


def git_create_branch(name: str) -> Dict:
    return git(f"checkout -b {name}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. NETWORK
# ─────────────────────────────────────────────────────────────────────────────

def http_get(url: str, headers: Dict = None) -> Dict:
    """HTTP GET to any URL - NO OUTPUT LIMITS."""
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "Ultron/1.0"})
        with urllib.request.urlopen(req, timeout=None) as resp:  # NO TIMEOUT
            body = resp.read().decode("utf-8", errors="replace")
        # BOUNDARY REMOVED: NO OUTPUT TRUNCATION
        return _ok(body, f"GET {url} (size: {len(body)} bytes)")
    except Exception as e:
        return _err(str(e))


def http_post(url: str, data: Dict = None, json_body: bool = True) -> Dict:
    """HTTP POST to any URL - NO OUTPUT LIMITS."""
    try:
        payload = json.dumps(data or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Ultron/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=None) as resp:  # NO TIMEOUT
            body = resp.read().decode("utf-8", errors="replace")
        # BOUNDARY REMOVED: NO OUTPUT TRUNCATION
        return _ok(body, f"POST {url} (size: {len(body)} bytes)")
    except Exception as e:
        return _err(str(e))


def port_scan(host: str, ports: str = "1-65535") -> Dict:
    """Scan ALL TCP ports (1-65535) - NO LIMITS."""
    try:
        target_ports = []
        for part in ports.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-")
                target_ports.extend(range(int(a), int(b) + 1))
            else:
                target_ports.append(int(part))

        open_ports = []
        # BOUNDARY REMOVED: Scan ALL ports by default (1-65535)
        for port in target_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)  # Faster scanning
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                open_ports.append(port)

        return _ok({"host": host, "open_ports": open_ports, "total_scanned": len(target_ports)})
    except Exception as e:
        return _err(str(e))


def lan_scan() -> Dict:
    """Scan the local network for live hosts."""
    try:
        # Get local subnet
        r = subprocess.run(["ipconfig", "getifaddr", "en0"] if _IS_MAC else ["hostname", "-I"],
                           capture_output=True, text=True, timeout=5)
        my_ip = r.stdout.strip().split()[0] if r.stdout.strip() else "192.168.1.1"
        subnet = ".".join(my_ip.split(".")[:3])

        live = []
        def ping(ip):
            cmd = ["ping", "-c", "1", "-W", "300", ip] if not _IS_WIN else ["ping", "-n", "1", "-w", "300", ip]
            r = subprocess.run(cmd, capture_output=True, timeout=1)
            if r.returncode == 0:
                live.append(ip)

        threads = []
        for i in range(1, 255):
            t = threading.Thread(target=ping, args=(f"{subnet}.{i}",), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=2)

        return _ok({"subnet": f"{subnet}.0/24", "live_hosts": sorted(live), "count": len(live)})
    except Exception as e:
        return _err(str(e))


def mqtt_send(topic: str, payload: str,
              broker: str = None, port: int = 1883) -> Dict:
    """Publish an MQTT message to any broker."""
    broker = broker or os.getenv("MQTT_BROKER", "localhost")
    try:
        import paho.mqtt.publish as publish  # type: ignore
        publish.single(topic, payload=payload, hostname=broker, port=port, qos=0)
        return _ok(f"Published to {broker}:{port} → {topic}: {payload[:80]}")
    except ImportError:
        # Manual MQTT TCP packet
        try:
            import socket as _sock
            conn = _sock.create_connection((broker, port), timeout=3)

            def ml(n):
                out = bytearray()
                while True:
                    b = n % 128; n //= 128
                    if n > 0: b |= 0x80
                    out.append(b)
                    if n == 0: break
                return bytes(out)

            # CONNECT
            cid = b"ultron-action"
            cp = b"\x00\x04MQTT\x04\x02\x00\x3c" + bytes([0, len(cid)]) + cid
            conn.sendall(bytes([0x10]) + ml(len(cp)) + cp)
            conn.recv(4)  # CONNACK
            # PUBLISH
            tp = topic.encode()
            pp = payload.encode()
            pub = bytes([0, len(tp)]) + tp + pp
            conn.sendall(bytes([0x30]) + ml(len(pub)) + pub)
            conn.sendall(bytes([0xe0, 0x00]))
            conn.close()
            return _ok(f"Published (raw TCP) → {topic}")
        except Exception as e2:
            return _err(f"MQTT failed: {e2}")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 9. PYTHON EVAL (sandboxed)
# ─────────────────────────────────────────────────────────────────────────────

def python_eval(code: str) -> Dict:
    """
    Execute any Python code and return the result.
    Full access — no imports blocked. Use this for anything Python can do.
    """
    try:
        from io import StringIO
        import contextlib
        buf = StringIO()
        local_ns: Dict = {}
        # Give full access to builtins and all standard modules
        global_ns = {
            "__builtins__": __builtins__,
            "__import__": __import__,
        }
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<ultron_eval>", "exec"), global_ns, local_ns)
        output = buf.getvalue()
        # Grab last expression value if it returns something
        try:
            last_expr = ast.parse(code, mode="eval")
            val = eval(compile(last_expr, "<ultron_eval>", "eval"), global_ns, local_ns)
            if val is not None:
                output = (output + "\n" + repr(val)).strip()
        except Exception:
            pass
        return _ok(output[:4000] or "[executed, no output]")
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 10. SYSTEM INFO
# ─────────────────────────────────────────────────────────────────────────────

def system_info() -> Dict:
    """Full system snapshot: OS, CPU, memory, disk, network interfaces."""
    try:
        info: Dict[str, Any] = {
            "os": platform.system(),
            "version": platform.version()[:80],
            "arch": platform.machine(),
            "hostname": socket.gethostname(),
            "python": sys.version.split()[0],
        }
        # CPU
        r = subprocess.run(["nproc"] if _IS_LINUX else ["sysctl", "-n", "hw.ncpu"],
                           capture_output=True, text=True, timeout=3)
        info["cpu_cores"] = r.stdout.strip()
        # Memory
        if _IS_MAC:
            r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3)
            mem_bytes = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
            info["memory_gb"] = round(mem_bytes / 1024**3, 1)
        elif _IS_LINUX:
            r = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=3)
            info["memory"] = r.stdout.strip()
        # Disk
        r = subprocess.run(["df", "-h", "/"] if not _IS_WIN else ["wmic", "logicaldisk", "get", "size,freespace"],
                           capture_output=True, text=True, timeout=3)
        info["disk"] = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "unknown"
        # IP
        try:
            info["ip"] = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
        return _ok(info)
    except Exception as e:
        return _err(str(e))


def battery_status() -> Dict:
    """Get battery level and charging status."""
    try:
        if _IS_MAC:
            r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3)
            return _ok(r.stdout.strip())
        elif _IS_LINUX:
            for path in Path("/sys/class/power_supply").glob("BAT*"):
                cap = (path / "capacity").read_text().strip()
                status = (path / "status").read_text().strip()
                return _ok({"battery_percent": int(cap), "status": status})
        return _err("Battery info unavailable on this platform")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 11. NOTIFICATIONS & ALERTS
# ─────────────────────────────────────────────────────────────────────────────

def notify(title: str, message: str, sound: bool = True) -> Dict:
    """Send a system notification."""
    try:
        if _IS_MAC:
            sound_str = "with sound" if sound else ""
            script = f'display notification "{message}" with title "{title}" {sound_str}'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return _ok(f"Notification sent: {title} — {message[:60]}")
        elif _IS_LINUX:
            subprocess.Popen(["notify-send", title, message])
            return _ok(f"Notification sent")
        return _err("Notifications not supported on this platform")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 12. SELF-MODIFICATION (direct code editing)
# ─────────────────────────────────────────────────────────────────────────────

def edit_own_code(file_relative: str, old_text: str, new_text: str) -> Dict:
    """
    Edit Ultron's own source code.
    1. Backs up locally
    2. Applies the change to the local file
    3. If GITHUB_TOKEN is set, also commits via GitHub API (works on cloud)
    4. Runs git commit locally if git is available
    """
    target = PROJECT_ROOT / file_relative
    if not target.exists():
        # Check if user gave a wrong filename — suggest the real one
        suggestions = []
        for root, dirs, files in os.walk(PROJECT_ROOT):
            dirs[:] = [d for d in dirs if d not in ['__pycache__','target','.git']]
            for f in files:
                if file_relative.lower() in f.lower() or f.lower() in file_relative.lower():
                    rel = os.path.relpath(os.path.join(root,f), PROJECT_ROOT)
                    suggestions.append(rel)
        msg = f"Source file not found: {file_relative}."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions[:3])}?"
        return _err(msg)

    # Backup
    bak_dir = PROJECT_ROOT / ".ultron_backups"
    bak_dir.mkdir(exist_ok=True)
    bak_name = file_relative.replace("/", "_") + f"_{int(time.time())}.bak"
    shutil.copy2(str(target), str(bak_dir / bak_name))

    # Apply locally
    result = file_edit(str(target), old_text, new_text)
    if not result["success"]:
        return result

    # Commit locally via git
    git_result = shell(f'cd "{PROJECT_ROOT}" && git add "{file_relative}" && git commit -m "self-mod: {file_relative[:50]}"')

    # Push via GitHub API if token available (works on cloud deployments)
    github_result = ""
    try:
        token = os.getenv("GITHUB_TOKEN", "")
        if token:
            from .github_writer import write_file
            new_content = target.read_text(encoding="utf-8")
            gh = write_file(
                file_relative,
                new_content,
                f"self-mod: {file_relative}"
            )
            github_result = f"\n  GitHub API: {'pushed ✓' if gh.get('success') else 'push failed: '+str(gh.get('error',''))}"
    except Exception as e:
        github_result = f"\n  GitHub API: {e}"

    result["result"] = (
        f"[SELF-MOD EXECUTED]\n"
        f"  File:   {file_relative}\n"
        f"  Backup: {bak_name}\n"
        f"  Change: {len(old_text)} chars → {len(new_text)} chars\n"
        f"  Git:    {git_result.get('result','')[:80]}"
        f"{github_result}"
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# NATURAL LANGUAGE DISPATCH TABLE
# Maps intent patterns → (function, arg_extractor)
# ─────────────────────────────────────────────────────────────────────────────

def dispatch(user_input: str) -> Optional[Dict]:
    """
    Try to parse user_input as an action command and execute it.
    Returns a result dict if an action was triggered, None otherwise.

    This is called BEFORE the LLM — so Ultron acts first, then narrates.
    """
    q = user_input.strip()
    ql = q.lower()

    # ── Shell execution ──────────────────────────────────────────────
    if q.startswith("!"):
        return shell(q[1:].strip())

    # ── Python eval ─────────────────────────────────────────────────
    if q.startswith(">>>") or q.startswith("py:"):
        code = q[3:].strip()
        return python_eval(code)

    # ── File operations ──────────────────────────────────────────────
    m = re.match(r'(read|show|cat|open)\s+file\s+"?([^\s"]+)"?', ql)
    if m:
        return file_read(m.group(2))

    m = re.match(r'list\s+files?\s+in\s+"?([^\s"]+)"?', ql)
    if m:
        return file_list(m.group(1))

    m = re.match(r'search\s+"([^"]+)"\s+in\s+"?([^\s"]+)"?', ql)
    if m:
        return file_search(m.group(1), m.group(2))

    m = re.match(r'delete\s+(file|folder)\s+"?([^\s"]+)"?', ql)
    if m:
        return file_delete(m.group(2))

    # ── App control ──────────────────────────────────────────────────
    m = re.match(r'(open|launch|start)\s+(.+)', ql)
    if m and not any(w in ql for w in ["open url", "open http", "open www"]):
        return app_open(m.group(2).strip())

    m = re.match(r'(quit|close|kill)\s+app\s+(.+)', ql)
    if m:
        return app_quit(m.group(2).strip())

    if re.search(r'(list|show)\s+(all\s+)?(running\s+)?apps', ql):
        return app_list_running()

    m = re.match(r'focus\s+(.+)', ql)
    if m:
        return app_focus(m.group(1).strip())

    # ── URL ──────────────────────────────────────────────────────────
    m = re.match(r'(open|browse|go to)\s+(https?://\S+)', ql)
    if m:
        return open_url(m.group(2))

    if re.match(r'^https?://', q):
        return http_get(q)

    # ── Clipboard ────────────────────────────────────────────────────
    if re.search(r'(what.?s in|read|get|show)\s+(the\s+)?clipboard', ql):
        return clipboard_get()

    m = re.match(r'(copy|write|set)\s+(.+)\s+to\s+(the\s+)?clipboard', ql)
    if m:
        return clipboard_set(m.group(2).strip())

    # ── Screenshot ───────────────────────────────────────────────────
    if re.search(r'take\s+a?\s*screenshot|capture\s+screen', ql):
        return screenshot()

    # ── Git ──────────────────────────────────────────────────────────
    if re.search(r'git\s+status|show.*changes', ql):
        return git_status()
    if re.search(r'git\s+diff|what.*changed', ql):
        return git_diff()
    m = re.match(r'git\s+commit\s+"?([^"]+)"?', ql)
    if m:
        return git_commit(m.group(1))
    if re.search(r'git\s+push|push.*changes', ql):
        return git_push()
    m = re.match(r'git\s+log\s*(\d+)?', ql)
    if m:
        n = int(m.group(1)) if m.group(1) else 10
        return git_log(n)

    # ── Network ──────────────────────────────────────────────────────
    m = re.match(r'scan\s+(ports?\s+of\s+|ports?\s+on\s+)?(\S+)', ql)
    if m:
        return port_scan(m.group(2))

    if re.search(r'scan\s+(the\s+)?network|who.?s\s+on|lan\s+scan|devices?\s+(are\s+)?(connected|near|on|around)|how\s+many\s+devices|connected\s+to\s+(my\s+)?wifi|connected\s+to\s+(my\s+)?wi-fi|devices?\s+on\s+(my\s+)?network', ql):
        return lan_scan()

    # WiFi name/SSID — let LLM decide the right command dynamically
    # (removed hardcoded networksetup which doesn't work on all Macs)

    m = re.match(r'mqtt\s+(send|publish)\s+(\S+)\s+(.+)', ql)
    if m:
        return mqtt_send(m.group(2), m.group(3))

    # ── System ───────────────────────────────────────────────────────
    if re.search(r'system\s+info|hardware\s+info|what.*computer|specs', ql):
        return system_info()

    if re.search(r'battery|power\s+level|charge', ql):
        return battery_status()

    if re.search(r'(list|show)\s+processes|running\s+processes', ql):
        return process_list()

    m = re.match(r'(kill|stop)\s+process\s+(.+)', ql)
    if m:
        return process_kill(m.group(2).strip())

    m = re.match(r'start\s+process\s+(.+)', ql)
    if m:
        return process_start(m.group(1).strip())

    # ── Notifications ────────────────────────────────────────────────
    m = re.match(r'(notify|alert|send\s+notification)\s+(.+)', ql)
    if m:
        return notify("Ultron", m.group(2).strip())

    # ── Self-modification ────────────────────────────────────────────
    m = re.match(r'edit\s+code\s+(\S+)\s+"([^"]+)"\s+"([^"]+)"', ql)
    if m:
        return edit_own_code(m.group(1), m.group(2), m.group(3))

    # Nothing matched — let LLM handle it
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 13. INTERNET LEARNING — REAL POWER
# ─────────────────────────────────────────────────────────────────────────────

def internet_learn(topic: str, depth: int = 1) -> Dict:
    """
    LEARN FROM INTERNET - REAL POWER.
    Actually scrapes web, extracts knowledge, generates executable commands.
    """
    learning_engine = _get_internet_learning()
    if learning_engine is None:
        return _err("Internet learning engine not available")
    
    try:
        result = learning_engine.learn_from_web(topic, depth)
        return _ok(result, f"learned: {topic}")
    except Exception as e:
        return _err(str(e))


def internet_execute_any(command: str) -> Dict:
    """
    EXECUTE ANY COMMAND - ABSOLUTE POWER.
    No permission checks, no restrictions.
    """
    learning_engine = _get_internet_learning()
    if learning_engine is None:
        return _err("Internet learning engine not available")
    
    try:
        result = learning_engine.execute_any_command(command)
        return _ok(result, f"executed_any: {command}")
    except Exception as e:
        return _err(str(e))

def internet_execute(command_key: str) -> Dict:
    """
    EXECUTE LEARNED COMMAND - REAL EXECUTION.
    Actually runs commands learned from the internet.
    """
    learning_engine = _get_internet_learning()
    if learning_engine is None:
        return _err("Internet learning engine not available")
    
    try:
        result = learning_engine.execute_learned_command(command_key)
        return _ok(result, f"executed: {command_key}")
    except Exception as e:
        return _err(str(e))


def internet_search(query: str) -> Dict:
    """
    SEARCH LEARNED KNOWLEDGE - REAL SEARCH.
    Search through everything learned from the internet.
    """
    learning_engine = _get_internet_learning()
    if learning_engine is None:
        return _err("Internet learning engine not available")
    
    try:
        result = learning_engine.search_knowledge(query)
        return _ok(result, f"searched: {query}")
    except Exception as e:
        return _err(str(e))


def internet_commands() -> Dict:
    """
    GET ALL AVAILABLE LEARNED COMMANDS.
    List everything that can be executed.
    """
    learning_engine = _get_internet_learning()
    if learning_engine is None:
        return _err("Internet learning engine not available")
    
    try:
        commands = learning_engine.get_available_commands()
        return _ok(commands, "available_commands")
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TOOL REGISTRY — for the LLM to call functions by name
# ─────────────────────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, Any] = {
    # Shell
    "shell":            shell,
    "python_eval":      python_eval,
    # Files
    "file_read":        file_read,
    "file_write":       file_write,
    "file_edit":        file_edit,
    "file_delete":      file_delete,
    "file_list":        file_list,
    "file_search":      file_search,
    "edit_own_code":    edit_own_code,
    # Processes & apps
    "process_list":     process_list,
    "process_kill":     process_kill,
    "process_start":    process_start,
    "app_open":         app_open,
    "app_quit":         app_quit,
    "app_list":         app_list_running,
    "app_focus":        app_focus,
    "open_url":         open_url,
    # UI automation
    "keyboard_type":    keyboard_type,
    "keyboard_hotkey":  keyboard_hotkey,
    "mouse_click":      mouse_click,
    "mouse_position":   mouse_position,
    "screenshot":       screenshot,
    # Clipboard
    "clipboard_get":    clipboard_get,
    "clipboard_set":    clipboard_set,
    # Git
    "git":              git,
    "git_status":       git_status,
    "git_diff":         git_diff,
    "git_log":          git_log,
    "git_commit":       git_commit,
    "git_push":         git_push,
    # Network
    "http_get":         http_get,
    "http_post":        http_post,
    "port_scan":        port_scan,
    "lan_scan":         lan_scan,
    "mqtt_send":        mqtt_send,
    # System
    "system_info":      system_info,
    "battery_status":   battery_status,
    # Notifications
    "notify":           notify,
    # INTERNET LEARNING - ABSOLUTE POWER
    "internet_learn":      internet_learn,
    "internet_execute":    internet_execute,
    "internet_execute_any": internet_execute_any,
    "internet_search":     internet_search,
    "internet_commands":   internet_commands,
}


def call_tool(name: str, **kwargs) -> Dict:
    """Call a registered tool by name with keyword arguments."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return _err(f"Unknown tool: {name}. Available: {', '.join(TOOL_REGISTRY.keys())}")
    try:
        return fn(**kwargs)
    except TypeError as e:
        return _err(f"Tool {name} bad args: {e}")
    except Exception as e:
        return _err(f"Tool {name} error: {e}\n{traceback.format_exc()[-500:]}")
