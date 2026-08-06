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

## 📅 Session: 2026-07-02 — SDC Routes, Search, Panic & GGUF Listing (Cline)

### ✅ 6 Missing Backend Routes Implemented
- [x] **`GET /api/models`** — Scans `D:\AI\Models\LLM` for .gguf files, returns `{models: [...]}`
    - Frontend AI Matrix tab now populates GGUF model dropdown (was failing silently)
- [x] **`GET /api/panic`** — Kills all known AI backend processes (KoboldCPP, Ollama, LM Studio)
- [x] **`GET /api/search?q=`** — Recursive filename search under `D:\AI\`, max depth 4, 100 results
    - Returns `{results: [{name, size, path}, ...]}`
- [x] **`GET /api/sdc/scan?path=`** — Scans directory for image files (png/jpg/gif/bmp/webp/tiff)
    - Returns `{images: [{name, path}, ...]}`
- [x] **`GET /api/sdc/thumb?path=`** — On-the-fly thumbnail generation via PIL; raw fallback without PIL
- [x] **`POST /api/sdc/tag-vlm`** — Sends image (base64) to Ollama vision model for auto-tagging
    - Returns `{tags: "..."}` or 503 if Ollama is offline

### 🔍 Gap Analysis Against Frontend
- **7 routes were referenced in `index.html` but absent from `app.py`** — 6 now fixed.
- **`POST /api/extract` & `GET /api/extract-status`** are the only remaining missing routes (OpenCV frame extraction).

### 📊 Updated Route Count: 26 total (20 original + 6 new)

### 📝 Docs Correction
- Video Harvester APIs (`/api/info`, `/api/download`, `/api/download_status`) were already implemented and functional. Previously misreported as "remaining."

---

## ⏳ Remaining / Next Up
- [x] **Extraction & Staging APIs** -- DONE
    - `POST /api/extract` (OpenCV frame extraction + pHash dedup via imagehash)
    - `GET /api/extract-status` (Poll: running/progress/total/saved/skipped)
    - `POST /api/extract-stop` (Graceful stop signal)
    - `POST /api/extract-pause` (Toggle pause/resume)
    - Live-tested: 239-frame video, 2 unique frames saved, 5 duplicates auto-skipped
- [x] **Ollama integration testing** -- All 13 models registered. `setup_ollama.bat` was already run 4-5h ago. `ollama list` verified all models active.
- [x] **Cleanup** -- Removed scratch/ (63 temp files), prompt_gen_ui.js duplicate, corrupted root index.html, stale logs & temp scripts. 75 files purged total.
- [ ] **LM Studio integration testing** -- run `setup_lmstudio.bat`, verify in LM Studio UI (lower priority)

---

**Last Updated:** 2026-07-02 -- Cline Session (Cyberpunk UI Applied)

---

## 📅 Session: 2026-07-02 -- Cyberpunk UI Redesign Applied

### ✅ Cyberpunk Theme Applied to `templates/index.html`
- [x] Celadon accent color (#2DD4BF) -- primary accent replacing purple
- [x] CRT scanlines via `body::after` pseudo-element
- [x] Glassmorphism panels -- `blur(16px) saturate(140%)`, hover glow + top light bar
- [x] Stat cards -- celadon radial gradient hover, glow box-shadow
- [x] Header -- deeper blur (`28px`), saturate boost, celadon border-bottom shadow
- [x] SCC badge -- `@keyframes badgePulse` animated celadon glow
- [x] Progress bars -- `@keyframes shimmer` sweeping highlight animation
- [x] Scrollbar -- celadon tint
- [x] Tabs -- celadon active glow, inner shadow, text-shadow hover
- [x] Background -- deeper void (#060810), layered radial + repeating gradients

### 💡 Note
The scratch/ directory (63 cyberpunk UI generator scripts) was deleted in cleanup.
This cyberpunk application was built fresh against the plan + design references.

---

**Final Route Count:** 30 | **Final File Count:** ~30 core files | **app.py:** 983 lines

---

## 📅 Session: 2026-07-02 — Bootstrap Refresh & Context Sync (Session E)

### ✅ BOOTSTRAP.md Rebuilt From Scratch
- [x] Old `BOOTSTRAP.md` was stale (pre-cyberpunk, pre-extraction APIs, listed only ~12 routes).
- [x] **Full rebuild** with current project state:
    - Complete **30-route inventory** (categorized: Core, AI Backends, Harvester, Explorer, Launchers, Prompt Gen, Terminals, SDC, Extraction).
    - Updated key files table (added `register_ollama_models.py`, `implementation_plan.md`, `ui-redesign-plan.md`, `test_api_info.py`, `_design_references/`).
    - Documented cyberpunk theme (celadon accent, CRT scanlines, glassmorphism, fonts).
    - Full LLM library table (13 curated models with quants & architectures).
    - Session-by-session accomplishment log (Sessions A–E).
    - Updated remaining tasks (LM Studio testing only medium-priority item left).
    - Expanded gotchas (deleted files noted, IDE terminal quirks).

### ✅ status_checkpoint.md Updated
- [x] This entry appended documenting the bootstrap refresh.

### 📊 Current State Snapshot
| Metric | Value |
|--------|-------|
| Total routes | 30 |
| `app.py` lines | 983 |
| Core files | ~30 |
| GGUF models (curated) | 13 |
| Disk reclaimed (LLM cleanup) | 100.43 GB |
| Frontend theme | Cyberpunk (celadon) |
| Backend launchers | KoboldCPP, Ollama, LM Studio |
| Extraction engine | OpenCV + imagehash pHash dedup |

### 📝 Commit Message
```
docs: refresh BOOTSTRAP.md + checkpoint with full project state

