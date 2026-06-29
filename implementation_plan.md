# Sanctuary Command Center (SCC) — Integration Implementation Plan

This implementation plan outlines the steps required to merge the advanced video downloading, trimming, and extraction functionalities of the standalone **Sanctuary Video Downloader & Clipper (SVD)** and the **Sanctuary Dataset Curator (SDC)** directly into the unified dashboard in the `command_center` workspace.

---

## 🎯 Target Goal
Consolidate all disjointed tools (standalone downloader, frame extractor, staging deduplication, and advanced cropping) into a single, cohesive dashboard layout inside [sanctuary_command_center.py](file:///D:/AI/Projects/command_center/sanctuary_command_center.py).

---

## 🛠️ Step-by-Step Integration Plan

### Step 1: Python API Integrations

The Flask server inside [video_downloader.py](file:///D:/AI/Projects/Sanctuary%20Video%20Downloader%20&%20Clipper%20(SVD)/video_downloader.py) and [dataset_curator.py](file:///D:/AI/Projects/Sanctuary%20Dataset%20Curator%20(SDC)/dataset_curator.py) implements core system endpoints. These must be ported to the `DashboardHandler` class inside `sanctuary_command_center.py`.

#### 1. Video Harvester APIs (`yt-dlp` integration)
*   **`GET /api/info`**: Runs `yt-dlp -F [URL]` to fetch the remote formats, downloads the video thumbnail, retrieves title/duration, and returns them as JSON.
*   **`POST /api/download`**: Runs the download process using a background thread:
    ```bash
    yt-dlp -f "bestvideo+bestaudio/best" --merge-output-format mkv -o "D:/AI/Downloads/%(title)s.%(ext)s" [URL]
    ```
    If timestamp range variables are supplied (`start_time`, `end_time`), invoke `ffmpeg` stream copying targeting the specified seconds instead of compiling the entire stream.

#### 2. Video Extraction & Staging APIs (OpenCV + Perceptual Hashing)
*   **`POST /api/extract`**: Spawns an asynchronous frame extractor thread.
    *   Imports `cv2` (OpenCV) and iterates through target video frames using intervals or custom frame steps.
    *   If `enable_dedup` is active, compute perceptual hashes using `imagehash.phash` and discard frames with a difference threshold below your target value (default 12).
*   **`GET /api/extract-status`**: Returns telemetry state (`running`, `paused`, `progress`, `total`).

---

### Step 2: Front-End UI Consolidation

Upgrade the **Dataset Curator** tab layout (`tabContent-curator`) inside the `HTML_UI` string of [sanctuary_command_center.py](file:///D:/AI/Projects/command_center/sanctuary_command_center.py).

1.  **Tab Navigation Bar**:
    Graft a sub-navigation bar inside the curator tab to switch between sub-studio views:
    *   `Ingest`: Video Harvester (`yt-dlp` controls) and frame extraction inputs.
    *   `Stage`: File lists, perceptual deduplication button, and resolution filtering.
    *   `Curate`: Bounding box cropping panels and Ollama-based VLM tagging (currently implemented).
2.  **Add Visual Telemetry**:
    Inject progress bars and log windows that stream logs in real-time using the existing `/api/terminals/logs` endpoint structure.

---

## 🚨 Dependency Warnings

*   `yt-dlp` and `ffmpeg` must be configured in your system environment PATH.
*   Ensure the `opencv-python` and `imagehash` packages are installed in the interpreter environment.
*   Port `9999` must be freed before spinning up the daemon VBScript.

---

## 🔍 Verification Checklist

- [ ] Verify `yt-dlp` format inspection runs cleanly without triggering domain redirect warnings.
- [ ] Test the lossless video trimmer using `-ss` and `-to` offset parameters.
- [ ] Scan a staged folder and verify that the perceptual deduplication script correctly filters out frame iterations.
- [ ] Confirm Ollama connects to local vision parameters and returns auto-tags.
