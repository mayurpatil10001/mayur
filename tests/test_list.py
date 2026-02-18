import os
import glob

path = r"C:\SierraChart\SC results WF"
print(f"Path: {path}")

found = []
for root, dirs, files in os.walk(path):
    for f in files:
        if f.upper().endswith(".DATA"):
            found.append(os.path.join(root, f))
            if len(found) < 5:
                print(f"Found: {os.path.join(root, f)}")

print(f"Total .DATA files found: {len(found)}")
