# BOOTSTRAP — Agent Context Resume

> **For the next AI agent:** Read this first. Everything you need to continue the Command Center project without re-auditing the codebase.

---

## 1. PROJECT SUMMARY

**Sanctuary Command Center (SCC)** — Flask dashboard at `http://localhost:9999`. Single-page web UI for AI workstation management.

**What it does:** System monitoring (CPU/RAM/GPU via pynvml), AI backend management (KoboldCPP, Ollama, LM Studio — launch/kill from dashboard), GGUF model launcher, video harvester (yt-dlp), file explorer, Ollama model listing, NSFW prompt generator, log streaming.

**Stack:** Python 3.11, Flask, psutil, pynvml, yt-dlp. Vanilla JS frontend (no framework).

---

## 2. KEY FILES

| File | Role |
|------|------|
| `app.py` | **Main Flask server.** All routes live here. Run this. |
| `templates/index.html` | **Served frontend** (Flask `render_template`). 1343 lines. |
| `static/css/` | Stylesheets |
| `static/prompt_bank.json` | NSFW prompt library |
| `static/prompt_gen_ui.js` | Prompt generator UI logic |
| `sanctuary_command_center.py` | yt-dlp helper functions (imported by app.py). 109 lines. |
| `START_COMMAND_CENTER.bat` | User launcher → calls `.vbs` |
| `START_COMMAND_CENTER.vbs` | **Silent launcher** — runs `pythonw.exe app.py` |
| `status_checkpoint.md` | Project history & task checklist |
| `BOOTSTRAP.md` | **This file** — agent handoff doc |

---

## 3. HOW TO START / RESTART

```powershell
# Manual start (for debugging — visible console):
python D:\AI\Projects\command_center\app.py

# Silent start (for normal use):
pythonw.exe D:\AI\Projects\command_center\app.py

# User-facing launcher:
D:\AI\Projects\command_center\START_COMMAND_CENTER.bat
```

**Open:** `http://localhost:9999`  
**Kill:** `taskkill /f /im python.exe` or `taskkill /f /im pythonw.exe`

---

## 4. WHAT WAS JUST ACCOMPLISHED (2026-07-02)

### LLM Library Curated
- Audited 22 GGUF models. Deleted 9 (redundant bases, lower quants, models >12GB VRAM).
- **100.43 GB freed.** 13 models remain — all fit in VRAM with `--gpulayers 99`.

