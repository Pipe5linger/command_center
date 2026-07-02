


from flask import Flask, request, jsonify, render_template, send_from_directory
import yt_dlp
import os
import sanctuary_command_center as scc
import psutil
import platform
import requests # Added for Ollama API calls
import subprocess # Added for opening folders
import glob # Added for explorer list
import time # Added for api_terminals_logs
import threading

# --- GPU Telemetry (NVML) ---
try:
    import pynvml
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False

app = Flask(__name__)

# ---------------------------------------------------------------------------
#  App Status Helper – detects KoboldCPP, Ollama, LM Studio via process+port
# ---------------------------------------------------------------------------
_APP_REGISTRY = {
    "koboldcpp": {"name": "KoboldCPP",  "exe": "koboldcpp.exe",  "port": 5001},
    "ollama":    {"name": "Ollama",     "exe": "ollama.exe",     "port": 11434},
    "lmstudio":  {"name": "LM Studio",  "exe": "LM Studio.exe", "port": 1234},
}

def get_app_statuses():
    """Check which AI backend apps are running by scanning process names
    and verifying their expected ports are listening."""
    # Phase 1 – collect running process names into a set for O(1) lookup
    running_exes = set()
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                running_exes.add(proc.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass

    # Phase 2 – collect listening ports
    listening_ports = set()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == "LISTEN" and conn.laddr:
                listening_ports.add(conn.laddr.port)
    except Exception:
        pass

    # Phase 3 – build status dict
    result = {}
    for key, cfg in _APP_REGISTRY.items():
        exe_running  = cfg["exe"] in running_exes
        port_listening = cfg["port"] in listening_ports
        result[key] = {
            "name":    cfg["name"],
            "port":    cfg["port"],
            "running": exe_running and port_listening,
        }
    return result

# ---------------------------------------------------------------------------
#  Drive Storage Helper – scans all fixed disk partitions
# ---------------------------------------------------------------------------
def get_drive_stats():
    """Return disk usage for every fixed drive on the system.
    Frontend expects: [{letter, used_gb, total_gb, pct}, ...]"""
    drives = []
    try:
        for part in psutil.disk_partitions():
            # Skip CD-ROM / removable / network unless they have a real mount
            if part.fstype == "":
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                # Extract just the drive letter (e.g. "C:" from "C:\")
                letter = part.device.rstrip("\\")
                drives.append({
                    "letter":   letter,
                    "used_gb":  round(usage.used / (1024**3), 1),
                    "total_gb": round(usage.total / (1024**3), 1),
                    "pct":      usage.percent,
                })
            except (PermissionError, OSError):
                continue
    except Exception:
        pass
    return drives

# ---------------------------------------------------------------------------
#  Top Processes Helper – top 10 by CPU + memory, for Resource Hog table
# ---------------------------------------------------------------------------
def get_top_processes(limit=10):
    procs = list()
    process_list = list(psutil.process_iter(["pid", "name", "memory_info"]))
    for proc in process_list:
        try: proc.cpu_percent()
        except: pass
    time.sleep(0.1)
    for proc in process_list:
        try:
            info = proc.info
            ram_mb = round(info["memory_info"].rss / (1024 * 1024), 1) if info["memory_info"] else 0
            cpu = round(proc.cpu_percent() or 0, 1)
            if cpu > 0 or ram_mb > 0:
                procs.append(dict(pid=info["pid"], name=info["name"], cpu=cpu, ram=ram_mb))
        except:
            continue
    procs.sort(key=lambda p: (p["cpu"], p["ram"]), reverse=True)
    return procs[:limit]


_NVML_INITIALIZED = False


def get_gpu_stats():
    """Query NVIDIA GPU via pynvml.  Returns a dict with keys the frontend
    expects: pct (VRAM %), vram_used (MB), vram_total (MB), temp (C), load (%).
    Includes an 'error' key explaining why telemetry is unavailable."""
    global _NVML_INITIALIZED

    if not _NVML_AVAILABLE:
        return {"pct": 0, "vram_used": 0, "vram_total": 0, "temp": 0, "load": 0,
                "error": "pynvml not installed — run: pip install nvidia-ml-py"}

    # Lazy-init NVML on first call
    if not _NVML_INITIALIZED:
        try:
            pynvml.nvmlInit()
            _NVML_INITIALIZED = True
        except Exception as e:
            return {"pct": 0, "vram_used": 0, "vram_total": 0, "temp": 0, "load": 0,
                    "error": f"NVML init failed: {e}"}

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_used_mb  = round(mem.used / (1024 * 1024), 1)
        vram_total_mb = round(mem.total / (1024 * 1024), 1)
        vram_pct      = round((mem.used / mem.total) * 100, 1) if mem.total > 0 else 0

        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_load = util.gpu  # percent

        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

        return {
            "pct":        vram_pct,
            "vram_used":  vram_used_mb,
            "vram_total": vram_total_mb,
            "temp":       temp,
            "load":       gpu_load,
        }
    except Exception as e:
        return {"pct": 0, "vram_used": 0, "vram_total": 0, "temp": 0, "load": 0,
                "error": f"GPU query failed: {e}"}

# ---------------------------------------------------------------------------
#  EXTRACTION — OpenCV frame extraction + perceptual hash deduplication
# ---------------------------------------------------------------------------

_extract_status = {
    "running": False,
    "paused":  False,
    "stopped": False,
    "progress": 0,
    "total_frames": 0,
    "saved": 0,
    "skipped": 0,
    "current_file": None,
    "output_folder": None,
    "error": None,
}
_extract_lock = threading.Lock()
_extract_thread = None


def _run_extraction(video_path, output_folder, frame_interval, dedup_threshold, enable_dedup):
    """Background thread: open video, extract frames, optionally deduplicate via pHash."""
    global _extract_status

    try:
        import cv2
        import imagehash
        from PIL import Image as _PILImage
    except ImportError as e:
        with _extract_lock:
            _extract_status["running"] = False
            _extract_status["error"] = f"Missing dependency: {e}"
        return

    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            with _extract_lock:
                _extract_status["error"] = f"Cannot open video: {video_path}"
                _extract_status["running"] = False
            return

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        with _extract_lock:
            _extract_status["total_frames"] = total

        os.makedirs(output_folder, exist_ok=True)

        if enable_dedup:
            try:
                last_hash = imagehash.phash(_PILImage.new("RGB", (1, 1)))
            except Exception:
                last_hash = None
        else:
            last_hash = None

        saved  = 0
        skipped = 0
        frame_idx = 0

        while True:
            with _extract_lock:
                if _extract_status["stopped"]:
                    break
                paused = _extract_status["paused"]

            if paused:
                time.sleep(0.2)
                continue

            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1

            if frame_idx % frame_interval != 0:
                continue

            with _extract_lock:
                _extract_status["progress"] = frame_idx

            if enable_dedup and last_hash is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = _PILImage.fromarray(rgb)
                try:
                    cur_hash = imagehash.phash(pil_img)
                except Exception:
                    cur_hash = None

                if cur_hash is not None and last_hash is not None:
                    diff = cur_hash - last_hash
                    if diff < dedup_threshold:
                        skipped += 1
                        with _extract_lock:
                            _extract_status["skipped"] = skipped
                        continue
                last_hash = cur_hash

            out_name = f"frame_{frame_idx:06d}.png"
            out_path = os.path.join(output_folder, out_name)
            cv2.imwrite(out_path, frame)
            saved += 1

            with _extract_lock:
                _extract_status["saved"]       = saved
                _extract_status["skipped"]      = skipped
                _extract_status["current_file"] = out_name

    except Exception as e:
        with _extract_lock:
            _extract_status["error"] = str(e)
    finally:
        if cap is not None:
            cap.release()
        with _extract_lock:
            _extract_status["running"] = False
            _extract_status["progress"] = _extract_status.get("total_frames", 0)


@app.route('/')
def index():
    # Set initial path to 'D:\AI\Projects' for the explorer
    explorer_initial_path = 'D:\\AI\\Projects'
    # Use double backslashes for JavaScript string literal in the template
    explorer_initial_path_js = explorer_initial_path.replace('\\', '\\\\')
    return render_template('index.html', explorer_initial_path=explorer_initial_path_js)

@app.route('/api/stats', methods=['GET'])
def api_stats():
    # Non-blocking CPU measurement: call once with interval=None to get
    # a reading since the last call, then sleep a tiny bit for accuracy.
    psutil.cpu_percent(interval=None)  # warm-up (first call returns 0)
    time.sleep(0.15)
    cpu_load = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    ram_pct = ram.percent
    ram_used_gb = round(ram.used / (1024**3), 2)
    ram_total_gb = round(ram.total / (1024**3), 2)

    gpu_stats = get_gpu_stats()
    
    app_statuses = get_app_statuses()

    stats = {
        "system": {
            "cpu_load": cpu_load,
            "ram_pct": ram_pct,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb
        },
        "gpu": gpu_stats,
        "apps": app_statuses,
        "drives": get_drive_stats(),
        "processes": get_top_processes(),
    }
    return jsonify(stats)


@app.route('/api/info', methods=['GET'])
def api_info():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing URL parameter"}), 400

    info = scc.get_video_info(url)
    if "error" in info:
        return jsonify(info), 500
    return jsonify(info)

@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.json
    if not data or not data.get('url') or not data.get('output_folder'):
        return jsonify({"error": "Missing URL or output_folder in request body"}), 400

    url = data['url']
    output_folder = data['output_folder']
    file_name = data.get('file_name')

    result = scc.download_video(url, output_folder, file_name)
    if not result['success']:
        return jsonify({'error': result['error']}), 500
    return jsonify({'message': result['message'], 'output_path': result['output_path']})

@app.route('/api/download_status', methods=['GET'])
def api_download_status():
    return jsonify(scc.get_download_status())

@app.route('/api/ollama/models', methods=['GET'])
def api_ollama_models():
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        response.raise_for_status()
        data = response.json()
        return jsonify(data)
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Ollama not running on port 11434", "models": []}), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Ollama request timed out", "models": []}), 503
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 500

