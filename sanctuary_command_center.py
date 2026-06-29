# Sanctuary Command Center (SCC) - Unified Edition v2.0
# ==============================================================================
import os
import sys
import json
import subprocess
import socket
import urllib.request
import urllib.parse
import urllib.error
import ctypes
import threading
import queue
import time
import base64
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Redirect stdout/stderr to log file for silent operation
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scc_server.log')
try:
    _log = open(_log_path, 'a', encoding='utf-8', buffering=1)
    sys.stdout = _log
    sys.stderr = _log
except Exception:
    pass

PORT = 9999
LLM_DIR = r"D:\AI\Models\LLM"
KOBOLD_EXE = r"D:\AI\Projects\KoboldCpp\koboldcpp.exe"
FORGE_DIR = r"D:\AI\Projects\stable-diffusion-webui-forge"
LAUNCHERS_DIR = r"D:\AI\Launchers"
OLLAMA_URL = "http://localhost:11434"

EXPLORER_SHORTCUTS = [
    {"name": "ComfyUI Workspace",       "path": r"D:\AI\Projects\ComfyUI"},
    {"name": "Amy Master (Face)",        "path": r"D:\AI\Projects\ComfyUI\input\Amy_Master"},
    {"name": "Alma Master (Body)",       "path": r"D:\AI\Projects\ComfyUI\input\Alma_Master"},
    {"name": "Flux Training Folder",    "path": r"D:\AI\Projects\flux_training"},
    {"name": "ChromaDB Memory Backups", "path": r"E:\_Sanctuary_Backups\Scripts"},
    {"name": "Plex TV Library",         "path": r"E:\Media_Server\TV_Shows"},
    {"name": "Adult Vault",             "path": r"E:\Adult_Vault"},
    {"name": "Personal Vault",          "path": r"E:\Personal_Vault"},
    {"name": "Antigravity Outputs",     "path": r"D:\AI\Antigravity outputs"},
]

APPS = {
    "forge": {
        "name": "SD WebUI Forge",
        "port": 7860,
        "process_names": ["python.exe"],
        "dir": FORGE_DIR,
        "launch_cmd": f'start cmd /k "cd /d {FORGE_DIR} && START_FORGE.bat"'
    },
    "kobold": {
        "name": "KoboldCPP",
        "port": 5001,
        "process_names": ["koboldcpp.exe"],
        "dir": os.path.dirname(KOBOLD_EXE),
        "launch_cmd": ""
    },
    "ollama": {
        "name": "Ollama Server",
        "port": 11434,
        "process_names": ["ollama.exe", "ollama_llama_server.exe"],
        "launch_cmd": "start ollama serve"
    }
}

# --- Terminal Log Stream State ---
# Stores last N lines per named stream
_terminal_logs = {}  # key -> deque of strings
_terminal_lock = threading.Lock()
MAX_LOG_LINES = 200

def _append_log(key, line):
    with _terminal_lock:
        if key not in _terminal_logs:
            import collections
            _terminal_logs[key] = collections.deque(maxlen=MAX_LOG_LINES)
        _terminal_logs[key].append(line)

def _pipe_reader(proc, key, prefix=""):
    """Reads stdout+stderr from a subprocess and stores in terminal log."""
    import collections
    with _terminal_lock:
        if key not in _terminal_logs:
            _terminal_logs[key] = collections.deque(maxlen=MAX_LOG_LINES)
    try:
        for raw in proc.stdout:
            try:
                line = raw.decode('utf-8', errors='replace').rstrip()
            except Exception:
                line = str(raw)
            _append_log(key, f"{prefix}{line}")
    except Exception:
        pass

# --- SYSTEM STATS ---

def get_gpu_stats():
    gpu = {"vram_used": 0, "vram_total": 0, "load": 0, "temp": 0, "processes": []}
    try:
        cmd = "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits"
        out = subprocess.check_output(cmd, shell=True, text=True).strip()
        parts = [p.strip() for p in out.split(',')]
        if len(parts) >= 4:
            gpu["vram_used"] = int(parts[0])
            gpu["vram_total"] = int(parts[1])
            gpu["load"]      = int(parts[2])
            gpu["temp"]      = int(parts[3])
        proc_cmd = "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits"
        proc_out = subprocess.check_output(proc_cmd, shell=True, text=True).strip()
        if proc_out:
            for line in proc_out.split('\n'):
                p = [x.strip() for x in line.split(',')]
                if len(p) >= 3:
                    gpu["processes"].append({"pid": int(p[0]), "name": os.path.basename(p[1]), "vram": int(p[2])})
    except Exception:
        pass
    return gpu

def get_disk_stats():
    import shutil
    drives = []
    for d in ['C', 'D', 'E', 'G']:
        path = f"{d}:\\"
        if os.path.exists(path):
            try:
                total, used, free = shutil.disk_usage(path)
                drives.append({
                    "letter": path,
                    "label": "Workstation" if d == 'D' else ("Archive" if d == 'E' else "Local"),
                    "total_gb": round(total / (1024**3), 1),
                    "used_gb":  round(used  / (1024**3), 1),
                    "free_gb":  round(free  / (1024**3), 1),
                    "pct":      round((used / total) * 100, 1) if total > 0 else 0
                })
            except Exception:
                pass
    return sorted(drives, key=lambda x: x['letter'])

def get_system_stats():
    stats = {"cpu_load": 0, "ram_used_gb": 0, "ram_total_gb": 0, "ram_pct": 0}
    try:
        # Fetch CPU
        cpu_cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty LoadPercentage"]
        cpu_out = subprocess.check_output(cpu_cmd, text=True, timeout=4).strip()
        stats["cpu_load"] = int(cpu_out) if cpu_out.isdigit() else 0

        # Fetch RAM
        ram_cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object -Property TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json"]
        ram_out = subprocess.check_output(ram_cmd, text=True, timeout=4).strip()
        if ram_out:
            ram_data = json.loads(ram_out)
            total_kb = int(ram_data.get("TotalVisibleMemorySize", 0))
            free_kb = int(ram_data.get("FreePhysicalMemory", 0))
            if total_kb > 0:
                used_kb = total_kb - free_kb
                stats["ram_total_gb"] = round(total_kb / (1024**2), 1)
                stats["ram_used_gb"]  = round(used_kb  / (1024**2), 1)
                stats["ram_pct"]      = round((used_kb / total_kb) * 100, 1)
    except Exception:
        pass
    return stats


def get_process_list():
    procs = []
    try:
        ps_cmd = ["powershell", "-NoProfile", "-Command",
                  "Get-Process | Where-Object {$_.CPU -gt 1 -or $_.WorkingSet64 -gt 100MB} | Select-Object Id,ProcessName,CPU,WorkingSet64 | ConvertTo-Json"]
        out = subprocess.check_output(ps_cmd, text=True).strip()
        if out:
            data = json.loads(out)
            if not isinstance(data, list): data = [data]
            for p in data:
                cpu = p.get("CPU"); cpu_val = round(cpu, 1) if cpu is not None else 0
                ram_mb = round(p.get("WorkingSet64", 0) / (1024**2), 1)
                procs.append({"pid": p.get("Id"), "name": p.get("ProcessName"), "cpu": cpu_val, "ram": ram_mb})
    except Exception:
        pass
    return sorted(procs, key=lambda x: x['ram'], reverse=True)[:15]

