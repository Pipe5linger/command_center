with open('d:/AI/Projects/command_center/test_html.html', 'r', encoding='utf-8') as f:
    raw = f.read()

# Slice from <!DOCTYPE html> to </html>
start_idx = raw.find('<!DOCTYPE html>')
end_idx = raw.rfind('</html>') + len('</html>')
content = raw[start_idx:end_idx]

with open('d:/AI/Projects/command_center/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

lines = content.splitlines()
print('Done. Lines written:', len(lines))
print('First line:', lines[0])
print('Last line:', lines[-1])


