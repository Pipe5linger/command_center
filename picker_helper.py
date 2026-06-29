"""
Standalone file/folder picker helper for SDC.
Spawned by Flask via subprocess with lpDesktop="winsta0\\default" STARTUPINFO
to bind explicitly to the interactive desktop session.

The dialog is forced topmost and lifted aggressively to prevent it from
rendering behind the browser window.

Usage:
    pythonw picker_helper.py folder <tmp_path>
    pythonw picker_helper.py file   <tmp_path> [video]
"""
import sys
import os
import tkinter as tk
from tkinter import filedialog


def main():
    mode     = sys.argv[1] if len(sys.argv) > 1 else "folder"
    out_file = sys.argv[2] if len(sys.argv) > 2 else None
    filt     = sys.argv[3] if len(sys.argv) > 3 else ""

    root = tk.Tk()
    root.withdraw()

    # Force the root window to the interactive desktop foreground
    root.attributes('-topmost', True)
    root.attributes('-alpha', 0.0)   # invisible but present - gives us a real HWND
    root.deiconify()
    root.lift()
    root.focus_force()
    root.update()

    if mode == "folder":
        path = filedialog.askdirectory(
            title="Select Folder — SDC",
            parent=root
        )
    elif mode == "file":
        filetypes = [("All Files", "*.*")]
        if filt == "video":
            filetypes = [
                ("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm"),
                ("All Files", "*.*")
            ]
        path = filedialog.askopenfilename(
            title="Select File — SDC",
            filetypes=filetypes,
            parent=root
        )
    else:
        path = ""

    root.destroy()

    if out_file:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(path if path else "")


if __name__ == "__main__":
    main()
