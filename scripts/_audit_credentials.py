import os
import glob
import re
from pathlib import Path

PROJECT_ROOT = Path(r"c:\SC_results_WF")
ignore_dirs = {'.git', 'node_modules', '.venv', '__pycache__', 'dist', 'build', '.gemini'}

findings = []

for root, dirs, files in os.walk(PROJECT_ROOT):
    dirs[:] = [d for d in dirs if d not in ignore_dirs]
    for file in files:
        filepath = Path(root) / file
        relpath = filepath.relative_to(PROJECT_ROOT)
        
        # Check config files
        if file.startswith('.env') or file.endswith(('.json', '.yaml', '.yml', '.key', '.pem', '.ini')):
            if 'package' not in file and 'tsconfig' not in file and 'components' not in str(relpath):
                findings.append(("Config/Env File", str(relpath), "Configuration file"))
                
        # Scan file content for secrets
        if file.endswith(('.py', '.ts', '.tsx', '.js', '.json', '.env', '.bat', '.sh', '.yaml')):
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')
                # Look for API keys, passwords, JWT secrets
                patterns = [
                    r'(?i)(secret_key|jwt_secret|api_key|password|access_token|auth_secret)\s*[:=]\s*["\']([^"\']{4,})["\']',
                    r'(?i)(BEARER|TOKEN|KEY)\s*[:=]\s*["\'](ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})["\']', # JWT
                ]
                for p in patterns:
                    for match in re.finditer(p, content):
                        key_name = match.group(1)
                        val = match.group(2)
                        if val.lower() not in {'string', 'your-secret-key', 'change-me', 'development', 'none', 'true', 'false'}:
                            findings.append(("Secret Candidate", f"{relpath}:{match.start()}", f"{key_name} = {val[:6]}***"))
            except Exception:
                pass

print(f"Total findings: {len(findings)}")
for cat, loc, desc in findings:
    print(f"[{cat}] {loc} -> {desc}")
