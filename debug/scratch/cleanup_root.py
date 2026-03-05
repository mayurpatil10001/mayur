import os
import shutil
from pathlib import Path

# Base directory
base_dir = Path(r"C:\SierraChart\SC results WF")
scratch_dir = base_dir / "debug" / "scratch"
scratch_dir.mkdir(parents=True, exist_ok=True)

# Patterns to move
patterns = [
    "check_*.py", "test_*.py", "audit_*.py", "diag_*.py", "debug_*.py",
    "sim_*.py", "verify_*.py", "trace_*.py", "find_*.py", "dump_*.py",
    "analyze_*.py", "inspect_*.py", "audit_*.txt", "diag_*.txt",
    "search_*.py", "search_*.txt", "out*.txt", "tags_*.txt",
    "*_result.txt", "*_report.txt", "pos_*.py", "pos_*.txt",
    "hex_*.py", "hex_*.txt", "parse_*.py", "decode_*.py",
    "extract_*.py", "reimport_*.py", "run_*.py", "target_*.py",
    "targeted_*.py", "trigger_*.py", "wipe_*.py", "reset_*.py",
    "fix_*.py", "update_*.py", "list_*.py", "get_*.py",
    "repro_*.py", "mass_*.py", "manual_*.py", "final_*.py",
    "checkpoint_*.py", "optimize_*.py", "add_*.py", "create_*.py",
    "migrate_*.py", "calc_*.py", "match_*.py", "scan_*.py",
    "dual_*.py", "smoking_*.py", "standalone_*.py", "sync_*.py",
    "global_*.py", "session_*.py", "minimal_*.py", "line_*.py",
    "normalize_*.py", "pos_analyser.py", "accurate_*.py",
    "activity_*.py", "examine_*.py", "investigate_*.py",
    "reverse_*.py", "sanitize_*.py", "discover_*.py",
    "peek_*.py", "vsim16_*.py", "detailed_*.py",
    "test_*.db", "drift_*.db", "trades.db", "vsim16_*.db",
    "*.log", # We'll handle trading_platform.log separately
    "*.bat", # We'll handle run_server.bat separately
]

# Files to KEEP in root (explicitly)
keep_files = {
    ".env", ".gitignore", "alembic.ini", "app_settings.json",
    "Dockerfile", "docker-compose.yml", "main.py", "README.md",
    "requirements.txt", "trading_platform.db", "trading_platform.log"
}

# Directories to keep
keep_dirs = {
    ".bmad-core", ".claude", ".cursor", ".git", ".kiro", ".pytest_cache", ".vscode",
    "__pycache__", "alembic", "data", "debug", "docs", "frontend", "legacy",
    "logs", "models", "scripts", "tests", "tools", "trading_platform",
    "validation_reports", "venv"
}

moved_count = 0
for item in base_dir.iterdir():
    if item.name in keep_files or item.name in keep_dirs:
        continue
    
    if item.is_file():
        # Check against patterns
        should_move = False
        for pattern in patterns:
            if item.match(pattern):
                should_move = True
                break
        
        # If it's a .py, .txt, .db file not explicitly kept, move it
        if item.suffix in ['.py', '.txt', '.db', '.log', '.bat', '.json', '.yaml']:
            should_move = True
            
        if should_move:
            try:
                # Handle duplicates if they exist in scratch
                target = scratch_dir / item.name
                if target.exists():
                    # Move to a timestamped folder if duplicate
                    target = scratch_dir / f"{item.stem}_{int(os.path.getmtime(item))}{item.suffix}"
                
                shutil.move(str(item), str(target))
                moved_count += 1
            except Exception as e:
                print(f"Error moving {item.name}: {e}")

print(f"Successfully moved {moved_count} files to debug/scratch/")