# ---------------------------------------------------------------------------
#  PROMPT GENERATOR — prompt bank + Ollama streaming generation
# ---------------------------------------------------------------------------
import json as _json

_PROMPT_BANK_PATH = os.path.join(os.path.dirname(__file__), "static", "prompt_bank.json")

@app.route('/api/prompt-bank', methods=['GET'])
def api_prompt_bank():
    """Serve the master prompt word bank as JSON."""
    try:
        with open(_PROMPT_BANK_PATH, 'r', encoding='utf-8') as f:
            bank = _json.load(f)
        return jsonify(bank)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate-prompt', methods=['POST'])
def api_generate_prompt():
    """Stream a prompt generation response from Ollama's /api/generate endpoint.
    Expects JSON: {model, prompt, system (optional), stream (optional)}"""
    data = request.get_json(silent=True) or {}
    model  = data.get("model", "")
    prompt = data.get("prompt", "")
    system = data.get("system", "")
    stream = data.get("stream", True)

    if not model or not prompt:
        return jsonify({"error": "model and prompt are required"}), 400

    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": stream,
    }
    if system:
        payload["system"] = system

    def generate():
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                stream=True,
                timeout=(5, 120),
            )
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if line:
                    yield f"data: {line}\n\n"
        except requests.exceptions.ConnectionError:
            yield "data: {\"error\":\"Ollama is not running on port 11434\"}\n\n"
        except Exception as e:
            yield f"data: {{\"error\":\"{str(e)}\"}}\n\n"

    return app.response_class(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route('/api/folders', methods=['GET'])
def api_folders():
    # This should return a list of predefined shortcuts or recently accessed folders
    return jsonify({
        "folders": [
            {"name": "ComfyUI", "path": "D:\\\\AI\\\\Projects\\\\ComfyUI"},
            {"name": "LLM Models", "path": "D:\\\\AI\\\\Models\\\\LLM"},
            {"name": "Flux Training", "path": "D:\\\\AI\\\\Projects\\\\flux_training"}
        ]
    })

@app.route('/api/explorer/list', methods=['GET'])
def api_explorer_list():
    target_path = request.args.get('path', 'D:\\\\') # Default to D: drive
    if not os.path.isdir(target_path):
        return jsonify({"error": "Path not found or is not a directory"}), 404

    items = []
    for entry in os.scandir(target_path):
        try:
            is_dir = entry.is_dir()
            item = {
                "name": entry.name,
                "path": entry.path,
                "is_dir": is_dir,
                "size": round(entry.stat().st_size / (1024 * 1024), 2) if not is_dir else 0  # Size in MB
            }
            items.append(item)
        except Exception as e:
            # print(f"Error accessing {entry.path}: {e}") # For debugging
            continue
    return jsonify({"path": target_path, "items": items})

@app.route('/api/explorer/view', methods=['GET'])
def api_explorer_view():
    file_path = request.args.get('path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    # Serve image files directly
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
        return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))
    
    # For text-based files, read and return content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return jsonify({"error": f"Could not read file: {str(e)}"}), 500