def check_port_active(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(('127.0.0.1', port)) == 0

def scan_ggufs():
    ggufs = []
    if os.path.exists(LLM_DIR):
        try:
            for f in os.listdir(LLM_DIR):
                if f.lower().endswith('.gguf'):
                    ggufs.append(f)
        except Exception:
            pass
    return sorted(ggufs)

def query_everything_search(query_str):
    results = []
    for port in [8080, 80]:
        try:
            url = f"http://localhost:{port}/?search={urllib.parse.quote(query_str)}&json=1"
            with urllib.request.urlopen(urllib.request.Request(url), timeout=0.8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data.get("results", [])[:40]:
                    results.append({
                        "name": item.get("name"),
                        "path": item.get("path", "") + "\\" + item.get("name", ""),
                        "size": round(int(item.get("size", 0)) / (1024**2), 2) if item.get("size") else 0,
                        "type": "Everything"
                    })
                if results: return results
        except Exception:
            pass
    scan_paths = [r"D:\AI\Projects", r"D:\AI\Antigravity outputs", r"E:\_Sanctuary_Backups"]
    q = query_str.lower()
    for base in scan_paths:
        if not os.path.exists(base): continue
        count = 0
        for root, dirs, files in os.walk(base):
            for file in files:
                if q in file.lower():
                    fp = os.path.join(root, file)
                    try: size = round(os.path.getsize(fp) / (1024**2), 2)
                    except: size = 0
                    results.append({"name": file, "path": fp, "size": size, "type": "Local Index"})
                    count += 1
                    if count > 20: break
            if len(results) >= 40: break
    return results

def get_ollama_models():
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def ollama_generate(model, prompt):
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode()).get("response", "")

# ============================================================
#  HTML FRONT-END
# ============================================================
HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sanctuary Command Center</title>
    <meta name="description" content="Unified AI workstation dashboard - monitor GPU, launch models, generate prompts, curate datasets.">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary:   #0A0C14;
            --bg-secondary: #0F111A;
            --bg-card:      rgba(18, 21, 38, 0.75);
            --bg-input:     rgba(25, 29, 52, 0.65);
            --border:       rgba(255, 255, 255, 0.07);
            --border-glow:  rgba(168, 85, 247, 0.45);
            --text-primary: #F1F2F6;
            --text-secondary:#9FA4BC;
            --text-muted:   #575E75;
            --accent:       #A855F7;
            --accent-cyan:  #22D3EE;
            --accent-pink:  #EC4899;
            --accent-glow:  rgba(168, 85, 247, 0.22);
            --danger:       #F43F5E;
            --success:      #10B981;
            --warning:      #F59E0B;
            --gradient:     linear-gradient(135deg, #A855F7 0%, #EC4899 100%);
            --gradient-cyan:linear-gradient(135deg, #22D3EE 0%, #A855F7 100%);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            background-image:
                radial-gradient(ellipse at 10% 15%, rgba(168,85,247,0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 90% 85%, rgba(34,211,238,0.04) 0%, transparent 50%);
        }

        /* ---- SCROLLBAR ---- */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(168,85,247,0.3); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(168,85,247,0.6); }

        /* ---- HEADER ---- */
        header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 14px 36px;
            border-bottom: 1px solid var(--border);
            background: rgba(10,12,20,0.92);
            backdrop-filter: blur(24px);
            position: sticky; top: 0; z-index: 200;
        }
        .header-logo { display: flex; align-items: center; gap: 14px; }
        .header-logo .badge {
            background: var(--gradient);
            padding: 5px 12px; border-radius: 8px;
            font-size: 11px; font-weight: 800; letter-spacing: 1.5px;
            box-shadow: 0 0 16px var(--accent-glow);
        }
        .header-logo h1 { font-size: 17px; font-weight: 700; letter-spacing: -0.3px; }
        #vramBanner {
            font-size: 12px; font-weight: 600;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 6px 14px; border-radius: 8px;
        }
        .header-time { font-size: 12px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }

        /* ---- TABS NAV ---- */
        .tabs-nav {
            display: flex; gap: 6px; flex-wrap: wrap;
            padding: 12px 36px;
            background: rgba(15,17,26,0.6);
            border-bottom: 1px solid var(--border);
        }
        .tab-btn {
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-secondary);
            padding: 9px 18px; font-size: 13px; font-weight: 600;
            border-radius: 9px;
            display: flex; align-items: center; gap: 7px;
            transition: all 0.2s; cursor: pointer;
            white-space: nowrap;
        }
        .tab-btn:hover {
            color: var(--text-primary);
            background: rgba(255,255,255,0.025);
            border-color: var(--border);
        }
        .tab-btn.active {
            color: var(--text-primary);
            background: var(--bg-card);
            border-color: rgba(168,85,247,0.25);
            box-shadow: 0 0 18px rgba(168,85,247,0.1);
            position: relative;
        }
        .tab-btn.active::after {
            content: '';
            position: absolute; bottom: -1px; left: 12%; width: 76%; height: 2px;
            background: var(--gradient);
            border-radius: 2px;
        }

        /* ---- TAB CONTENT ---- */
        .tab-content { display: none; padding: 28px 36px; animation: fadeIn 0.25s ease-out; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

        /* ---- LAYOUT ---- */
        .panel-grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 22px; }
        .panel-grid-equal { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
        .panel-grid-3 { display: grid; grid-template-columns: repeat(3,1fr); gap: 22px; }

        .panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 22px;
            backdrop-filter: blur(12px);
        }
        .panel-title {
            font-size: 14px; font-weight: 700;
            margin-bottom: 18px;
            display: flex; align-items: center; justify-content: space-between;
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
        }
        .panel-title-label { display: flex; align-items: center; gap: 8px; }

        /* ---- STAT CARDS ---- */
        .grid-stats { display: grid; grid-template-columns: repeat(4,1fr); gap: 18px; margin-bottom: 22px; }
        .card-stat {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 15px; padding: 18px;
            backdrop-filter: blur(12px);
            transition: border-color 0.2s;
        }
        .card-stat:hover { border-color: rgba(168,85,247,0.25); }
        .stat-header {
            font-size: 10px; font-weight: 700; text-transform: uppercase;
            letter-spacing: 1px; color: var(--text-secondary);
            margin-bottom: 8px; display: flex; justify-content: space-between;
        }
        .stat-value { font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 4px; }
        .stat-sub { font-size: 11px; color: var(--text-muted); }
        .progress-bar { width: 100%; height: 4px; background: rgba(255,255,255,0.04); border-radius: 2px; overflow: hidden; margin-top: 8px; }
        .progress-fill { height: 100%; background: var(--gradient); border-radius: 2px; transition: width 0.4s ease-out; }

        /* ---- BUTTONS ---- */
        button {
            padding: 8px 16px; border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--bg-input);
            color: var(--text-primary);
            font-family: inherit; font-size: 13px; font-weight: 600;
            cursor: pointer; transition: all 0.2s;
        }
        button:hover { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }
        button.btn-primary { background: var(--gradient); border: none; }
        button.btn-primary:hover { opacity: 0.92; box-shadow: 0 4px 16px rgba(168,85,247,0.35); }
        button.btn-danger { border-color: var(--danger); color: var(--danger); background: rgba(244,63,94,0.05); }
        button.btn-danger:hover { background: var(--danger); color: #fff; box-shadow: 0 0 12px rgba(244,63,94,0.3); }
        button.btn-cyan { background: var(--gradient-cyan); border: none; }
        button.btn-cyan:hover { opacity: 0.9; box-shadow: 0 4px 16px rgba(34,211,238,0.3); }
        button:disabled { opacity: 0.45; cursor: not-allowed; }

        /* ---- INPUTS ---- */
        select, input[type="number"], input[type="text"], textarea {
            padding: 8px 12px; border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--bg-input); color: var(--text-primary);
            font-family: inherit; font-size: 13px; outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        select:focus, input:focus, textarea:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        textarea { resize: vertical; }
        label { font-size: 11px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.6px; }

        /* ---- APP ROWS ---- */
        .app-row {
            display: flex; align-items: center; justify-content: space-between;
            padding: 13px 16px;
            background: rgba(255,255,255,0.015);
            border: 1px solid var(--border);
            border-radius: 11px; margin-bottom: 9px;
            transition: border-color 0.2s;
        }
        .app-row:hover { border-color: rgba(168,85,247,0.2); }
        .app-indicator { width: 9px; height: 9px; border-radius: 50%; background: var(--text-muted); transition: all 0.3s; }
        .app-indicator.active { background: var(--success); box-shadow: 0 0 10px rgba(16,185,129,0.5); animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100% { box-shadow: 0 0 6px rgba(16,185,129,0.4); } 50% { box-shadow: 0 0 14px rgba(16,185,129,0.7); } }

        /* ---- FILE EXPLORER ---- */
        .explorer-layout { display: grid; grid-template-columns: 240px 1fr; gap: 18px; min-height: 500px; }
        .explorer-sidebar { border-right: 1px solid var(--border); padding-right: 18px; display: flex; flex-direction: column; gap: 8px; overflow-y: auto; }
        .shortcut-item {
            padding: 9px 13px; background: rgba(255,255,255,0.01);
            border: 1px solid var(--border); border-radius: 8px;
            font-size: 12px; cursor: pointer;
            transition: all 0.2s; display: flex; align-items: center; gap: 8px;
        }
        .shortcut-item:hover { border-color: var(--accent); background: rgba(168,85,247,0.06); }
        .explorer-main { display: flex; flex-direction: column; gap: 14px; }
        .explorer-toolbar {
            display: flex; align-items: center; gap: 10px;
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border); border-radius: 9px; padding: 9px 14px;
        }
        .breadcrumbs { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-secondary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .explorer-list { flex: 1; background: rgba(255,255,255,0.01); border: 1px solid var(--border); border-radius: 11px; max-height: 460px; overflow-y: auto; }
        .file-item { display: flex; align-items: center; justify-content: space-between; padding: 9px 14px; border-bottom: 1px solid rgba(255,255,255,0.015); font-size: 12px; transition: background 0.12s; }
        .file-item:hover { background: rgba(255,255,255,0.025); }
        .file-meta { display: flex; align-items: center; gap: 10px; flex: 1; cursor: pointer; }
        .file-icon { font-size: 15px; min-width: 18px; }
        .file-name { font-weight: 500; }
        .file-size { color: var(--text-muted); font-size: 10px; font-family: 'JetBrains Mono', monospace; }

        /* ---- LIGHTBOX ---- */
        .lightbox-overlay {
            position: fixed; inset: 0;
            background: rgba(5,6,12,0.88); backdrop-filter: blur(10px);
            z-index: 500; display: none; align-items: center; justify-content: center;
        }
        .lightbox-card {
            background: var(--bg-secondary); border: 1px solid var(--border);
            border-radius: 18px; max-width: 82vw; max-height: 82vh;
            padding: 22px; display: flex; flex-direction: column; align-items: center; position: relative;
        }
        .lightbox-close { position: absolute; top: 14px; right: 14px; font-size: 20px; cursor: pointer; color: var(--text-muted); }
        .lightbox-close:hover { color: #fff; }

        /* ---- SEARCH ---- */
        .search-bar-container { display: flex; gap: 10px; margin-bottom: 18px; }
        .search-input { flex: 1; padding: 11px; font-size: 13px; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th { text-align: left; padding: 9px; color: var(--text-secondary); border-bottom: 1px solid var(--border); font-size: 11px; letter-spacing: 0.5px; }
        td { padding: 9px; border-bottom: 1px solid rgba(255,255,255,0.015); font-family: 'JetBrains Mono', monospace; font-size: 11px; }
        tr:hover td { background: rgba(255,255,255,0.015); }

        /* ---- DRIVES ---- */
        .drives-grid { display: flex; flex-direction: column; gap: 12px; }
        .drive-row { padding: 11px; border: 1px solid var(--border); border-radius: 9px; background: rgba(255,255,255,0.01); }

        /* ---- LAUNCHERS ---- */
        .launchers-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr)); gap: 14px; }
        .launcher-card {
            display: flex; flex-direction: column; justify-content: space-between;
            background: rgba(168,85,247,0.04);
            border: 1px solid rgba(168,85,247,0.14);
            border-radius: 12px; padding: 16px;
            transition: all 0.2s;
        }
        .launcher-card:hover { border-color: var(--accent); background: rgba(168,85,247,0.09); box-shadow: 0 0 14px var(--accent-glow); }
        .launcher-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; word-break: break-all; }
        .launcher-ext { font-size: 10px; font-family: 'JetBrains Mono', monospace; color: var(--text-muted); text-transform: uppercase; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px; align-self: flex-start; margin-bottom: 12px; }

        /* ---- PROMPT GENERATOR ---- */
        .prompt-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
        .preset-group { display: flex; flex-direction: column; gap: 10px; }
        .preset-row { display: flex; flex-wrap: wrap; gap: 7px; }
        .preset-chip {
            padding: 5px 12px; border-radius: 20px;
            border: 1px solid var(--border); background: var(--bg-input);
            font-size: 11px; font-weight: 600; cursor: pointer;
            transition: all 0.18s; color: var(--text-secondary);
        }
        .preset-chip:hover { border-color: var(--accent); color: var(--text-primary); }
        .preset-chip.selected { background: var(--gradient); border-color: transparent; color: #fff; box-shadow: 0 0 10px var(--accent-glow); }
        .prompt-output {
            background: rgba(0,0,0,0.35); border: 1px solid var(--border);
            border-radius: 11px; padding: 16px;
            font-family: 'JetBrains Mono', monospace; font-size: 11px;
            line-height: 1.7; color: var(--text-secondary);
            min-height: 140px; white-space: pre-wrap;
            overflow-y: auto; max-height: 220px;
        }
        .prompt-label { font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-bottom: 5px; }
        .prompt-label.pos { color: var(--success); }
        .prompt-label.neg { color: var(--danger); }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.2); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; vertical-align: middle; margin-right: 6px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* ---- TERMINALS ---- */
        .terminal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(440px,1fr)); gap: 18px; }
        .terminal-window {
            background: #080A11;
            border: 1px solid rgba(34,211,238,0.15);
            border-radius: 13px; overflow: hidden;
        }
        .terminal-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 10px 16px;
            background: rgba(34,211,238,0.06);
            border-bottom: 1px solid rgba(34,211,238,0.12);
        }
        .terminal-title { font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; color: var(--accent-cyan); }
        .terminal-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 8px rgba(16,185,129,0.5); }
        .terminal-body {
            font-family: 'JetBrains Mono', monospace; font-size: 11px;
            color: #8FFFC8; line-height: 1.6;
            padding: 14px; height: 300px; overflow-y: auto;
            word-break: break-all;
        }
        .terminal-line { opacity: 0; animation: lineIn 0.1s forwards; }
        @keyframes lineIn { to { opacity: 1; } }

        /* ---- SDC (Dataset Curator) ---- */
        .sdc-grid { display: grid; grid-template-columns: 320px 1fr; gap: 20px; min-height: 520px; }
        .sdc-panel { display: flex; flex-direction: column; gap: 14px; }
        .image-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px,1fr)); gap: 10px; }
        .gallery-thumb {
            border-radius: 10px; overflow: hidden; cursor: pointer;
            border: 2px solid var(--border); position: relative;
            transition: all 0.2s;
        }
        .gallery-thumb:hover { border-color: var(--accent); box-shadow: 0 0 12px var(--accent-glow); }
        .gallery-thumb.selected { border-color: var(--accent-cyan); box-shadow: 0 0 16px rgba(34,211,238,0.35); }
        .gallery-thumb img { width: 100%; aspect-ratio: 1; object-fit: cover; display: block; }
        .gallery-thumb .thumb-label { font-size: 9px; padding: 3px 6px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

        /* ---- BADGES / TAGS ---- */
        .badge-tag {
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 10px; font-weight: 600; letter-spacing: 0.5px;
        }
        .badge-running { background: rgba(16,185,129,0.15); color: var(--success); border: 1px solid rgba(16,185,129,0.25); }
        .badge-stopped { background: rgba(87,94,117,0.15); color: var(--text-muted); border: 1px solid rgba(87,94,117,0.25); }

        /* Notification toast */
        #toast {
            position: fixed; bottom: 28px; right: 28px;
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: 11px; padding: 12px 20px;
            font-size: 13px; z-index: 999;
            display: none; backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            animation: slideUp 0.25s ease-out;
        }
        @keyframes slideUp { from { transform: translateY(16px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

        .vram-panic-bar {
            display: flex; justify-content: space-between; align-items: center;
            background: rgba(244,63,94,0.06);
            border: 1px solid rgba(244,63,94,0.2);
            border-radius: 12px; padding: 14px 18px; margin-bottom: 20px;
        }
    </style>
</head>
<body>

    <header>
        <div class="header-logo">
            <span class="badge">SCC</span>
            <h1>Sanctuary Command Center</h1>
        </div>
        <div id="vramBanner">VRAM Loading...</div>
        <div class="header-time" id="headerClock">--:--:--</div>
    </header>

    <!-- Navigation Tabs -->
    <div class="tabs-nav">
        <button class="tab-btn active" id="tab-system"   onclick="switchTab('system')">&#128187; System Monitor</button>
        <button class="tab-btn"        id="tab-ai"       onclick="switchTab('ai')">&#129504; AI Matrix</button>
        <button class="tab-btn"        id="tab-prompt"   onclick="switchTab('prompt')">&#10024; Prompt Generator</button>
        <button class="tab-btn"        id="tab-curator"  onclick="switchTab('curator')">&#128444; Dataset Curator</button>
        <button class="tab-btn"        id="tab-terminals"onclick="switchTab('terminals')">&#128187; Terminals</button>
        <button class="tab-btn"        id="tab-launchers"onclick="switchTab('launchers')">&#128640; Launchers</button>
        <button class="tab-btn"        id="tab-explorer" onclick="switchTab('explorer')">&#128193; File Explorer</button>
        <button class="tab-btn"        id="tab-search"   onclick="switchTab('search')">&#128269; Search</button>
    </div>

    <!-- ================================================================
         TAB 1: SYSTEM MONITOR
    ================================================================ -->
    <div class="tab-content active" id="tabContent-system">
        <div class="grid-stats">
            <div class="card-stat">
                <div class="stat-header"><span>CPU Load</span><span id="cpuTemp">--</span></div>
                <div class="stat-value" id="cpuLoad">0%</div>
                <div class="stat-sub">Processor workload</div>
                <div class="progress-bar"><div class="progress-fill" id="cpuProgress" style="width:0%"></div></div>
            </div>
            <div class="card-stat">
                <div class="stat-header"><span>System RAM</span><span id="ramRaw">0 GB</span></div>
                <div class="stat-value" id="ramPct">0%</div>
                <div class="stat-sub">Memory allocation</div>
                <div class="progress-bar"><div class="progress-fill" id="ramProgress" style="width:0%"></div></div>
            </div>
            <div class="card-stat">
                <div class="stat-header"><span>GPU VRAM</span><span id="vramRaw">0 GB</span></div>
                <div class="stat-value" id="vramPct">0%</div>
                <div class="stat-sub" id="gpuTemp">Temp: --C</div>
                <div class="progress-bar"><div class="progress-fill" id="vramProgress" style="width:0%"></div></div>
            </div>
            <div class="card-stat">
                <div class="stat-header"><span>GPU Core Load</span><span>NVIDIA</span></div>
                <div class="stat-value" id="gpuLoad">0%</div>
                <div class="stat-sub">Graphics pipeline load</div>
                <div class="progress-bar"><div class="progress-fill" id="gpuLoadProgress" style="width:0%"></div></div>
            </div>
        </div>

        <div class="panel-grid-2">
            <div class="panel">
                <div class="panel-title"><span>Resource Hog Processes</span></div>
                <div style="overflow-x:auto">
                    <table>
                        <thead><tr><th>PID</th><th>Name</th><th>CPU</th><th>RAM</th><th style="text-align:right">Control</th></tr></thead>
                        <tbody id="processTableBody"><tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Scanning...</td></tr></tbody>
                    </table>
                </div>
            </div>
            <div class="panel">
                <div class="panel-title"><span>Drive Storage</span></div>
                <div class="drives-grid" id="drivesContainer"></div>
            </div>
        </div>
    </div>

    <!-- ================================================================
         TAB 2: AI MATRIX
    ================================================================ -->
    <div class="tab-content" id="tabContent-ai">
        <div class="vram-panic-bar">
            <div>
                <h4 style="color:var(--danger);font-size:14px;font-weight:700">VRAM Panic Release</h4>
                <p style="font-size:11px;color:var(--text-secondary);margin-top:2px">Kills Ollama, Kobold, and WebUI Forge in one click.</p>
            </div>
            <button class="btn-danger" onclick="executePanic()">Nuke GPU Pipelines</button>
        </div>

        <div class="panel-grid-2">
            <div class="panel">
                <div class="panel-title"><span>AI Application Matrix</span></div>
                <div id="appContainer"></div>
            </div>
            <div class="panel">
                <div class="panel-title"><span>KoboldCPP Launcher</span></div>
                <div style="display:flex;flex-direction:column;gap:14px">
                    <div style="display:flex;flex-direction:column;gap:6px">
                        <label>Select GGUF Model</label>
                        <select id="ggufSelect"><option value="">-- Scanning models... --</option></select>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>GPU Layers</label>
                            <input type="number" id="gpuLayers" value="35" min="0" max="200">
                        </div>
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>Context Size</label>
                            <input type="number" id="contextSize" value="4096" step="1024">
                        </div>
                    </div>
                    <button class="btn-primary" onclick="launchKobold()">Launch Selected Model</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ================================================================
         TAB 3: PROMPT GENERATOR
    ================================================================ -->
    <div class="tab-content" id="tabContent-prompt">
        <div class="prompt-grid">
            <!-- LEFT: Controls -->
            <div style="display:flex;flex-direction:column;gap:18px">
                <div class="panel">
                    <div class="panel-title"><span>Model &amp; Subject</span></div>
                    <div style="display:flex;flex-direction:column;gap:12px">
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>Ollama Model</label>
                            <select id="ollamaModelSelect"><option value="">-- Loading models... --</option></select>
                        </div>
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>Subject / Scene Seed</label>
                            <input type="text" id="promptSubject" placeholder="e.g. Amy, cyberpunk alley, intimate portrait...">
                        </div>
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>Extra Context (optional)</label>
                            <textarea id="promptContext" rows="3" placeholder="mood, artistic direction, clothing, setting..."></textarea>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>Camera &amp; Lens</span></div>
                    <div class="preset-row" id="chipsCamera">
                        <div class="preset-chip" data-group="camera" data-val="shot on 35mm lens">35mm</div>
                        <div class="preset-chip" data-group="camera" data-val="shot on 85mm portrait lens">85mm Portrait</div>
                        <div class="preset-chip" data-group="camera" data-val="ultra wide angle lens">Wide Angle</div>
                        <div class="preset-chip" data-group="camera" data-val="50mm cinematic lens">50mm Cine</div>
                        <div class="preset-chip" data-group="camera" data-val="macro lens extreme closeup">Macro</div>
                        <div class="preset-chip" data-group="camera" data-val="telephoto 200mm lens">Telephoto 200mm</div>
                        <div class="preset-chip" data-group="camera" data-val="fish-eye lens distortion">Fish-Eye</div>
                        <div class="preset-chip" data-group="camera" data-val="tilt-shift lens bokeh blur">Tilt-Shift</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>Lighting Preset</span></div>
                    <div class="preset-row" id="chipsLighting">
                        <div class="preset-chip" data-group="lighting" data-val="dramatic chiaroscuro lighting">Chiaroscuro</div>
                        <div class="preset-chip" data-group="lighting" data-val="volumetric god rays lighting">Volumetric</div>
                        <div class="preset-chip" data-group="lighting" data-val="neon cyberpunk rim lighting">Neon Rim</div>
                        <div class="preset-chip" data-group="lighting" data-val="soft golden hour sunlight">Golden Hour</div>
                        <div class="preset-chip" data-group="lighting" data-val="studio three-point lighting">Studio 3-Point</div>
                        <div class="preset-chip" data-group="lighting" data-val="candlelight warm ambient">Candlelight</div>
                        <div class="preset-chip" data-group="lighting" data-val="moonlit blue ambient night">Moonlit Night</div>
                        <div class="preset-chip" data-group="lighting" data-val="backlit silhouette contre-jour">Backlit</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>Composition &amp; Mood</span></div>
                    <div class="preset-row" id="chipsMood">
                        <div class="preset-chip" data-group="mood" data-val="dutch tilt angle composition">Dutch Tilt</div>
                        <div class="preset-chip" data-group="mood" data-val="low angle hero shot">Low Angle</div>
                        <div class="preset-chip" data-group="mood" data-val="bird's eye view aerial">Bird's Eye</div>
                        <div class="preset-chip" data-group="mood" data-val="rule of thirds framing">Rule of Thirds</div>
                        <div class="preset-chip" data-group="mood" data-val="cinematic widescreen 2.39:1">Cinematic</div>
                        <div class="preset-chip" data-group="mood" data-val="intimate close-up portrait framing">Intimate</div>
                        <div class="preset-chip" data-group="mood" data-val="symmetrical centered composition">Symmetrical</div>
                        <div class="preset-chip" data-group="mood" data-val="over-the-shoulder POV shot">OTS POV</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>Art Style</span></div>
                    <div class="preset-row" id="chipsStyle">
                        <div class="preset-chip" data-group="style" data-val="hyperrealistic photographic">Hyperrealistic</div>
                        <div class="preset-chip" data-group="style" data-val="digital oil painting">Oil Painting</div>
                        <div class="preset-chip" data-group="style" data-val="anime illustration style">Anime</div>
                        <div class="preset-chip" data-group="style" data-val="dark fantasy concept art">Dark Fantasy</div>
                        <div class="preset-chip" data-group="style" data-val="retro synthwave aesthetic">Synthwave</div>
                        <div class="preset-chip" data-group="style" data-val="film noir black and white photography">Film Noir</div>
                        <div class="preset-chip" data-group="style" data-val="impressionist painterly texture">Impressionist</div>
                        <div class="preset-chip" data-group="style" data-val="glitch art digital corruption">Glitch Art</div>
                    </div>
                </div>

                <button class="btn-primary" id="generateBtn" onclick="generatePrompt()" style="width:100%;padding:13px;font-size:14px">
                    Generate Prompt via Ollama
                </button>
            </div>

            <!-- RIGHT: Output -->
            <div style="display:flex;flex-direction:column;gap:16px">
                <div class="panel" style="flex:1">
                    <div class="panel-title">
                        <span>Generated Output</span>
                        <div style="display:flex;gap:8px">
                            <button onclick="copyPrompt('pos')" style="font-size:11px;padding:4px 10px">Copy Positive</button>
                            <button onclick="copyPrompt('neg')" style="font-size:11px;padding:4px 10px">Copy Negative</button>
                            <button onclick="copyPrompt('both')" style="font-size:11px;padding:4px 10px;background:var(--gradient);border:none">Copy Both</button>
                        </div>
                    </div>
                    <div class="prompt-label pos">POSITIVE</div>
                    <div class="prompt-output" id="promptPositive">Waiting for generation...</div>
                    <br>
                    <div class="prompt-label neg">NEGATIVE</div>
                    <div class="prompt-output" id="promptNegative" style="min-height:80px">--</div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>Assembled Prefix Tags</span></div>
                    <div id="previewTags" class="prompt-output" style="min-height:60px;color:var(--accent-cyan)">-- select presets above --</div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>Generation Log</span></div>
                    <div id="promptLog" class="prompt-output" style="min-height:80px;color:var(--text-muted)">Idle.</div>
                </div>
            </div>
        </div>
    </div>

    <!-- ================================================================
         TAB 4: DATASET CURATOR
    ================================================================ -->
    <div class="tab-content" id="tabContent-curator">
        <div class="sdc-grid">
            <!-- Controls Panel -->
            <div class="sdc-panel">
                <div class="panel">
                    <div class="panel-title"><span>Scan Directory</span></div>
                    <div style="display:flex;flex-direction:column;gap:10px">
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>Source Path</label>
                            <input type="text" id="sdcPath" value="D:\AI\Projects\ComfyUI\input\Amy_Master" style="width:100%">
                        </div>
                        <button class="btn-primary" onclick="sdcScan()">Scan for Images</button>
                        <div id="sdcScanStatus" style="font-size:11px;color:var(--text-muted)">Ready.</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>Selected Image</span></div>
                    <div id="sdcSelectedPreview" style="text-align:center;padding:20px;color:var(--text-muted)">
                        No image selected.
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title"><span>VLM Auto-Tag</span></div>
                    <div style="display:flex;flex-direction:column;gap:10px">
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>Vision Model</label>
                            <select id="sdcVlmModel"><option value="">-- Loading... --</option></select>
                        </div>
                        <div style="display:flex;flex-direction:column;gap:6px">
                            <label>Tag Instruction</label>
                            <textarea id="sdcTagInstruction" rows="3">Describe this image in detailed Stable Diffusion tags. List visual elements, pose, clothing, lighting, style, separated by commas. Be explicit and precise.</textarea>
                        </div>
                        <button class="btn-cyan" onclick="sdcTagSelected()" id="sdcTagBtn">Tag Selected Image</button>
                        <div id="sdcTagOutput" class="prompt-output" style="min-height:80px;color:var(--accent-cyan)">--</div>
                    </div>
                </div>
            </div>

            <!-- Gallery Panel -->
            <div class="sdc-panel">
                <div class="panel" style="flex:1">
                    <div class="panel-title">
                        <span>Image Gallery</span>
                        <span id="sdcImageCount" style="font-size:11px;color:var(--text-muted)">0 images</span>
                    </div>
                    <div class="image-gallery" id="sdcGallery">
                        <div style="color:var(--text-muted);font-size:13px;grid-column:1/-1;text-align:center;padding:40px">Scan a directory to load images.</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- ================================================================
         TAB 5: TERMINALS
    ================================================================ -->
    <div class="tab-content" id="tabContent-terminals">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">
            <h3 style="font-size:15px;font-weight:700">Live Process Terminals</h3>
            <div style="display:flex;gap:10px">
                <button onclick="clearAllLogs()">Clear All</button>
                <button class="btn-cyan" onclick="pollTerminals()">Refresh Now</button>
            </div>
        </div>
        <div class="terminal-grid" id="terminalGrid">
            <!-- Rendered by JS -->
        </div>
    </div>

    <!-- ================================================================
         TAB 6: LAUNCHERS
    ================================================================ -->
    <div class="tab-content" id="tabContent-launchers">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">
            <h3 style="font-size:15px;font-weight:700">AI Launchers Directory</h3>
            <button onclick="openLaunchersFolder()">Open in Windows</button>
        </div>
        <div class="launchers-grid" id="launchersContainer">
            <div style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:40px">Loading launchers...</div>
        </div>
    </div>

    <!-- ================================================================
         TAB 7: FILE EXPLORER
    ================================================================ -->
    <div class="tab-content" id="tabContent-explorer">
        <div class="panel">
            <div class="panel-title"><span>Sanctuary File Explorer</span></div>
            <div class="explorer-layout">
                <div class="explorer-sidebar" id="explorerShortcutsContainer"></div>
                <div class="explorer-main">
                    <div class="explorer-toolbar">
                        <button onclick="navigateUp()" style="padding:6px 12px;font-size:12px">&uarr; Up</button>
                        <div class="breadcrumbs" id="currentPathLabel">D:\\AI\\Projects</div>
                        <button onclick="openCurrentDirInHost()" style="padding:6px 12px;font-size:12px">Show in Windows</button>
                    </div>
                    <div class="explorer-list" id="explorerList">
                        <div style="text-align:center;padding:40px;color:var(--text-muted)">Initializing...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- ================================================================
         TAB 8: SEARCH
    ================================================================ -->
    <div class="tab-content" id="tabContent-search">
        <div class="panel">
            <div class="panel-title"><span>Everything Search Indexer</span></div>
            <div class="search-bar-container">
                <input type="text" class="search-input" id="searchInput" placeholder="Search filenames: *.safetensors, Amy_Face, prompt..." onkeyup="checkSearchEnter(event)">
                <button class="btn-primary" onclick="triggerSearch()">Execute Search</button>
            </div>
            <div style="overflow-x:auto;max-height:500px">
                <table>
                    <thead><tr><th>File Name</th><th>Size (MB)</th><th>Path</th><th style="text-align:right">Control</th></tr></thead>
                    <tbody id="searchResultsBody"><tr><td colspan="4" style="text-align:center;color:var(--text-muted)">Enter query above...</td></tr></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Lightbox -->
    <div class="lightbox-overlay" id="mediaLightbox" onclick="closeLightbox()">
        <div class="lightbox-card" onclick="event.stopPropagation()">
            <span class="lightbox-close" onclick="closeLightbox()">&times;</span>
            <div id="lightboxContent" style="display:flex;flex-direction:column;align-items:center;gap:14px"></div>
        </div>
    </div>

    <!-- Toast -->
    <div id="toast"></div>

    <script>
        // ============================================================
        //  GLOBAL STATE
        // ============================================================
        let currentExplorerPath = "D:\\\\AI\\\\Projects";
        let selectedPresets = { camera: null, lighting: null, mood: null, style: null };
        let sdcSelectedFile = null;
        let terminalPollInterval = null;

        // Clock
        function updateClock() {
            const now = new Date();
            document.getElementById('headerClock').textContent = now.toLocaleTimeString('en-US', {hour12: false});
        }
        setInterval(updateClock, 1000);
        updateClock();

        // Toast helper
        function showToast(msg, color) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.style.color = color || 'var(--text-primary)';
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 2800);
        }

        // ============================================================
        //  TAB SWITCHING
        // ============================================================
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const btn = document.getElementById('tab-' + tabId);
            if (btn) btn.classList.add('active');
            const content = document.getElementById('tabContent-' + tabId);
            if (content) content.classList.add('active');
            if (tabId === 'explorer') loadDirectory(currentExplorerPath);
            if (tabId === 'launchers') loadLaunchers();
            if (tabId === 'terminals') pollTerminals();
            if (tabId === 'prompt') fetchOllamaModels();
            if (tabId === 'curator') { fetchOllamaModels(); populateSdcVlmModels(); }
        }

        // ============================================================
        //  STATS POLLING
        // ============================================================
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const d = await res.json();
                document.getElementById('cpuLoad').textContent    = d.system.cpu_load + '%';
                document.getElementById('cpuProgress').style.width = d.system.cpu_load + '%';
                document.getElementById('ramPct').textContent     = d.system.ram_pct + '%';
                document.getElementById('ramProgress').style.width = d.system.ram_pct + '%';
                document.getElementById('ramRaw').textContent     = d.system.ram_used_gb + ' / ' + d.system.ram_total_gb + ' GB';

                const vp = d.gpu.pct;
                document.getElementById('vramPct').textContent     = vp + '%';
                document.getElementById('vramProgress').style.width = vp + '%';
                document.getElementById('vramRaw').textContent     = (d.gpu.vram_used/1024).toFixed(1) + ' / ' + (d.gpu.vram_total/1024).toFixed(1) + ' GB';
                document.getElementById('gpuTemp').textContent     = 'Temp: ' + d.gpu.temp + 'C';
                document.getElementById('gpuLoad').textContent     = d.gpu.load + '%';
                document.getElementById('gpuLoadProgress').style.width = d.gpu.load + '%';
                document.getElementById('vramBanner').textContent  = 'VRAM: ' + (d.gpu.vram_used/1024).toFixed(1) + ' / ' + (d.gpu.vram_total/1024).toFixed(1) + ' GB (' + vp + '%)';

                // Apps
                const ac = document.getElementById('appContainer');
                ac.innerHTML = '';
                for (const [key, app] of Object.entries(d.apps)) {
                    const row = document.createElement('div');
                    row.className = 'app-row';
                    row.innerHTML = '<div style="display:flex;align-items:center;gap:12px">' +
                        '<div class="app-indicator ' + (app.running ? 'active' : '') + '"></div>' +
                        '<div>' +
                            '<div style="font-size:13px;font-weight:600">' + app.name + '</div>' +
                            '<div style="font-size:10px;color:var(--text-muted);margin-top:2px">Port ' + app.port + '</div>' +
                        '</div></div>' +
                        '<div style="display:flex;align-items:center;gap:8px">' +
                            '<span class="badge-tag ' + (app.running ? 'badge-running' : 'badge-stopped') + '">' + (app.running ? 'ONLINE' : 'OFFLINE') + '</span>' +
                            (app.running ?
                                '<button class="btn-danger" style="font-size:11px;padding:4px 10px" onclick="killApp(\'' + key + '\')">Kill</button>' :
                                '<button style="font-size:11px;padding:4px 10px" onclick="launchApp(\'' + key + '\')">Launch</button>') +
                        '</div>';
                    ac.appendChild(row);
                }

                // Drives
                const dc = document.getElementById('drivesContainer');
                dc.innerHTML = '';
                d.drives.forEach(drive => {
                    const row = document.createElement('div');
                    row.className = 'drive-row';
                    const danger = drive.pct > 88;
                    row.innerHTML =
                        '<div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;margin-bottom:5px">' +
                            '<span>Drive ' + drive.letter + '</span>' +
                            '<span style="font-family:JetBrains Mono,monospace;color:' + (danger ? 'var(--danger)' : 'var(--text-secondary)') + '">' + drive.used_gb + ' / ' + drive.total_gb + ' GB</span>' +
                        '</div>' +
                        '<div class="progress-bar"><div class="progress-fill" style="width:' + drive.pct + '%;background:' + (danger ? 'var(--danger)' : 'var(--gradient)') + '"></div></div>';
                    dc.appendChild(row);
                });

                // Processes
                const tb = document.getElementById('processTableBody');
                tb.innerHTML = '';
                d.processes.forEach(proc => {
                    const tr = document.createElement('tr');
                    tr.innerHTML =
                        '<td>' + proc.pid + '</td>' +
                        '<td style="color:var(--accent-hover);font-weight:600">' + proc.name + '</td>' +
                        '<td>' + proc.cpu + '%</td>' +
                        '<td>' + proc.ram + ' MB</td>' +
                        '<td style="text-align:right"><button class="btn-danger" style="padding:2px 8px;font-size:10px" onclick="killPid(' + proc.pid + ')">Kill</button></td>';
                    tb.appendChild(tr);
                });

            } catch(e) {}
        }

        // ============================================================
        //  AI MATRIX ACTIONS
        // ============================================================
        async function fetchModels() {
            try {
                const res = await fetch('/api/models');
                const d = await res.json();
                const sel = document.getElementById('ggufSelect');
                sel.innerHTML = '<option value="">-- Choose GGUF model --</option>';
                d.models.forEach(m => {
                    const o = document.createElement('option');
                    o.value = m; o.textContent = m;
                    sel.appendChild(o);
                });
            } catch(e) {}
        }

        async function launchApp(key) { await fetch('/api/launch?app=' + key); setTimeout(fetchStats, 1200); showToast('Launch signal sent for ' + key, 'var(--success)'); }
        async function killApp(key)   { await fetch('/api/kill?app=' + key);   setTimeout(fetchStats, 800);  showToast('Kill signal sent for ' + key,   'var(--danger)'); }
        async function killPid(pid)   { if (confirm('Kill PID ' + pid + '?')) { await fetch('/api/killpid?pid=' + pid); setTimeout(fetchStats, 600); } }

        async function launchKobold() {
            const model   = document.getElementById('ggufSelect').value;
            const layers  = document.getElementById('gpuLayers').value;
            const context = document.getElementById('contextSize').value;
            if (!model) return showToast('Select a GGUF model first!', 'var(--warning)');
            await fetch('/api/launch-kobold?model=' + encodeURIComponent(model) + '&layers=' + layers + '&context=' + context);
            showToast('KoboldCPP launching...', 'var(--success)');
        }

        async function executePanic() {
            if (confirm('Kill ALL active AI pipelines? This will nuke Ollama, Kobold, and Forge.')) {
                await fetch('/api/panic');
                showToast('All AI pipelines terminated.', 'var(--danger)');
                setTimeout(fetchStats, 1500);
            }
        }

        // ============================================================
        //  PROMPT GENERATOR
        // ============================================================
        async function fetchOllamaModels() {
            try {
                const res = await fetch('/api/ollama/models');
                const d = await res.json();
                const sel = document.getElementById('ollamaModelSelect');
                sel.innerHTML = d.models.length ? '' : '<option value="">-- No Ollama models found --</option>';
                d.models.forEach(m => {
                    const o = document.createElement('option');
                    o.value = m; o.textContent = m;
                    if (m.includes('nsfw') || m.includes('prompt')) o.selected = true;
                    sel.appendChild(o);
                });
            } catch(e) {
                document.getElementById('ollamaModelSelect').innerHTML = '<option value="">-- Ollama offline --</option>';
            }
        }

        // Preset chips — single-select per group
        document.querySelectorAll('.preset-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const group = chip.dataset.group;
                if (selectedPresets[group] === chip.dataset.val) {
                    selectedPresets[group] = null;
                    chip.classList.remove('selected');
                } else {
                    document.querySelectorAll('.preset-chip[data-group="' + group + '"]').forEach(c => c.classList.remove('selected'));
                    chip.classList.add('selected');
                    selectedPresets[group] = chip.dataset.val;
                }
                updatePreviewTags();
            });
        });

        function updatePreviewTags() {
            const parts = Object.values(selectedPresets).filter(Boolean);
            document.getElementById('previewTags').textContent = parts.length ? parts.join(', ') : '-- select presets above --';
        }

        function buildPromptInstruction() {
            const subject = document.getElementById('promptSubject').value.trim();
            const context = document.getElementById('promptContext').value.trim();
            const presets = Object.values(selectedPresets).filter(Boolean);
            const presetStr = presets.length ? presets.join(', ') : '';

            let instruction = 'You are an expert Stable Diffusion / Flux prompt engineer. ';
            instruction += 'Generate a detailed, evocative image generation prompt.\\n\\n';
            if (subject) instruction += 'Subject/Scene: ' + subject + '\\n';
            if (presetStr) instruction += 'Required visual tags to weave in: ' + presetStr + '\\n';
            if (context) instruction += 'Additional context: ' + context + '\\n';
            instruction += '\\nRespond ONLY with:\\nPOSITIVE: [comma-separated tags, natural language description]\\nNEGATIVE: [things to avoid]\\n\\nBe detailed. Include anatomy quality tags, render quality boosters, style descriptors.';
            return instruction;
        }

        async function generatePrompt() {
            const model = document.getElementById('ollamaModelSelect').value;
            if (!model) return showToast('Select an Ollama model first.', 'var(--warning)');

            const btn = document.getElementById('generateBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span>Generating...';
            document.getElementById('promptLog').textContent = 'Sending request to Ollama...';
            document.getElementById('promptPositive').textContent = 'Generating...';
            document.getElementById('promptNegative').textContent = 'Generating...';

            try {
                const res = await fetch('/api/generate-prompt', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: model, prompt: buildPromptInstruction() })
                });
                const d = await res.json();
                if (d.error) throw new Error(d.error);
                document.getElementById('promptPositive').textContent = d.positive || '(empty)';
                document.getElementById('promptNegative').textContent = d.negative || '(empty)';
                document.getElementById('promptLog').textContent = 'Done. Model: ' + model + ' | Tokens: ~' + ((d.positive || '').split(',').length + (d.negative || '').split(',').length) + ' tags.';
                showToast('Prompt generated!', 'var(--success)');
            } catch(err) {
                document.getElementById('promptPositive').textContent = 'ERROR: ' + err.message;
                document.getElementById('promptLog').textContent = 'Failed: ' + err.message;
                showToast('Generation failed: ' + err.message, 'var(--danger)');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Generate Prompt via Ollama';
            }
        }

        function copyPrompt(which) {
            const pos = document.getElementById('promptPositive').textContent;
            const neg = document.getElementById('promptNegative').textContent;
            let text = '';
            if (which === 'pos')  text = pos;
            if (which === 'neg')  text = neg;
            if (which === 'both') text = pos + '\\n\\nNEGATIVE: ' + neg;
            navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard!', 'var(--success)'));
        }

        // ============================================================
        //  DATASET CURATOR
        // ============================================================
        async function populateSdcVlmModels() {
            try {
                const res = await fetch('/api/ollama/models');
                const d = await res.json();
                const sel = document.getElementById('sdcVlmModel');
                sel.innerHTML = '';
                d.models.forEach(m => {
                    const o = document.createElement('option');
                    o.value = m; o.textContent = m;
                    sel.appendChild(o);
                });
                if (!d.models.length) sel.innerHTML = '<option value="">-- No models --</option>';
            } catch(e) {}
        }

        async function sdcScan() {
            const path = document.getElementById('sdcPath').value.trim();
            if (!path) return showToast('Enter a directory path.', 'var(--warning)');
            document.getElementById('sdcScanStatus').textContent = 'Scanning...';
            document.getElementById('sdcGallery').innerHTML = '<div style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:40px">Scanning...</div>';
            try {
                const res = await fetch('/api/sdc/scan?path=' + encodeURIComponent(path));
                const d = await res.json();
                if (d.error) throw new Error(d.error);
                document.getElementById('sdcImageCount').textContent = d.images.length + ' images';
                document.getElementById('sdcScanStatus').textContent = 'Found ' + d.images.length + ' images.';
                renderSdcGallery(d.images);
            } catch(err) {
                document.getElementById('sdcScanStatus').textContent = 'Error: ' + err.message;
                showToast('Scan failed: ' + err.message, 'var(--danger)');
            }
        }

        function renderSdcGallery(images) {
            const gal = document.getElementById('sdcGallery');
            gal.innerHTML = '';
            if (!images.length) {
                gal.innerHTML = '<div style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:40px">No images found.</div>';
                return;
            }
            images.forEach(img => {
                const thumb = document.createElement('div');
                thumb.className = 'gallery-thumb';
                thumb.innerHTML =
                    '<img src="/api/sdc/thumb?path=' + encodeURIComponent(img.path) + '" loading="lazy" alt="' + img.name + '">' +
                    '<div class="thumb-label">' + img.name + '</div>';
                thumb.onclick = () => selectSdcImage(img, thumb);
                gal.appendChild(thumb);
            });
        }

        function selectSdcImage(img, el) {
            document.querySelectorAll('.gallery-thumb').forEach(t => t.classList.remove('selected'));
            el.classList.add('selected');
            sdcSelectedFile = img;
            document.getElementById('sdcSelectedPreview').innerHTML =
                '<img src="/api/sdc/thumb?path=' + encodeURIComponent(img.path) + '" style="max-width:100%;max-height:200px;border-radius:10px;border:1px solid var(--border)">' +
                '<p style="font-size:11px;color:var(--text-muted);margin-top:8px;font-family:JetBrains Mono,monospace">' + img.name + '</p>';
        }

        async function sdcTagSelected() {
            if (!sdcSelectedFile) return showToast('Select an image first.', 'var(--warning)');
            const model = document.getElementById('sdcVlmModel').value;
            if (!model) return showToast('Select a VLM model.', 'var(--warning)');
            const instruction = document.getElementById('sdcTagInstruction').value;
            const btn = document.getElementById('sdcTagBtn');
            btn.disabled = true; btn.textContent = 'Tagging...';
            document.getElementById('sdcTagOutput').textContent = 'Sending to Ollama VLM...';
            try {
                const res = await fetch('/api/sdc/tag-vlm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: sdcSelectedFile.path, model: model, instruction: instruction })
                });
                const d = await res.json();
                if (d.error) throw new Error(d.error);
                document.getElementById('sdcTagOutput').textContent = d.tags;
                showToast('Tags generated!', 'var(--success)');
            } catch(err) {
                document.getElementById('sdcTagOutput').textContent = 'Error: ' + err.message;
                showToast('Tag failed: ' + err.message, 'var(--danger)');
            } finally {
                btn.disabled = false; btn.textContent = 'Tag Selected Image';
            }
        }

        // ============================================================
        //  TERMINALS
        // ============================================================
        async function pollTerminals() {
            try {
                const res = await fetch('/api/terminals/logs');
                const d = await res.json();
                const grid = document.getElementById('terminalGrid');
                if (!d.streams || Object.keys(d.streams).length === 0) {
                    grid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;text-align:center;padding:60px;grid-column:1/-1">No active process streams. Launch Forge, Kobold, or Ollama to see terminal output here.</div>';
                    return;
                }
                for (const [key, lines] of Object.entries(d.streams)) {
                    let win = document.getElementById('term-' + key);
                    if (!win) {
                        win = document.createElement('div');
                        win.className = 'terminal-window';
                        win.id = 'term-' + key;
                        win.innerHTML =
                            '<div class="terminal-header">' +
                                '<span class="terminal-title">' + key.toUpperCase() + '</span>' +
                                '<div style="display:flex;align-items:center;gap:8px">' +
                                    '<div class="terminal-dot"></div>' +
                                    '<button onclick="clearLog(\'' + key + '\')" style="font-size:10px;padding:2px 8px">Clear</button>' +
                                '</div>' +
                            '</div>' +
                            '<div class="terminal-body" id="tbody-' + key + '"></div>';
                        grid.appendChild(win);
                    }
                    const body = document.getElementById('tbody-' + key);
                    body.innerHTML = '';
                    lines.forEach(line => {
                        const span = document.createElement('div');
                        span.className = 'terminal-line';
                        span.textContent = line;
                        if (line.includes('ERROR') || line.includes('error')) span.style.color = 'var(--danger)';
                        else if (line.includes('WARNING') || line.includes('warn')) span.style.color = 'var(--warning)';
                        body.appendChild(span);
                    });
                    body.scrollTop = body.scrollHeight;
                }
            } catch(e) {}
        }

        async function clearLog(key) {
            await fetch('/api/terminals/clear?key=' + encodeURIComponent(key));
            pollTerminals();
        }

        async function clearAllLogs() {
            await fetch('/api/terminals/clear-all');
            document.getElementById('terminalGrid').innerHTML = '';
            pollTerminals();
        }

        // ============================================================
        //  LAUNCHERS
        // ============================================================
        async function loadLaunchers() {
            try {
                const res = await fetch('/api/launchers');
                const d = await res.json();
                const con = document.getElementById('launchersContainer');
                con.innerHTML = '';
                if (!d.launchers || !d.launchers.length) {
                    con.innerHTML = '<div style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:40px">No launchers found in D:\\\\AI\\\\Launchers</div>';
                    return;
                }
                d.launchers.forEach(item => {
                    const ext = item.filename.split('.').pop();
                    const card = document.createElement('div');
                    card.className = 'launcher-card';
                    card.innerHTML =
                        '<div><div class="launcher-title">' + item.name + '</div><div class="launcher-ext">' + ext + '</div></div>' +
                        '<button class="btn-primary" onclick="launchFile(\'' + item.filename.replace(/'/g, "\\'") + '\')" style="width:100%">Execute</button>';
                    con.appendChild(card);
                });
            } catch(e) {}
        }

        async function launchFile(filename) {
            try {
                const res = await fetch('/api/launch-file?file=' + encodeURIComponent(filename));
                const d = await res.json();
                showToast('Launched: ' + filename, 'var(--success)');
            } catch(e) { showToast('Launch failed', 'var(--danger)'); }
        }

        async function openLaunchersFolder() {
            await fetch('/api/open-launchers-folder');
        }

        // ============================================================
        //  FILE EXPLORER
        // ============================================================
        async function loadExplorerShortcuts() {
            try {
                const res = await fetch('/api/folders');
                const d = await res.json();
                const con = document.getElementById('explorerShortcutsContainer');
                con.innerHTML = '';
                ['C:\\\\', 'D:\\\\', 'E:\\\\', 'G:\\\\'].forEach(dr => {
                    const item = document.createElement('div');
                    item.className = 'shortcut-item';
                    item.onclick = () => loadDirectory(dr);
                    item.innerHTML = '<span>&#128190;</span><span style="font-weight:700">Drive ' + dr.slice(0,2) + '</span>';
                    con.appendChild(item);
                });
                const div = document.createElement('div');
                div.style.cssText = 'height:1px;background:var(--border);margin:6px 0';
                con.appendChild(div);
                d.folders.forEach(f => {
                    const item = document.createElement('div');
                    item.className = 'shortcut-item';
                    item.onclick = () => loadDirectory(f.path);
                    item.innerHTML = '<span>&#128193;</span><span>' + f.name + '</span>';
                    con.appendChild(item);
                });
            } catch(e) {}
        }

        async function loadDirectory(path) {
            currentExplorerPath = path;
            document.getElementById('currentPathLabel').textContent = path;
            const con = document.getElementById('explorerList');
            con.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>';
            try {
                const res = await fetch('/api/explorer/list?path=' + encodeURIComponent(path));
                const d = await res.json();
                if (d.error) { con.innerHTML = '<div style="text-align:center;padding:40px;color:var(--danger)">' + d.error + '</div>'; return; }
                con.innerHTML = '';
                if (!d.items.length) { con.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Folder is empty</div>'; return; }
                d.items.forEach(item => {
                    const row = document.createElement('div');
                    row.className = 'file-item';
                    row.setAttribute('data-path', item.path);
                    row.setAttribute('data-name', item.name);
                    row.setAttribute('data-isdir', item.is_dir ? 'true' : 'false');
                    
                    const icon = item.is_dir ? '&#128193;' : getFileIcon(item.name);
                    const size = item.is_dir ? '' : item.size + ' MB';
                    row.innerHTML =
                        '<div class="file-meta" onclick="handleFileClick(this)">' +
                            '<span class="file-icon">' + icon + '</span>' +
                            '<span class="file-name">' + item.name + '</span>' +
                            '<span class="file-size">' + size + '</span>' +
                        '</div>' +
                        '<div class="file-actions"><button onclick="handleShowClick(this)" style="padding:2px 8px;font-size:10px">Show</button></div>';
                    con.appendChild(row);
                });
            } catch(e) { con.innerHTML = '<div style="text-align:center;padding:40px;color:var(--danger)">Connection error</div>'; }
        }

        function getFileIcon(name) {
            const ext = name.split('.').pop().toLowerCase();
            if (['png','jpg','jpeg','webp','gif'].includes(ext)) return '&#128444;';
            if (['txt','json','yaml','yml','md','bat','py'].includes(ext)) return '&#128196;';
            if (['safetensors','bin','ckpt','gguf'].includes(ext)) return '&#128230;';
            return '&#128196;';
        }

        function navigateUp() {
            const sep = currentExplorerPath.includes('\\\\') ? '\\\\\\\\' : '\\\\';
            const parts = currentExplorerPath.split(sep);
            if (parts.length > 1) {
                parts.pop();
                let parent = parts.join('\\\\');
                if (parent.match(/^[A-Z]:$/i)) parent += '\\\\';
                loadDirectory(parent);
            }
        }

        async function openCurrentDirInHost() { await fetch('/api/open-folder?path=' + encodeURIComponent(currentExplorerPath)); }
        async function openFileDirectory(p)   { await fetch('/api/open-file-dir?path=' + encodeURIComponent(p)); }

        function handleFileClick(el) {
            const card = el.closest('[data-path]');
            const path = card.getAttribute('data-path');
            const name = card.getAttribute('data-name');
            const isDir = card.getAttribute('data-isdir') === 'true';
            if (isDir) {
                loadDirectory(path);
            } else {
                previewFile(path, name);
            }
        }

        function handleShowClick(el) {
            const card = el.closest('[data-path]');
            const path = card.getAttribute('data-path');
            openFileDirectory(path);
        }

        async function previewFile(path, name) {
            const ext = name.split('.').pop().toLowerCase();
            const lb = document.getElementById('mediaLightbox');
            const content = document.getElementById('lightboxContent');
            content.innerHTML = '<div style="color:#fff">Loading...</div>';
            lb.style.display = 'flex';
            if (['png','jpg','jpeg','webp','gif'].includes(ext)) {
                content.innerHTML = '<h3 style="font-size:14px;margin-bottom:8px">' + name + '</h3><img src="/api/explorer/view?path=' + encodeURIComponent(path) + '" style="max-width:100%;max-height:480px;border-radius:10px;border:1px solid var(--border)">';
            } else if (['txt','json','yaml','yml','md','bat','py'].includes(ext)) {
                try {
                    const res = await fetch('/api/explorer/view?path=' + encodeURIComponent(path));
                    const text = await res.text();
                    content.innerHTML = '<h3 style="font-size:14px;margin-bottom:8px">' + name + '</h3><pre style="width:660px;height:420px;overflow:auto;text-align:left;background:rgba(0,0,0,0.4);padding:14px;border-radius:10px;font-family:JetBrains Mono,monospace;font-size:11px;white-space:pre-wrap;border:1px solid var(--border);color:var(--text-secondary)">' + escapeHtml(text) + '</pre>';
                } catch(e) { content.innerHTML = '<div style="color:var(--danger)">Failed to load preview</div>'; }
            } else {
                content.innerHTML = '<h3>' + name + '</h3><p style="color:var(--text-muted);font-size:12px;margin-top:8px">Binary file — cannot preview inline.</p><button class="btn-primary" style="margin-top:16px" data-path="' + path + '" onclick="handleShowClick(this)">Open in Windows</button>';
            }
        }

        function closeLightbox() { document.getElementById('mediaLightbox').style.display = 'none'; }
        function escapeHtml(t) { return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;'); }

        // ============================================================
        //  SEARCH
        // ============================================================
        function checkSearchEnter(e) { if (e.key === 'Enter') triggerSearch(); }
        async function triggerSearch() {
            const val = document.getElementById('searchInput').value.trim();
            if (!val) return;
            const tb = document.getElementById('searchResultsBody');
            tb.innerHTML = '<tr><td colspan="4" style="text-align:center">Searching...</td></tr>';
            try {
                const res = await fetch('/api/search?q=' + encodeURIComponent(val));
                const d = await res.json();
                tb.innerHTML = '';
                if (!d.results.length) { tb.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">No results.</td></tr>'; return; }
                d.results.forEach(r => {
                    const tr = document.createElement('tr');
                    tr.setAttribute('data-path', r.path);
                    tr.innerHTML =
                        '<td style="color:var(--text-primary);font-weight:600">' + r.name + '</td>' +
                        '<td>' + r.size + '</td>' +
                        '<td style="color:var(--text-muted)">' + r.path + '</td>' +
                        '<td style="text-align:right"><button onclick="handleShowClick(this)" style="padding:3px 8px;font-size:10px">Show</button></td>';
                    tb.appendChild(tr);
                });
            } catch(e) { document.getElementById('searchResultsBody').innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--danger)">Search failed.</td></tr>'; }
        }

        // ============================================================
        //  INIT
        // ============================================================
        setInterval(fetchStats, 3000);
        setInterval(() => {
            if (document.getElementById('tabContent-terminals').classList.contains('active')) pollTerminals();
        }, 4000);

        fetchStats();
        fetchModels();
        loadExplorerShortcuts();
        fetchOllamaModels();
    </script>
</body>
</html>
"""

# ============================================================
#  HTTP REQUEST HANDLER
# ============================================================
class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # ---- Serve Dashboard ----
        if self.path in ('/', '/index.html'):
            self._json_ok_html(HTML_UI.encode('utf-8'), 'text/html; charset=utf-8')

        # ---- Stats ----
        elif self.path == '/api/stats':
            system = get_system_stats()
            gpu    = get_gpu_stats()
            vram_u = gpu.get("vram_used", 0); vram_t = gpu.get("vram_total", 1)
            gpu["pct"] = round((vram_u / vram_t) * 100, 1) if vram_t else 0
            app_statuses = {k: {"name": v["name"], "port": v["port"], "running": check_port_active(v["port"])} for k, v in APPS.items()}
            self._json_ok({"system": system, "gpu": gpu, "drives": get_disk_stats(), "apps": app_statuses, "processes": get_process_list()})

        # ---- GGUF Models ----
        elif self.path == '/api/models':
            self._json_ok({"models": scan_ggufs()})

        # ---- Ollama models (proxied) ----
        elif self.path == '/api/ollama/models':
            self._json_ok({"models": get_ollama_models()})

        # ---- Launchers ----
        elif self.path == '/api/launchers':
            _skip = ['command_center', 'sanctuary_launcher', 'launch_scc', 'ignite_the_sanctum']
            items = []
            if os.path.exists(LAUNCHERS_DIR):
                try:
                    for f in os.listdir(LAUNCHERS_DIR):
                        if any(k in f.lower().replace(' ','_').replace('-','_') for k in _skip): continue
                        if f.lower().endswith(('.lnk','.bat','.vbs','.ps1')):
                            dn = f
                            for ext in ['.lnk','.bat','.vbs','.ps1']:
                                if dn.lower().endswith(ext): dn = dn[:-len(ext)]
                            dn = dn.replace(" - Shortcut","").replace("_silent"," (Silent)")
                            items.append({"filename": f, "name": dn, "path": os.path.join(LAUNCHERS_DIR, f)})
                except Exception:
                    pass
            self._json_ok({"launchers": sorted(items, key=lambda x: x["name"])})

        # ---- Launch file ----
        elif self.path.startswith('/api/launch-file'):
            params = self._qp()
            fp = os.path.join(LAUNCHERS_DIR, params.get('file',[''])[0])
            status = "failed"
            if os.path.exists(fp):
                try: os.startfile(fp); status = "launched"
                except Exception as e: status = f"error:{e}"
            self._json_ok({"status": status})

        # ---- Open launchers folder ----
        elif self.path == '/api/open-launchers-folder':
            if os.path.exists(LAUNCHERS_DIR): subprocess.Popen(f'explorer.exe "{LAUNCHERS_DIR}"', shell=True)
            self._json_ok({"status": "opened"})

        # ---- Pinned folders ----
        elif self.path == '/api/folders':
            self._json_ok({"folders": EXPLORER_SHORTCUTS})

        # ---- Explorer list ----
        elif self.path.startswith('/api/explorer/list'):
            params = self._qp()
            target = params.get('path',[''])[0]
            if not target or not os.path.exists(target):
                self._json_ok({"error": "Invalid path", "items": []})
                return
            items = []
            try:
                for f in sorted(os.listdir(target)):
                    fp = os.path.join(target, f)
                    is_dir = os.path.isdir(fp)
                    try: size = round(os.path.getsize(fp) / (1024**2), 2) if not is_dir else 0
                    except: size = 0
                    items.append({"name": f, "path": fp, "is_dir": is_dir, "size": size})
                items = sorted(items, key=lambda x: (not x['is_dir'], x['name'].lower()))
            except Exception as e:
                self._json_ok({"error": str(e), "items": []}); return
            self._json_ok({"items": items})

        # ---- Explorer view (raw file or image) ----
        elif self.path.startswith('/api/explorer/view'):
            params = self._qp()
            fp = params.get('path',[''])[0]
            if not fp or not os.path.isfile(fp):
                self.send_error(404); return
            ext = fp.rsplit('.', 1)[-1].lower()
            ctype_map = {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp','gif':'image/gif'}
            ctype = ctype_map.get(ext, 'text/plain; charset=utf-8')
            try:
                with open(fp, 'rb') as fh:
                    data = fh.read()
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(500)

        # ---- Open folder in Windows Explorer ----
        elif self.path.startswith('/api/open-folder'):
            params = self._qp()
            fp = params.get('path',[''])[0]
            if fp and os.path.exists(fp): subprocess.Popen(f'explorer.exe "{fp}"', shell=True)
            self._json_ok({"status": "opened"})

        # ---- Open file location ----
        elif self.path.startswith('/api/open-file-dir'):
            params = self._qp()
            fp = params.get('path',[''])[0]
            if fp and os.path.exists(fp): subprocess.Popen(f'explorer.exe /select,"{fp}"', shell=True)
            self._json_ok({"status": "opened"})

        # ---- Search ----
        elif self.path.startswith('/api/search'):
            params = self._qp()
            q = params.get('q',[''])[0]
            self._json_ok({"results": query_everything_search(q)})

        # ---- SDC Scan ----
        elif self.path.startswith('/api/sdc/scan'):
            params = self._qp()
            scan_path = params.get('path',[''])[0]
            if not scan_path or not os.path.isdir(scan_path):
                self._json_ok({"error": "Invalid directory path", "images": []}); return
            IMG_EXTS = {'.png','.jpg','.jpeg','.webp','.bmp','.gif'}
            images = []
            try:
                for f in sorted(os.listdir(scan_path)):
                    if os.path.splitext(f)[1].lower() in IMG_EXTS:
                        fp = os.path.join(scan_path, f)
                        try: size = round(os.path.getsize(fp) / (1024**2), 2)
                        except: size = 0
                        images.append({"name": f, "path": fp, "size": size})
            except Exception as e:
                self._json_ok({"error": str(e), "images": []}); return
            self._json_ok({"images": images})

        # ---- SDC Thumbnail (serve image) ----
        elif self.path.startswith('/api/sdc/thumb'):
            params = self._qp()
            fp = params.get('path',[''])[0]
            if not fp or not os.path.isfile(fp):
                self.send_error(404); return
            ext = fp.rsplit('.', 1)[-1].lower()
            ctype_map = {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp','gif':'image/gif','bmp':'image/bmp'}
            ctype = ctype_map.get(ext, 'image/jpeg')
            try:
                with open(fp, 'rb') as fh: data = fh.read()
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(500)

        # ---- Terminals: get logs ----
        elif self.path == '/api/terminals/logs':
            with _terminal_lock:
                streams = {k: list(v) for k, v in _terminal_logs.items()}
            self._json_ok({"streams": streams})

        # ---- Terminals: clear one ----
        elif self.path.startswith('/api/terminals/clear') and 'all' not in self.path:
            params = self._qp()
            key = params.get('key',[''])[0]
            with _terminal_lock:
                if key in _terminal_logs: _terminal_logs[key].clear()
            self._json_ok({"status": "cleared"})

        # ---- Terminals: clear all ----
        elif self.path == '/api/terminals/clear-all':
            with _terminal_lock: _terminal_logs.clear()
            self._json_ok({"status": "cleared"})

        # ---- Launch app ----
        elif self.path.startswith('/api/launch-kobold'):
            params = self._qp()
            model   = params.get('model',[''])[0]
            layers  = params.get('layers',['35'])[0]
            context = params.get('context',['4096'])[0]
            mp = os.path.join(LLM_DIR, model)
            cmd = f'start cmd /k "title KoboldCPP && "{KOBOLD_EXE}" --model "{mp}" --gpulayers {layers} --contextsize {context} --port 5001 --usecublas"'
            subprocess.Popen(cmd, shell=True)
            self._json_ok({"status": "launched"})

        elif self.path.startswith('/api/launch'):
            params = self._qp()
            key = params.get('app',[''])[0]
            if key in APPS:
                cmd = APPS[key]["launch_cmd"]
                if cmd: subprocess.Popen(cmd, shell=True)
            self._json_ok({"status": "launched"})

        elif self.path.startswith('/api/kill'):
            params = self._qp()
            key = params.get('app',[''])[0]
            if key in APPS:
                for name in APPS[key].get("process_names", []):
                    subprocess.Popen(f'taskkill /F /IM {name}', shell=True)
            self._json_ok({"status": "killed"})

        elif self.path.startswith('/api/killpid'):
            params = self._qp()
            pid = params.get('pid',[''])[0]
            if pid: subprocess.Popen(f'taskkill /F /PID {pid}', shell=True)
            self._json_ok({"status": "killed"})

        elif self.path == '/api/panic':
            for name in ["koboldcpp.exe","python.exe","ollama.exe","ollama_llama_server.exe"]:
                subprocess.Popen(f'taskkill /F /IM {name}', shell=True)
            self._json_ok({"status": "panicked"})

        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)

        # ---- Generate Prompt ----
        if self.path == '/api/generate-prompt':
            try:
                payload = json.loads(body)
                model   = payload.get('model','')
                prompt  = payload.get('prompt','')
                if not model or not prompt:
                    self._json_ok({"error": "Missing model or prompt"}); return

                raw = ollama_generate(model, prompt)

                positive = ""; negative = ""
                for line in raw.split('\n'):
                    l = line.strip()
                    if l.upper().startswith('POSITIVE:'):
                        positive = l[9:].strip()
                    elif l.upper().startswith('NEGATIVE:'):
                        negative = l[9:].strip()

                if not positive:
                    positive = raw.strip()

                self._json_ok({"positive": positive, "negative": negative, "raw": raw})
            except urllib.error.URLError:
                self._json_ok({"error": "Ollama is not running or unreachable on port 11434"})
            except Exception as e:
                self._json_ok({"error": str(e)})

        # ---- SDC VLM Tag ----
        elif self.path == '/api/sdc/tag-vlm':
            try:
                payload  = json.loads(body)
                fp       = payload.get('path','')
                model    = payload.get('model','')
                instr    = payload.get('instruction', 'Describe this image in detail for Stable Diffusion tags.')
                if not fp or not model or not os.path.isfile(fp):
                    self._json_ok({"error": "Invalid file or model"}); return

                # Read image and base64 encode for Ollama vision
                with open(fp, 'rb') as fh:
                    img_b64 = base64.b64encode(fh.read()).decode()

                vlm_payload = json.dumps({
                    "model": model,
                    "prompt": instr,
                    "images": [img_b64],
                    "stream": False
                }).encode()

                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/generate",
                    data=vlm_payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read().decode())
                    tags = result.get("response", "").strip()
                self._json_ok({"tags": tags})
            except urllib.error.URLError:
                self._json_ok({"error": "Ollama offline"})
            except Exception as e:
                self._json_ok({"error": str(e)})

        else:
            self.send_error(404)

    # ---- Helpers ----
    def _qp(self):
        from urllib.parse import urlparse, parse_qs
        return parse_qs(urlparse(self.path).query)

    def _json_ok(self, payload):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_ok_html(self, data, ctype):
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass  # Silent

# ============================================================
#  MAIN
# ============================================================
def main():
    server = HTTPServer(('localhost', PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    main()