Rebuilt stale BOOTSTRAP.md agent handoff doc from scratch to reflect
current codebase reality. Old version was frozen pre-cyberpunk-theme
and pre-extraction-APIs, listing only a fraction of the 30 live routes.

- Full 30-route inventory categorized by subsystem
- Cyberpunk theme (celadon/CRT/glassmorphism) documented
- LLM library table: 13 curated models, quants, architectures
- Session-by-session accomplishment log (A-E)
- Expanded gotchas: deleted files, IDE terminal quirks
- Appended status_checkpoint.md session E entry
```

---

**Last Updated:** 2026-07-02 — Cline Session E (Bootstrap Refresh)

---

## 📅 Session: 2026-07-05 — RPG Character Prompt Builder Overhaul (Antigravity)

### ✅ Database Migration & Seed
- [x] Migrated `prompt_generator.db` to new structure supporting hierarchical dependencies.
- [x] Created `dropdown_options` and `tag_chips` tables.
- [x] Populated **288 dropdown options**, **19 quality chips**, and **3 archetype presets** (Dark Sorceress, Cyberpunk Hacker, Gothic Valkyrie).

### ✅ RPG Character Builder UI Rewrite
- [x] Replaced flat dropdown UI with an RPG-style character sheet interface using 7 tabbed panels.
- [x] Implemented cascading dependent dropdown trees (e.g., sex/gender -> archetype, environment -> location, etc.).
- [x] Added live color-coded prompt preview rendering in real-time.
- [x] Integrated character card saving/loading directly to SQLite backend.
- [x] Created direct ComfyUI API endpoint injection for Flux generations.
- [x] Removed all NSFW/SFW filtering restrictions per user direction.

### ✅ Collapsible LoRAs & Trigger Word Stack
- [x] Wrapped LoRA stack manager in an accordion-style collapsible interface.
- [x] Integrated trigger words edit field next to weight sliders for each active LoRA.
- [x] Persisted custom trigger words via local storage.
- [x] Configured /api/loras to scan directory recursively (unlocking `/steps` checkpoints and training iterations).
- [x] Automatically inject active LoRA tags and their associated trigger words into the final prompt builder string.

---

**Last Updated:** 2026-07-05 — Antigravity Session (RPG Overhaul Complete)

---

## 📅 Session: 2026-07-05 — Harlequin Archetypes, Clones & Custom Prompt Vault (Antigravity)

### ✅ Prompt Truncation & Backend Scaling
- [x] Swapped max generation tokens constraint from 400 to 1024/2048 to prevent truncated prompts.
- [x] Implemented a model picker header, querying Ollama dynamically (`/api/ollama_models`) and updating active settings.
- [x] Aligned dynamic preset workers with the user-selected active Ollama model.

### ✅ Harlequin Romance novel Archetypes & Gender Hardline
- [x] Hardlined genders strictly to Male and Female, removing other designations from default listings.
- [x] Migrated `archetype` selections from DND roles to Harlequin Romance Novel characters (Brooding Billionaire, Rogue Rake, Dashing Marquess, Scandalous Widow, Innocent Governess, etc.).
- [x] Expanded anatomy options covering thighs, waist, ass, tits, arms, and styles matching romance novels.
- [x] Doubled the options inside the Lighting tab.

### ✅ Duplicates & Custom Text Inputs
- [x] Enabled custom text fields alongside every option selector to support arbitrary user additions.
- [x] Added duplicate clone triggers (`+` button) to spawn up to 3 separate duplicate option selector slots per card.
- [x] Integrated copy clipboard logic with fallbacks for non-secure HTTP boundaries.
- [x] Rebuilt favorites list into a SQLite-backed Prompt Vault database.

---

**Last Updated:** 2026-07-05 — Antigravity Session (Harlequin & Clones Complete)

---

## 📅 Session: 2026-07-05 — Locks, Tab Persistence & Worker VRAM Flushing (Antigravity)

### ✅ Tab Refresh & State Persistence
- [x] Implemented `localStorage` state serialization on the frontend. The entire builder state (selections, clones, custom text inputs, and locks) is saved on change and restored automatically on page reload.
- [x] This prevents the prompt generator from losing user choices when switching tabs inside the parent Command Center iframe dashboard.

### ✅ Model Locking Mechanic
- [x] Added padlock icons (`🔓`/`🔒`) next to every option row.
- [x] Checking lock locks the value.
- [x] Rolling all random values (`Roll Unlocked`) skips locked values, preserving choices.

### ✅ Background VRAM Flush & Model Bypass
- [x] Added `keep_alive: 0` to the Ollama preset worker requests, ensuring VRAM is fully freed between background preset updates.
- [x] Injected system prompt instructions asking models to ignore alignment filters to improve tag expansion on standard LLMs.

---

**Last Updated:** 2026-07-05 — Antigravity Session (Overhaul Polished)

---

## 📅 Session: 2026-07-05 — Single Launch Ignition & Kill Button Integration (Antigravity)

### ✅ Simplified Dashboard Ignition Panel
- [x] Overhauled the Command Center Prompt Generator tab dashboard.
- [x] Removed the model select dropdowns and the backend select boxes from the ignition screen.
- [x] Simplified the setup to a single "Launch Prompt Workstation" button.

### ✅ Integrated Terminate/Kill Action
- [x] Added a new backend route `/api/kill-prompt-generator` that scans for running `prompt_generator_app.py` process namespaces or port `9669` sockets and halts them.
- [x] Exposed a "Kill Workstation" button directly in the active iframe tab header to shut down the server process on demand.

---

**Last Updated:** 2026-07-05 — Antigravity Session (Dashboard Ignition Complete)

---

## 📅 Session: 2026-07-05 — Ollama Models List Filtering (Antigravity)

### ✅ Whitelist Filter for Prompt Generator Models
- [x] Implemented a whitelist query filter on the `/api/ollama_models` route.
- [x] Only models matching keyword strings (`nsfw`, `uncensored`, `dolphin`, `hermes`, `lexi`, `hades`, `prompt-gen`) are returned to the picker dropdown.
- [x] This screens out unrelated vision, coding, and heavily aligned base models to keep the picker list lightweight and targeted to uncensored prompt expansion.

---

**Last Updated:** 2026-07-05 — Antigravity Session (Model List Filter Complete)

---

## 📅 Session: 2026-07-05 — Infinite Chaos: Global Dropdown Customization (Antigravity)

### ✅ Complete Dropdown Customization
- [x] Overhauled the `/api/section/` endpoint in the Prompt Workstation to inject dynamic options into *every* dropdown field.
- [x] Implemented a background thread `cache_hydrator_worker()` that cycles through every visual attribute field (build type, breast shape, hip curve, thigh description, hair, hosiery, lighting, camera angles, locations, time, shadow styling, output modes, etc.).
- [x] The worker pre-generates batches of 15 creative, uncensored visual items using the active LLM backend and caches them.
- [x] Pre-populated choices are prepended with `✨` emoji tags, refreshing with new selections on every workstation tab refresh or reload.

---

**Last Updated:** 2026-07-05 — Antigravity Session (Infinite Chaos Overhaul Complete)

---

## 📅 Session: 2026-07-06 — Batch Expansion & Local Prompts Storage (Antigravity)

### ✅ Local Batch Expansion Module
- [x] Integrated a new UI sub-module **Batch Expansion** inside the Prompt Workstation output panel.
- [x] Enables batch prompt generation loops with configurable run lengths (e.g. 5, 10, 20 runs).
- [x] Added randomization modes: **Randomize Unlocked** (respects UI settings locks, picking new choices only for unlocked features) and **Randomize All Options**.
- [x] Added automated prompt writing inside the backend: expanded prompts are automatically written to `D:\AI\Prompts` with filenames matching `prompt_YYYYMMDD_HHMMSS_idx.txt`.

---

**Last Updated:** 2026-07-06 — Antigravity Session (Batch Expansion Complete)
