# Sanctuary Command Center (SCC) - Progress Checkpoint

## Project Overview
Integration of the Sanctuary Video Downloader & Clipper (SVD) and the Sanctuary Dataset Curator (SDC) into a unified Command Center dashboard.

## Current Status: Backend Launch & LLM Configuration
**Status:** 🟢 Operational (Launch/Kill routes live, LLM library curated)

---

## 📅 Session: 2026-07-02 — LLM Audit, Cleanup & Server Launch Fix

### ✅ LLM Library Audit & Cleanup
- [x] Scanned `D:\AI\Models\LLM\` — cataloged all 22 GGUF models with sizes & quantizations
- [x] Cross-referenced models against RTX 4070 (12GB VRAM) limits
- [x] **Deleted 9 waste/oversized models — 100.43 GB reclaimed:**
    - 4 redundant base models (fine-tuned Vespera versions exist)
    - 1 lower-quant duplicate (Q4 vs Q6)
    - 1 older version of same model (V1 vs V2)
    - 3 models too large for 12GB VRAM (2× 26B + 1× 30B = 48+ GB)
- [x] **13 curated models remain** — all fit 100% in 12GB VRAM with `--gpulayers 99`

### ✅ Ollama Modelfiles — All 13 Models
- [x] Created `D:\AI\Models\LLM\Ollama_Modelfiles\` with per-model configs:
    - Correct chat templates per architecture (ChatML, Llama 3, Mistral, Gemma, DeepSeek)
    - Optimized parameters (temperature, context size, stop tokens)
    - `setup_ollama.bat` — one-click batch registration (`ollama create`)
    - S-Tier models: qwen2.5-coder-vespera, deepseek-r1-vespera, qwen-coder-14b

### ✅ LM Studio Configuration
- [x] `setup_lmstudio.bat` — symlinks/copies models into `%USERPROFILE%\.cache\lm-studio\models\`
- [x] Fallback: documented how to point LM Studio directly at `D:\AI\Models\LLM`

### ✅ KoboldCPP Launcher
- [x] `setup_koboldcpp.bat` — numbered menu launcher for all 13 models
- [x] All models use `--gpulayers 99 --usecublas --highpriority`
- [x] Context sizes: 32K for 14B models, 8K for smaller/specialized ones

### ✅ Backend API Routes Added (app.py)
- [x] **`GET /api/launch?app=koboldcpp|ollama|lmstudio`** — Launches exe via subprocess
    - KoboldCPP & LM Studio: `CREATE_NEW_CONSOLE` (visible window)
    - Ollama: `DETACHED_PROCESS` (background server)
    - Duplicate detection: skips if process already running
- [x] **`GET /api/kill?app=koboldcpp|ollama|lmstudio`** — Kills process by name
- [x] **`GET /api/killpid?pid=<id>`** — Kills any process by PID
- [x] **`GET /api/launch-kobold?model=&layers=&context=`** — Full KoboldCPP launch with:
    - GGUF model from `D:\AI\Models\LLM\` (filename or absolute path)
    - GPU layers, context size, cuBLAS, high priority, port 5001
- [x] All 4 routes tested and verified (5/5 functional tests passed)

### ✅ Critical Bug Fix: VBS Launcher
- [x] **`START_COMMAND_CENTER.vbs` was launching `sanctuary_command_center.py`** — a 109-line yt-dlp helper with zero Flask code. Server never started.
- [x] Fixed to launch `app.py` via `pythonw.exe`
- [x] Duplicate-detection check updated from `sanctuary_command_center.py` → `app.py`
- [x] Verified: server boots, homepage loads (75K chars), all routes respond

### ✅ GPU Telemetry (Previously Placeholder)
- [x] `pynvml` integration implemented in `app.py` (was already done, confirmed working)
- [x] `/api/stats` returns live GPU usage, VRAM, and temperature

### ✅ App Status Detection
- [x] Process + port scanning for KoboldCPP, Ollama, and LM Studio
- [x] Frontend shows ONLINE/OFFLINE badges with Launch/Kill buttons
- [x] `/api/stats` includes `apps` dict with per-app running status

---

## 📁 File Inventory — Key Configs Created

| Path | Purpose |
|------|---------|
| `D:\AI\Models\LLM\Ollama_Modelfiles\*.Modelfile` | 13 Ollama model configs |
| `D:\AI\Models\LLM\Ollama_Modelfiles\setup_ollama.bat` | Batch register all models |
| `D:\AI\Models\LLM\Ollama_Modelfiles\setup_lmstudio.bat` | Symlink into LM Studio |
| `D:\AI\Models\LLM\Ollama_Modelfiles\setup_koboldcpp.bat` | One-click Kobold launcher |
| `D:\AI\Models\LLM\Ollama_Modelfiles\README.md` | Full LLM library docs |

---

## 📊 Surviving Model Library (13 models, RTX 4070-compatible)

| Tier | Model | Size | Architecture |
|------|-------|------|-------------|
| S+ | qwen2.5-coder-14b-32k-Vespera (daily driver) | 8.37 GB | Qwen 2.5 / ChatML |
| S | deepseek-r1-14b-32k-Vespera (reasoning) | 8.37 GB | DeepSeek-R1 |
| S | qwen-coder-14b-16k (coding, shorter ctx) | 8.37 GB | Qwen 2.5 / ChatML |
| A | Mistral-Nemo-Instruct-2407-Q5_K_M | 8.13 GB | Mistral Nemo |
| A | Gemma4-12B-QAT-Uncensored | 6.87 GB | Gemma 4 |
| A | Vespera-original | 7.54 GB | Qwen / ChatML |
| B | Llama-3.1-8B-Lexi-Uncensored-V2-Q6_K | 6.14 GB | Llama 3.1 |
| B | Qwythos-9B-Claude-Mythos-5-Q6_K | 7.09 GB | Qwen 2.5 / ChatML |
| B | ornith-1.0-9b-Q6_K | 6.85 GB | Mistral |
| B | llava-latest (vision) | 3.83 GB | LLaVA |
| C | llama3-latest (fast 8B) | 4.34 GB | Llama 3 |
| C | nsfw-prompt-generator-latest | 7.54 GB | Various / ChatML |
| U | nomic-embed-text-latest (embeddings/RAG) | 0.26 GB | Nomic |

---

## ⏳ Remaining / Next Up
- [ ] **Video Harvester APIs**
    - `GET /api/info` (yt-dlp format inspection)
    - `POST /api/download` (background download with timestamping)
- [ ] **Extraction & Staging APIs**
    - `POST /api/extract` (OpenCV frame extraction + imagehash deduplication)
    - `GET /api/extract-status` (Telemetry for progress bars)
- [ ] **Frontend UI Consolidation**
    - Implement "Sub-Studio" Layout (Ingest / Stage / Curate tabs)
    - Real-time Telemetry & Log Streamers (beyond basic streaming)
- [ ] **Ollama/LM Studio integration testing** — run `setup_ollama.bat` and verify `ollama list`

---

**Last Updated:** 2026-07-02 — Vespera Session (LLM Audit + Backend Routes + VBS Fix)