### Ollama, LM Studio, KoboldCPP Configs
- `D:\AI\Models\LLM\Ollama_Modelfiles\` — 13 Modelfiles + 3 batch scripts + README
- `setup_ollama.bat` — `ollama create` for all 13 models
- `setup_lmstudio.bat` — symlinks into LM Studio cache
- `setup_koboldcpp.bat` — numbered menu launcher for all 13 models

### Backend Routes Added to app.py
- `GET /api/launch?app=koboldcpp|ollama|lmstudio` — launches exe (duplicate-safe)
- `GET /api/kill?app=koboldcpp|ollama|lmstudio` — kills by process name
- `GET /api/killpid?pid=<id>` — kills by PID
- `GET /api/launch-kobold?model=<file>&layers=99&context=32768` — model-specific Kobold launch
- All 4 routes tested, all respond correctly.

---

## 5. KEY PATHS & CONSTANTS (HARDCODED IN app.py)

| Constant | Value | Where Used |
|----------|-------|-----------|
| KoboldCPP exe | `D:\AI\Projects\KoboldCpp\koboldcpp.exe` | Launch/kill routes |
| LM Studio exe | `C:\Users\boben\AppData\Local\Programs\LM Studio\LM Studio.exe` | Launch/kill routes |
| Ollama cmd | `ollama serve` (system PATH) | Launch/kill routes |
| GGUF models dir | `D:\AI\Models\LLM` | `/api/models`, `/api/launch-kobold` |
| Launchers dir | `D:\AI\Launchers` | `/api/launchers`, `/api/launch-file` |
| Server port | `9999` | Hardcoded in `app.run()` |
| KoboldCPP port | `5001` | `/api/launch-kobold`, `_APP_REGISTRY` |

---

## 6. APP REGISTRY (PORT/PROCESS DETECTION)

```python
_APP_REGISTRY = {
    "koboldcpp": {"name": "KoboldCPP",  "exe": "koboldcpp.exe",  "port": 5001},
    "ollama":    {"name": "Ollama",     "exe": "ollama.exe",     "port": 11434},
    "lmstudio":  {"name": "LM Studio",  "exe": "LM Studio.exe", "port": 1234},
}
```

App status is detected by scanning running processes + listening ports. Frontend polls `/api/stats` every 3 seconds — `d.apps` dict has per-app running status. ONLINE/OFFLINE badges with Launch/Kill buttons.

---

## 7. GPU / VRAM CONTEXT

- **GPU:** RTX 4070, 12 GB VRAM
- **pynvml** for GPU telemetry (`/api/stats` returns live usage, VRAM, temp)
- All 13 surviving models fit entirely in VRAM with `--gpulayers 99`
- KV cache note: 32K context on 14B models uses ~3-4 GB extra VRAM

---

## 8. FRONTEND TABS

Dashboard tabs (defined in `templates/index.html`):
- **Home** — System stats, drive usage, process table, app status cards
- **AI Matrix** — KoboldCPP launcher (model select, GPU layers, context), Ollama model list
- **Harvester** — yt-dlp URL input, video info, download controls
- **Terminals** — Log streaming
- **Prompt Gen** — NSFW prompt generator with Ollama
- **Curator** — Dataset curator UI (SDC integration)
- **Explorer** — File browser
- **Search** — File search
- **Launchers** — Quick-launch shortcuts from `D:\AI\Launchers`

---

## 9. REMAINING TASKS (PRIORITY ORDER)

### High Priority
- [ ] **Test Ollama integration** — run `setup_ollama.bat`, verify `ollama list`
- [ ] **Test LM Studio integration** — run `setup_lmstudio.bat`, verify in LM Studio UI

### Medium Priority
- [ ] **Video Harvester APIs** — yt-dlp info + background download (routes in sanctuary_command_center.py)
- [ ] **Download progress UI** — frontend polling for download status

### Low Priority
- [ ] Extraction & Staging APIs (OpenCV frame extraction + imagehash dedup)
- [ ] Frontend UI consolidation (Sub-Studio layout)
- [ ] Real-time log streaming improvements

---

## 10. KNOWN QUIRKS & GOTCHAS

- **PowerShell quoting:** NEVER use complex quoting in terminal. Write `.py` temp scripts and run them.
- **CMD `&` in PowerShell:** `cmd /c ... & ...` creates background jobs. Use `;` or Python scripts.
- **The root `index.html`:** Completely corrupted (garbage CSS). Ignore it. Real one is `templates/index.html`.
- **`sanctuary_command_center.py`:** Only yt-dlp helpers, NOT an entry point. Do NOT use as launcher.
- **Encoding:** Some files have emoji (checkmark, green circle). Open with UTF-8, not CP1252.
- **Port 9999 conflict:** Check with `netstat -ano | findstr :9999` before starting.

---

## 11. QUICK START FOR NEXT AGENT

```bash
# 1. Verify server not already running
netstat -ano | findstr :9999

# 2. Start the server
python D:\AI\Projects\command_center\app.py

# 3. Open dashboard
# http://localhost:9999

# 4. Quick API tests
curl http://localhost:9999/api/stats
curl http://localhost:9999/api/launch?app=koboldcpp
curl http://localhost:9999/api/kill?app=koboldcpp
```

---

**Bootstrap written:** 2026-07-02  
**For agent model:** Any  
**Context freshness:** Full project state captured above


### Critical Bug Fixed
- `START_COMMAND_CENTER.vbs` was launching `sanctuary_command_center.py` (no Flask code). Server never booted.
- Fixed: now launches `app.py` via `pythonw.exe`.