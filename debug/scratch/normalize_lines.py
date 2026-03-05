import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'rb') as f:
    data = f.read()

# Replace all \r\n and \r with \n
# Then replace \n with \r\n for Windows consistency
normalized = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
final = normalized.replace(b'\n', b'\r\n')

with open(file_path, 'wb') as f:
    f.write(final)
print("Line endings normalized")
