# Sanctuary Command Center (SCC) - Progress Checkpoint

## Project Overview
Integration of the Sanctuary Video Downloader & Clipper (SVD) and the Sanctuary Dataset Curator (SDC) into a unified Command Center dashboard.

## Current Status: Step 1 (Backend API Porting)
**Status:** 🟢 Not Started (API Phase)

### ✅ Completed
- [x] Core Dashboard Framework (Python/Flask/SimpleHTTPRequestHandler)
- [x] Ollama Model Fetching Integration
- [x] Local File Explorer Integration
- [x] Basic Curator UI (Base Layout)

### ⏳ In Progress / Next Up
- [ ] **Step 1.1: Video Harvester APIs**
    - Port `GET /api/info` (yt-dlp format inspection)
    - Port `POST /api/download` (background download with timestamping)
- [ ] **Step 1.2: Extraction & Staging APIs**
    - Port `POST /api/extract` (OpenCV frame extraction + imagehash deduplication)
    - Port `GET /api/extract-status` (Telemetry for progress bars)
- [ ] **Step 2: Frontend UI Consolidation**
    - Implement "Sub-Studio" Layout (Ingest / Stage / Curate tabs)
    - Real-time Telemetry & Log Streamers

## Notes
- **Current Bottleneck:** Need to ensure `yt-dlp` and `opencv-python` are properly handled in the backend environment.
- **VRAM Context:** Using RTX 4070 (12GB). Ensure Ollama/KoboldCPP releases memory after generation.

**Last Updated:** 2026-06-29
