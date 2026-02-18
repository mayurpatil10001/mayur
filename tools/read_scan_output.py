
import os

filepath = "scanner_output.txt"
if os.path.exists(filepath):
    with open(filepath, "rb") as f:
        content = f.read()
        # Decode iteratively or just replace
        text = content.decode("utf-16le", errors="ignore") # The error said utf-16le, maybe powershell made it so?
        if not text.isprintable(): # If it looks garbage, try utf-8
             # Powershell '>' often creates utf-16le
             pass
        print(text)
else:
    print("File not found")
