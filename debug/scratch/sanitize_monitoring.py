import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

checked_lines = []
for line in lines:
    if 'pi/system/import-start' in line:
        print(f"Found garbage line: {repr(line)}")
        # Clean it
        line = line.split(';')[0] + ';\n'
    checked_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(checked_lines)
print("Sanitization complete")
