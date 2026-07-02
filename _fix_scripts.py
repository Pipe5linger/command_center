"""Script to fix terminal API in app.py — replaces old streaming endpoint
with proper JSON endpoints, then fixes the template JS bugs.
Run from command_center directory."""
import re

# ---- 1. Fix app.py terminals ----
app_path = r"D:\AI\Projects\command_center\app.py"
with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the old streaming logs function (the one with log_file_path)
old_logs = """@app.route('/api/terminals/logs', methods=['GET'])
def api_terminals_logs():
    log_file_path = "scc_server.log" # Assume scc_server.log is in the same directory
    if not os.path.exists(log_file_path):
        x

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
    return app.response_class(generate(), mimetype='text/plain')"""

new_logs = """@app.route('/api/terminals/logs', methods=['GET'])
def api_terminals_logs():
    \"\"\"Return all captured process logs as JSON.\"\"\"
    return jsonify(dict(streams=dict(_terminal_buffers)))"""

if old_logs in content:
    content = content.replace(old_logs, new_logs)
    print("Replaced /api/terminals/logs endpoint.")
else:
    print("WARNING: Could not find old logs function in app.py!")

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("app.py fixes complete.")


# ---- 2. Fix templates/index.html Ollama model selectors ----
template_path = r"D:\AI\Projects\command_center\templates\index.html"
with open(template_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Fix fetchOllamaModels - lines ~1000-1004
# Old: o.value=m; o.textContent=m; m.includes('nsfw')
# New: o.value=m.name; o.textContent=m.name; m.name.includes('nsfw')
old_fetch = """d.models.forEach(m=>{const o=document.createElement('option');o.value=m;o.textContent=m;if(m.includes('nsfw')||m.includes('prompt'))o.selected=true;s.appendChild(o)});"""
new_fetch = """d.models.forEach(m=>{const o=document.createElement('option');o.value=m.name;o.textContent=m.name;if(m.name&&(m.name.includes('nsfw')||m.name.includes('prompt')))o.selected=true;s.appendChild(o)});"""
if old_fetch in html:
    html = html.replace(old_fetch, new_fetch)
    print("Fixed fetchOllamaModels selector.")
else:
    print("WARNING: fetchOllamaModels pattern not found!")

# Fix populateSdcVlmModels - lines ~1055-1056
# Old: o.value = m; o.textContent = m;
# New: o.value = m.name; o.textContent = m.name;
old_sdc = """d.models.forEach(m => {
            // Favor vision models, but include all
            const o = document.createElement('option');
            o.value = m;
            o.textContent = m;
            if(m.name&&(m.name.includes('vision')||m.name.includes('llava')))o.selected=true;"""
new_sdc = """d.models.forEach(m => {
            // Favor vision models, but include all
            const o = document.createElement('option');
            o.value = m.name;
            o.textContent = m.name;
            if(m.name&&(m.name.includes('vision')||m.name.includes('llava')))o.selected=true;"""
if old_sdc in html:
    html = html.replace(old_sdc, new_sdc)
    print("Fixed populateSdcVlmModels selector.")
else:
    print("WARNING: populateSdcVlmModels pattern not found!")

# Fix navigateUp - use proper Windows path parsing
old_nav = """function navigateUp() {
            const sep = currentExplorerPath.includes('\\\\\\\\') ? '\\\\\\\\\\\\\\\\' : '\\\\\\\\';
            const parts = currentExplorerPath.split(sep);
            if (parts.length > 1) {
                parts.pop();
                let parent = parts.join('\\\\\\\\');
                if (parent.match(/^[A-Z]:$/i)) parent += '\\\\\\\\';
                loadDirectory(parent);
            }"""
# Hmm this is tricky with backslashes. Let me re-read the exact content.

with open(template_path, 'r', encoding='utf-8') as f:
    html = f.read()

# NavigateUp fix - use simpler path parsing
# Search for the navigateUp function
nav_pattern = r'(async function navigateUp\(\) \{[\s\S]*?loadDirectory\(parent\);\s*\})'
nav_match = re.search(nav_pattern, html)
if nav_match:
    old_nav_text = nav_match.group(1)
    new_nav_text = """async function navigateUp() {
            // Split on backslash, handle Windows path separators properly
            const parts = currentExplorerPath.split('\\\\');
            // Remove empty trailing segment from trailing backslash
            if (parts[parts.length - 1] === '') parts.pop();
            if (parts.length > 1) {
                parts.pop();
                let parent = parts.join('\\\\');
                if (parent.match(/^[A-Z]:$/i)) parent += '\\\\';
                loadDirectory(parent);
            }"""
    html = html.replace(old_nav_text, new_nav_text)
    print("Fixed navigateUp.")
else:
    print("WARNING: navigateUp pattern not found!")

with open(template_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("Template fixes complete. Now delete root index.html...")

# ---- 3. Delete garbage root index.html ----
import os
garbage = r"D:\AI\Projects\command_center\index.html"
if os.path.exists(garbage):
    os.remove(garbage)
    print("Deleted garbage root index.html.")
else:
    print("Root index.html already deleted or not found.")

import os
garbage2 = r"D:\AI\Projects\command_center\served.html"
if os.path.exists(garbage2):
    os.remove(garbage2)
    print("Deleted stale served.html.")

garbage3 = r"D:\AI\Projects\command_center\test_html.html"
if os.path.exists(garbage3):
    os.remove(garbage3)
    print("Deleted stale test_html.html.")

print("All fixes complete.")