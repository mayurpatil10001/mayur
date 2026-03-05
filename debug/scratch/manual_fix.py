import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    line_num = i + 1
    if line_num == 115:
        line = '      const accRes = await fetch(`${API_BASE}/api/system/accounts`);\n'
    if line_num == 122:
        line = '      const statusRes = await fetch(`${API_BASE}/api/system/status`);\n'
    if line_num == 127:
        line = '      const settingsRes = await fetch(`${API_BASE}/api/system/settings`);\n'
    if line_num == 222:
        # fetchImportStatus();tch(`${API_BASE}/api/system/import-status`);;
        # Wait, let me check 222 in view_file
        pass
    if line_num == 235:
        line = '    if (!window.confirm(`Permanently remove future trades, PnL outliers and overnight holds for ${account}?`)) return;\n'
    if line_num == 244:
        line = '      alert(`Cleaned: ${data.removed.future} future, ${data.removed.overnight} overnight, ${data.removed.outliers} PnL outliers.`);\n'
    if line_num == 269:
        line = '      const res = await fetch(`${API_BASE}/api/v1/accounts/accounts/${account}/validate?symbol=${symbol}`);\n'
    if line_num == 876:
        line = '                    alert("Import failed: " + e);\n'
    
    # Fix the double semicolon issue from my previous script
    line = line.replace('`);;', '`);')
    
    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Manual line-by-line correction completed")