@app.route('/api/open-folder', methods=['GET'])
def api_open_folder():
    folder_path = request.args.get('path')
    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({"error": "Folder not found or invalid path"}), 404
    try:
        # For Windows
        if platform.system() == "Windows":
            os.startfile(folder_path)
        # For macOS
        elif platform.system() == "Darwin":
            subprocess.Popen(['open', folder_path])
        # For Linux
        else:
            subprocess.Popen(['xdg-open', folder_path])
        return jsonify({"message": "Folder opened successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Could not open folder: {str(e)}"}), 500


@app.route('/api/open-file-dir', methods=['GET'])
def api_open_file_dir():
    """Open the parent directory of a file in Windows Explorer."""
    file_path = request.args.get('path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    try:
        parent_dir = os.path.dirname(file_path)
        if os.path.isdir(parent_dir):
            os.startfile(parent_dir)
            return jsonify({"message": "File directory opened"}), 200
        return jsonify({"error": "Parent directory not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Could not open directory: {str(e)}"}), 500

# ---------------------------------------------------------------------------
#  LAUNCHERS – scan D:\AI\Launchers for executable files
# ---------------------------------------------------------------------------
_LAUNCHERS_DIR = r"D:\AI\Launchers"
_LAUNCHER_EXTENSIONS = {".bat", ".exe", ".lnk", ".ps1", ".py", ".cmd", ".vbs"}

@app.route('/api/launchers', methods=['GET'])
def api_launchers():
    """Scan the launchers directory and return every launchable file."""
    launchers = []
    if os.path.isdir(_LAUNCHERS_DIR):
        try:
            for entry in sorted(os.scandir(_LAUNCHERS_DIR), key=lambda e: e.name.lower()):
                if entry.is_file():
                    _, ext = os.path.splitext(entry.name)
                    if ext.lower() in _LAUNCHER_EXTENSIONS:
                        launchers.append({
                            "name":     entry.name,
                            "filename": entry.name,
                        })
        except Exception:
            pass
    return jsonify({"launchers": launchers})


@app.route('/api/launch-file', methods=['GET'])
def api_launch_file():
    """Launch a file from the launchers directory."""
    filename = request.args.get('file')
    if not filename:
        return jsonify({"error": "Missing file parameter"}), 400
    filepath = os.path.join(_LAUNCHERS_DIR, filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found in launchers directory"}), 404
    try:
        os.startfile(filepath)
        return jsonify({"message": f"Launched {filename}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/open-launchers-folder', methods=['GET'])
def api_open_launchers_folder():
    """Open the launchers directory in Windows Explorer."""
    if os.path.isdir(_LAUNCHERS_DIR):
        try:
            os.startfile(_LAUNCHERS_DIR)
            return jsonify({"message": "Launchers folder opened"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Launchers directory not found"}), 404


# In-memory terminal log buffers — each key is a process name, value is a list of lines.
_terminal_buffers = {}
_terminal_max_lines = 500
@app.route('/api/terminals/clear', methods=['GET'])
def api_terminals_clear():
    """Clear the log buffer for a specific process key."""
    key = request.args.get('key', '')
    if key in _terminal_buffers:
        del _terminal_buffers[key]
    return jsonify({"message": "Cleared logs for " + key})


@app.route('/api/terminals/clear-all', methods=['GET'])
def api_terminals_clear_all():
    """Clear all terminal log buffers."""
    _terminal_buffers.clear()
    return jsonify({"message": "All terminal logs cleared"})
@app.route('/api/terminals/logs', methods=['GET'])
def api_terminals_logs():
    log_file_path = "scc_server.log" # Assume scc_server.log is in the same directory
    if not os.path.exists(log_file_path):
        return jsonify(dict(streams=_terminal_buffers))

    def generate():
        with open(log_file_path, 'r') as f:
            # Seek to the end of the file
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line: 
                    time.sleep(0.5) # Wait a bit then try again
                    continue
                yield line
    return app.response_class(generate(), mimetype='text/plain')


# ---------------------------------------------------------------------------
#  APP LAUNCHERS – start/kill KoboldCPP, Ollama, LM Studio
# ---------------------------------------------------------------------------
_APP_LAUNCH_CFG = {
    "koboldcpp": {
        "exe":      r"D:\AI\Projects\KoboldCpp\koboldcpp.exe",
        "proc":     "koboldcpp.exe",
        "name":     "KoboldCPP",
    },
    "ollama": {
        "cmd":      ["ollama", "serve"],
        "proc":     "ollama.exe",
        "name":     "Ollama",
    },
    "lmstudio": {
        "exe":      r"C:\Users\boben\AppData\Local\Programs\LM Studio\LM Studio.exe",
        "proc":     "LM Studio.exe",
        "name":     "LM Studio",
    },
}


@app.route('/api/launch', methods=['GET'])
def api_launch():
    """Launch an AI backend app (koboldcpp / ollama / lmstudio)."""
    key = request.args.get('app')
    if not key or key not in _APP_LAUNCH_CFG:
        return jsonify({"error": f"Unknown app: {key}"}), 400

    cfg = _APP_LAUNCH_CFG[key]

    # Already running? Skip duplicate launch
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] == cfg["proc"]:
                return jsonify({"message": f"{cfg['name']} is already running."}), 200
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    try:
        if "cmd" in cfg:
            # Ollama runs as a background server — no console needed
            subprocess.Popen(cfg["cmd"], creationflags=subprocess.DETACHED_PROCESS)
        else:
            # KoboldCPP & LM Studio — open in a visible window so user can monitor
            subprocess.Popen([cfg["exe"]], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return jsonify({"message": f"Launched {cfg['name']}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/kill', methods=['GET'])
def api_kill():
    """Kill an AI backend app by process name."""
    key = request.args.get('app')
    if not key or key not in _APP_LAUNCH_CFG:
        return jsonify({"error": f"Unknown app: {key}"}), 400

    cfg = _APP_LAUNCH_CFG[key]
    killed = 0
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] == cfg["proc"]:
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return jsonify({"message": f"Killed {killed} instance(s) of {cfg['name']}"}), 200


@app.route('/api/killpid', methods=['GET'])
def api_killpid():
    """Kill a process by PID."""
    pid_str = request.args.get('pid')
    if not pid_str:
        return jsonify({"error": "Missing pid parameter"}), 400
    try:
        pid = int(pid_str)
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        return jsonify({"message": f"Killed PID {pid} ({name})"}), 200
    except psutil.NoSuchProcess:
        return jsonify({"error": f"PID {pid_str} not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/launch-kobold', methods=['GET'])
def api_launch_kobold():
    """Launch KoboldCPP with a specific GGUF model, GPU layers, and context size."""
    model   = request.args.get('model',   '')
    layers  = request.args.get('layers',  '99')
    context = request.args.get('context', '32768')

    if not model:
        return jsonify({"error": "Missing model parameter"}), 400

    # Resolve model path — support full path or filename in D:\AI\Models\LLM
    model_path = model
    if not os.path.isabs(model_path):
        candidate = os.path.join(r"D:\AI\Models\LLM", model)
        if os.path.isfile(candidate):
            model_path = candidate
        else:
            return jsonify({"error": f"Model not found: {model}"}), 404

    kobold_exe = r"D:\AI\Projects\KoboldCpp\koboldcpp.exe"
    if not os.path.isfile(kobold_exe):
        return jsonify({"error": "koboldcpp.exe not found"}), 500

    try:
        cmd = [
            kobold_exe,
            "--model",        model_path,
            "--gpulayers",    layers,
            "--contextsize",  context,
            "--usecublas",
            "--highpriority",
            "--port",         "5001",
            "--host",         "127.0.0.1",
        ]
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return jsonify({
            "message": f"KoboldCPP launched with {os.path.basename(model_path)}",
            "command": " ".join(cmd),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
#  GGUF MODEL LISTING — scan D:\AI\Models\LLM for .gguf files
# ---------------------------------------------------------------------------
_GGUF_DIR = r"D:\AI\Models\LLM"


@app.route('/api/models', methods=['GET'])
def api_models():
    """Return every .gguf file found in the LLM models directory."""
    models = []
    if os.path.isdir(_GGUF_DIR):
        try:
            for entry in sorted(os.scandir(_GGUF_DIR), key=lambda e: e.name.lower()):
                if entry.is_file() and entry.name.lower().endswith(".gguf"):
                    models.append(entry.name)
        except Exception:
            pass
    return jsonify({"models": models})


# ---------------------------------------------------------------------------
#  PANIC BUTTON — kill all AI backends at once
# ---------------------------------------------------------------------------


@app.route('/api/panic', methods=['GET'])
def api_panic():
    """Kill every known AI backend process — KoboldCPP, Ollama, LM Studio."""
    targets = ["koboldcpp.exe", "ollama.exe", "LM Studio.exe"]
    killed = {}
    for exe in targets:
        killed[exe] = 0
        try:
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    if proc.info["name"] == exe:
                        proc.kill()
                        killed[exe] += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
    total = sum(killed.values())
    return jsonify({"message": f"Terminated {total} AI process(es)", "killed": killed}), 200


# ---------------------------------------------------------------------------
#  SEARCH — recursive filename search across D:\AI
# ---------------------------------------------------------------------------
_SEARCH_ROOTS = [r"D:\AI", r"D:\AI\Projects", r"D:\AI\Models"]
_SEARCH_MAX_RESULTS = 100
_SEARCH_MAX_DEPTH = 4


@app.route('/api/search', methods=['GET'])
def api_search():
    """Recursive filename search under configured roots.
    Returns [{name, size, path}, ...] limited to _SEARCH_MAX_RESULTS."""
    query = request.args.get('q', '').strip().lower()
    if not query or len(query) < 2:
        return jsonify({"results": []})

    results = []
    for root in _SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                depth = dirpath.replace(root, "").count(os.sep)
                if depth > _SEARCH_MAX_DEPTH:
                    _dirnames.clear()
                    continue
                for name in filenames:
                    if query in name.lower():
                        fp = os.path.join(dirpath, name)
                        try:
                            size_mb = round(os.path.getsize(fp) / (1024 * 1024), 2)
                        except OSError:
                            size_mb = 0
                        results.append({
                            "name": name,
                            "size": f"{size_mb} MB" if size_mb >= 1 else f"{round(size_mb * 1024)} KB",
                            "path": fp,
                        })
                        if len(results) >= _SEARCH_MAX_RESULTS:
                            break
                if len(results) >= _SEARCH_MAX_RESULTS:
                    break
        except Exception:
            continue
        if len(results) >= _SEARCH_MAX_RESULTS:
            break

    return jsonify({"results": results})


# ---------------------------------------------------------------------------
#  SDC — DATASET CURATOR (image scanning, thumbnails, VLM tagging)
# ---------------------------------------------------------------------------
_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
_THUMB_SIZE = (320, 240)

# Lazy-import PIL so the server still boots without it
_PIL_AVAILABLE = False
try:
    from PIL import Image as _PILImage
    import io as _io
    _PIL_AVAILABLE = True
except Exception:
    pass


@app.route('/api/sdc/scan', methods=['GET'])
def api_sdc_scan():
    """Scan a directory recursively for image files.
    Returns {images: [{name, path}, ...]}."""
    path = request.args.get('path', '').strip()
    if not path or not os.path.isdir(path):
        return jsonify({"error": "Invalid or missing directory path"}), 400

    images = []
    try:
        for entry in sorted(os.scandir(path), key=lambda e: e.name.lower()):
            if not entry.is_file():
                continue
            _, ext = os.path.splitext(entry.name)
            if ext.lower() in _IMAGE_EXTENSIONS:
                images.append({"name": entry.name, "path": entry.path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"images": images})


@app.route('/api/sdc/thumb', methods=['GET'])
def api_sdc_thumb():
    """Serve a thumbnail of the image at the given path.
    Uses PIL if available; otherwise falls back to serving the full file."""
    img_path = request.args.get('path', '').strip()
    if not img_path or not os.path.isfile(img_path):
        return jsonify({"error": "File not found"}), 404

    if _PIL_AVAILABLE:
        try:
            im = _PILImage.open(img_path)
            im.thumbnail(_THUMB_SIZE)
            buf = _io.BytesIO()
            fmt = im.format or "JPEG"
            if fmt.upper() == "GIF":
                fmt = "PNG"
            im.save(buf, format=fmt)
            buf.seek(0)
            return app.response_class(buf.read(), mimetype=f"image/{fmt.lower()}")
        except Exception:
            pass  # fall through to raw serve

    # Fallback: serve the file directly
    return send_from_directory(
        os.path.dirname(img_path),
        os.path.basename(img_path),
    )


@app.route('/api/sdc/tag-vlm', methods=['POST'])
def api_sdc_tag_vlm():
    """Tag an image using an Ollama vision model.
    Expects JSON: {path, model, instruction}
    Returns {tags: "..."}"""
    data = request.get_json(silent=True) or {}
    img_path    = data.get("path", "")
    model       = data.get("model", "")
    instruction = data.get("instruction", "Describe this image in detail.")

    if not img_path or not os.path.isfile(img_path):
        return jsonify({"error": "Image file not found"}), 404
    if not model:
        return jsonify({"error": "model is required"}), 400

    # Read & base64-encode the image
    try:
        with open(img_path, "rb") as f:
            img_bytes = f.read()
    except Exception as e:
        return jsonify({"error": f"Cannot read image: {e}"}), 500

    import base64
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    payload = {
        "model":  model,
        "prompt": instruction,
        "images": [img_b64],
        "stream": False,
    }

    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=(10, 120),
        )
        resp.raise_for_status()
        result = resp.json()
        tags = result.get("response", "").strip()
        return jsonify({"tags": tags})
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Ollama is not running on port 11434"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/extract', methods=['POST'])
def api_extract():
    """Start frame extraction from a video file.
    JSON body: {path, output_folder?, frame_interval?, dedup_threshold?, enable_dedup?}"""
    global _extract_thread

    with _extract_lock:
        if _extract_status["running"]:
            return jsonify({"error": "Extraction already in progress"}), 409

    data = request.get_json(silent=True) or {}
    video_path      = data.get("path", "").strip()
    output_folder   = data.get("output_folder", "").strip()
    frame_interval  = int(data.get("frame_interval", 30))
    dedup_threshold = int(data.get("dedup_threshold", 12))
    enable_dedup    = data.get("enable_dedup", True)

    if not video_path or not os.path.isfile(video_path):
        return jsonify({"error": "Video file not found: " + video_path}), 404

    if not output_folder:
        base, _ = os.path.splitext(video_path)
        output_folder = base + "_frames"

    with _extract_lock:
        _extract_status.update({
            "running": True, "paused": False, "stopped": False,
            "progress": 0, "total_frames": 0, "saved": 0, "skipped": 0,
            "current_file": None, "output_folder": output_folder, "error": None,
        })

    _extract_thread = threading.Thread(
        target=_run_extraction,
        args=(video_path, output_folder, frame_interval, dedup_threshold, enable_dedup),
        daemon=True,
    )
    _extract_thread.start()

    return jsonify({
        "message": "Extraction started",
        "output_folder": output_folder,
        "frame_interval": frame_interval,
        "dedup_threshold": dedup_threshold,
        "enable_dedup": enable_dedup,
    }), 202


@app.route('/api/extract-status', methods=['GET'])
def api_extract_status():
    """Return the current extraction telemetry."""
    with _extract_lock:
        status = dict(_extract_status)
    return jsonify(status)


@app.route('/api/extract-stop', methods=['POST'])
def api_extract_stop():
    """Stop a running extraction."""
    with _extract_lock:
        if not _extract_status["running"]:
            return jsonify({"error": "No extraction running"}), 409
        _extract_status["stopped"] = True
    return jsonify({"message": "Stop signal sent"}), 200


@app.route('/api/extract-pause', methods=['POST'])
def api_extract_pause():
    """Toggle pause on a running extraction."""
    with _extract_lock:
        if not _extract_status["running"]:
            return jsonify({"error": "No extraction running"}), 409
        _extract_status["paused"] = not _extract_status["paused"]
        new_state = "paused" if _extract_status["paused"] else "resumed"
    return jsonify({"message": f"Extraction {new_state}"}), 200
if __name__ == '__main__':
    app.run(debug=False, port=9999)

