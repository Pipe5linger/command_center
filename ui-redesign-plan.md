# Command Center UI & Functional Redesign Plan

## 1. Executive Summary
This project aims to transform the Command Center from a static interface into a dynamic, "Cyberpunk" styled system monitor. The redesign focuses on real-time data ingestion, dynamic list generation from local directories, unified terminal management, and a highly polished, interactive UI.

## 2. Architectural Strategy
*   **Sub-Agent Workflow:** The primary agent shall delegate tasks to sub-agents for specific modular components (e.g., Layout & Grid, Interaction Layer, Telemetry).
*   **Active Collaboration (The 3-Choice Rule):** For every new UI element or significant functional change, the agent **must** present 3 distinct design/implementation directions before writing code:
    *   **Choice A:** Conservative / Function-first.
    *   **Choice B:** Balanced / Modern.
    *   **Choice C:** Experimental / Highly "Cyberpunk" creative.
*   **Creative Liberty:** The agent is encouraged to add micro-interactions, animations, and depth effects, provided they stay within the established visual theme. Propose flourishes (e.g., scanlines, data-glitch effects) as part of "Choice C."

## 3. Functional Requirements (Priority Phase)
The following functional updates must be prioritized to ensure the UI is built on a stable data foundation:

### A. Telemetry & Monitoring
*   **System Monitor Tab:** Fix the GPU/Telemetry polling accuracy to ensure real-time rendering. Refactor the polling service if necessary.

### B. Dynamic List Management
*   **File Explorer Tab:** Replace the static UI with a dynamic list of the last 10 open folders.
*   **Launchers Tab:** Implement a directory watcher for `D:/AI/Launchers`. The UI must automatically update its list based on the executable/shortcut files present in this directory.

### C. Unified Terminal Interface
*   **Silent Launch Execution:** Configure background processes (Kobold, Ollama, LM Studio, ComfyUI, etc.) to launch without foreground windows.
*   **Terminal Multiplexing:** Create a container in the Terminals tab that dynamically mounts active process streams.
*   **Responsive Grid:** Implement a CSS Grid layout that automatically adjusts column/row counts based on the number of active terminal sessions (e.g., 1 session = full screen, 2 sessions = 50/50 split, 4+ = grid).

### D. Backend-Aware UI
*   **AI Matrix Tab:** Make the launcher area dynamic. It must switch configuration options, sliders, and inputs based on the detected backend service currently running (e.g., Kobold vs. Ollama).

## 4. Visual & Spatial Requirements (UI Redesign)
*   **Reference Images:** Use `image_6fe791.png`, `image_6feb52.png`, `image_6fee37.png`, `image_6fef12.jpg`, and `image_6ff239.png` as visual benchmarks for current state and spatial layout.
*   **Component Library:** Use the modular `.vue` and `.html` components stored in `_design_references/` (Loaders, Locks, Dials, Inputs, Glassmorphism layouts) to replace generic UI elements.

## 5. Configuration & Color System
All UI development must pull its design tokens from the central theme configuration. 

*   **Source of Truth:** `/src/styles/theme-config.css`
*   **Variable Usage:** Use CSS variables for all colors (e.g., `background-color: var(--bg-void)`).
*   **Constraint:** Do not use hardcoded hex values in component stylesheets.

### Theme Overview (Crimson-Celadon Dynamic)
*   **Backgrounds & Surfaces:** `--color-crimson-violet` and `--color-blackberry-cream` are reserved for deep backgrounds and primary containers.
*   **Accents & Glows:** `--color-pearl-aqua` and `--color-celadon` are reserved for active states, neon glows, and live telemetry feedback.
*   **Structure:** `--color-rosy-granite` is used for borders, secondary text, and inactive states.

---

## 6. Instructions for the Cline Agent
1.  **Read:** Before any implementation, read this `ui-redesign-plan.md` and review the `_design_references/` library.
2.  **Consult:** Before modifying any tab or function, present your 3 choices (A, B, C) and wait for user selection.
3.  **Refactor Phase:** Ensure backend polling and file-watching logic is stable before applying the visual layer.
4.  **Execute:** Delegate to sub-agents as necessary to maintain a modular, clean codebase.