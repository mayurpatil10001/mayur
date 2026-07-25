"""
reorganize.py
=============
Phase 1 repo cleanup script for Sierra Chart Trade Optimization Platform.

Performs:
  1. Moves 80+ throwaway debug/check/find scripts → archive/debug_scripts/
  2. Moves root-level *.md audit files → docs/audits/
  3. Moves root-level *.pdf reports → docs/reports/
  4. Renames trading_platform/ → backend/ (if not already done)
  5. Creates missing __init__.py across all backend modules
  6. Adds critical files to .gitignore (*.db, *.log, __pycache__, etc.)
  7. Generates Makefile with standard targets

Usage:
    python reorganize.py [--dry-run]

Options:
    --dry-run   Print what would happen without making changes.
"""

import os
import re
import shutil
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"  {msg}")

def move(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if DRY_RUN:
        log(f"[DRY] MOVE {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
    else:
        shutil.move(str(src), str(dst))
        log(f"MOVE  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")

def rename_dir(src: Path, dst: Path) -> None:
    if not src.exists():
        log(f"SKIP  {src.name}/ (not found)")
        return
    if dst.exists():
        log(f"SKIP  {src.name}/ -> {dst.name}/ (destination already exists)")
        return
    if DRY_RUN:
        log(f"[DRY] RENAME DIR {src.name}/ -> {dst.name}/")
    else:
        src.rename(dst)
        log(f"RENAME DIR {src.name}/ -> {dst.name}/")

def touch(path: Path) -> None:
    if path.exists():
        return
    if DRY_RUN:
        log(f"[DRY] CREATE {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        log(f"CREATE {path.relative_to(ROOT)}")

def write_file(path: Path, content: str) -> None:
    if DRY_RUN:
        log(f"[DRY] WRITE  {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log(f"WRITE  {path.relative_to(ROOT)}")

# ── Step 1: Classify scripts for archiving ───────────────────────────────────

# Patterns that mark a script as a throwaway / debug artifact
ARCHIVE_PREFIXES = (
    "check_", "find_", "detect_", "debug_", "compare_", "search_",
    "test_",   # one-off test scripts (not pytest files)
    "analyze_", "inspect_", "audit_", "calc_", "correlate_",
    "populate_", "reimport_", "simulate_", "stationarity_",
    "verify_", "deduplicate_", "optimize_",
)

ARCHIVE_EXACT = {
    "clean_all_trades.py", "clean_binary_garbage.py", "clean_garbage.py",
    "clean_ts4_reimport.py", "clear_db.py", "clear_sim14.py", "clear_sim15.py",
    "comprehensive_processed_import.py", "convert_md_to_pdf.py",
    "db_cleanup_outliers.py", "export_problematic_sequences.py",
    "final_nuke.py", "force_import_sim15_gap.py",
    "generate_500_day_audit_report.py", "generate_dev_token.py",
    "generate_detailed_session_ab_audit.py", "generate_full_562_day_stage4_audit.py",
    "generate_master_project_update_audit.py", "generate_pipeline_superiority_audit.py",
    "generate_ultra_detailed_master_audit.py", "generate_clean_tm7_sequence.py",
    "global_persistence_test.py", "integrate_advanced_recommendations.py",
    "nuclear_clear_ts4.py", "nuke_garbage.py", "thorough_cleanup.py",
    "trade_reconstructor.py", "trigger_cl_sync.py", "trigger_sim15_sync.py",
    "wipe_cl.py", "simple_api_server.py", "run_full_sync.py",
    "run_test_import.py", "run_verification_import.py", "run_calc.bat",
    "batch_verify_range.py", "sample_data_validator.py",
    "verification_audit_data.json",
    # GFRE analysis scripts → move to tests/
    "tm7_nq_ghost_analysis.py", "test_fast_days_resync.py",
    "find_ghost_creators.py", "full_signal_fill_sync.py",
    "parse_graphdata_signals.py",
}

# Scripts to KEEP in /scripts/ (operational)
KEEP_IN_SCRIPTS = {
    "run_walk_forward_test.py", "run_permutation_test.py",
    "run_out_of_sample_audit.py", "promote_clean_data_to_production.py",
    "run_full_import.py", "generate_report.py",
    "start_trading_platform.bat", "start_backend_only.bat",
    "start_frontend_only.bat", "kill_trading_platform.bat",
    "monitor_logs.bat", "restart_api.bat",
    "export_problematic_sequences.py",  # keep for docs/examples
}

def should_archive(name: str) -> bool:
    if name in KEEP_IN_SCRIPTS:
        return False
    if name in ARCHIVE_EXACT:
        return True
    for prefix in ARCHIVE_PREFIXES:
        if name.startswith(prefix):
            return True
    return False

def step1_archive_scripts() -> None:
    print("\n-- Step 1: Archive throwaway scripts ------------------------------")
    archive_dir = ROOT / "archive" / "debug_scripts"
    scripts_dir = ROOT / "scripts"

    if not scripts_dir.exists():
        log("scripts/ not found — skipping")
        return

    archived = 0
    for f in sorted(scripts_dir.iterdir()):
        if f.is_file() and f.suffix in (".py", ".json", ".bat") and should_archive(f.name):
            move(f, archive_dir / f.name)
            archived += 1

    log(f"Archived {archived} files into archive/debug_scripts/")

# ── Step 2: Move audit docs ───────────────────────────────────────────────────

def step2_move_docs() -> None:
    print("\n-- Step 2: Move root-level docs ------------------------------------")

    # .md files at root that belong in docs/
    root_mds = [
        "ghost_fill_audit.md", "project_deep_dive.md",
    ]
    for name in root_mds:
        src = ROOT / name
        if src.exists():
            move(src, ROOT / "docs" / "audits" / name)

    # PDFs at root -> docs/reports/
    for f in ROOT.glob("*.pdf"):
        move(f, ROOT / "docs" / "reports" / f.name)

    log("Root-level docs moved.")

# -- Step 3: Rename trading_platform/ -> backend/ ------------------------------

def step3_rename_backend() -> None:
    print("\n-- Step 3: Rename trading_platform/ -> backend/ ---------------------")
    rename_dir(ROOT / "trading_platform", ROOT / "backend")

    # Also fix root main.py import if it exists
    root_main = ROOT / "main.py"
    if root_main.exists() and not DRY_RUN:
        content = root_main.read_text(encoding="utf-8")
        updated = content.replace("from trading_platform", "from backend")
        updated = updated.replace("import trading_platform", "import backend")
        if updated != content:
            root_main.write_text(updated, encoding="utf-8")
            log("Updated imports in root main.py")

# -- Step 4: Create missing __init__.py ---------------------------------------

BACKEND_PACKAGES = [
    "backend",
    "backend/core",
    "backend/db",
    "backend/models",
    "backend/schemas",
    "backend/repositories",
    "backend/services",
    "backend/services/ingestion",
    "backend/services/analytics",
    "backend/services/walkforward",
    "backend/services/montecarlo",
    "backend/services/recommendation",
    "backend/services/statistical",
    "backend/services/market_data",
    "backend/services/ml",
    "backend/services/export",
    "backend/services/monitoring",
    "backend/api",
    "backend/api/v1",
    "backend/api/v1/routes",
    "backend/utils",
    "tests",
    "tests/unit",
    "tests/integration",
    "tests/fixtures",
]

def step4_create_init_files() -> None:
    print("\n-- Step 4: Create missing __init__.py files -------------------------")
    for pkg in BACKEND_PACKAGES:
        path = ROOT / pkg / "__init__.py"
        touch(path)

# -- Step 5: Update .gitignore -------------------------------------------------

GITIGNORE_ADDITIONS = """
# === SC Results WF additions ===
# Database files - never commit
*.db
*.db-shm
*.db-wal

# Log files - never commit
*.log
*.log.old
ghost_all.log
import_debug.log
import_files_trace.log

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.eggs/

# Environment
.env
!.env.example

# IDE configs - local only
.bmad-core/
.claude/
.cursor/
.kiro/
.qodo/

# Test artifacts
.pytest_cache/
.coverage
htmlcov/
coverage.xml

# Frontend build
frontend/dist/
frontend/node_modules/
frontend/.env.local

# Archive (don't track debug scripts)
archive/

# Scratch artifacts
scratch_parser_test.db
rar_extract/
"""

def step5_update_gitignore() -> None:
    print("\n-- Step 5: Update .gitignore ----------------------------------------")
    gi_path = ROOT / ".gitignore"
    if gi_path.exists():
        existing = gi_path.read_text(encoding="utf-8")
    else:
        existing = ""

    additions = [
        line for line in GITIGNORE_ADDITIONS.splitlines()
        if line not in existing
    ]
    if additions:
        new_content = existing.rstrip() + "\n" + "\n".join(additions) + "\n"
        write_file(gi_path, new_content)
    else:
        log(".gitignore already up to date")

# ── Step 6: Create missing directory scaffolding ─────────────────────────────

REQUIRED_DIRS = [
    "backend/core", "backend/db", "backend/models", "backend/schemas",
    "backend/repositories", "backend/services/ingestion",
    "backend/services/analytics", "backend/services/walkforward",
    "backend/services/montecarlo", "backend/services/recommendation",
    "backend/services/statistical", "backend/api/v1/routes",
    "backend/utils", "tests/unit", "tests/integration", "tests/fixtures",
    "docs/audits", "docs/reports", "docs/examples",
    "data/samples", "infra/docker", "archive/debug_scripts",
    "scripts",
]

def step6_create_dirs() -> None:
    print("\n-- Step 6: Create missing directory scaffold ------------------------")
    for d in REQUIRED_DIRS:
        path = ROOT / d
        if not path.exists():
            if DRY_RUN:
                log(f"[DRY] MKDIR {d}/")
            else:
                path.mkdir(parents=True, exist_ok=True)
                log(f"MKDIR {d}/")

# ── Step 7: Generate Makefile ─────────────────────────────────────────────────

MAKEFILE_CONTENT = """\
# Makefile — Sierra Chart Trade Optimization Platform
# Usage: make <target>
# Requires: Python 3.11+, Node 18+, Docker

.PHONY: dev backend frontend test test-unit test-integration lint \\
        migrate migrate-rollback migrate-create \\
        docker-up docker-down docker-prod \\
        import walkforward permutation-test oos promote \\
        clean generate-types

# ── Development ──────────────────────────────────────────────────────────────

dev:
\t@echo "Starting backend + frontend..."
\t@start cmd /k "make backend"
\t@start cmd /k "make frontend"

backend:
\tcd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
\tcd frontend && npm run dev

# ── Testing ───────────────────────────────────────────────────────────────────

test:
\tpytest tests/ -v --cov=backend --cov-report=term-missing --cov-fail-under=70

test-unit:
\tpytest tests/unit/ -v

test-integration:
\tpytest tests/integration/ -v -x

# ── Linting ───────────────────────────────────────────────────────────────────

lint:
\tcd backend && python -m ruff check . && python -m mypy . --ignore-missing-imports
\tcd frontend && npm run lint

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
\tcd backend && alembic upgrade head

migrate-rollback:
\tcd backend && alembic downgrade -1

migrate-create:
\tcd backend && alembic revision --autogenerate -m "$(msg)"

# ── Pipeline Operations ───────────────────────────────────────────────────────

import:
\tpython scripts/run_full_import.py

walkforward:
\tpython scripts/run_walk_forward_test.py

permutation-test:
\tpython scripts/run_permutation_test.py

oos:
\tpython scripts/run_out_of_sample_audit.py

promote:
\tpython scripts/promote_clean_data_to_production.py

ingest:
\tcurl -X POST http://localhost:8000/api/v1/ingest -H "Content-Type: application/json" \\
\t  -d "{\\"data_dir\\": \\"$(DIR)\\"}"

# ── Frontend Tooling ──────────────────────────────────────────────────────────

generate-types:
\tcd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up:
\tdocker-compose -f infra/docker-compose.yml up --build

docker-down:
\tdocker-compose -f infra/docker-compose.yml down

docker-prod:
\tdocker-compose -f infra/docker-compose.prod.yml up -d

# -- Cleanup ------------------------------------------------------------------

clean:
\tfor /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
\tif exist .pytest_cache rd /s /q .pytest_cache
\tif exist backend\\.mypy_cache rd /s /q backend\\.mypy_cache
"""

def step7_generate_makefile() -> None:
    print("\n-- Step 7: Generate Makefile ----------------------------------------")
    write_file(ROOT / "Makefile", MAKEFILE_CONTENT)

# -- Main ---------------------------------------------------------------------

def main() -> None:
    print("=" * 65)
    print("SC Results WF - Phase 1 Repo Reorganization")
    if DRY_RUN:
        print("MODE: DRY RUN (no changes will be made)")
    print("=" * 65)

    step6_create_dirs()
    step1_archive_scripts()
    step2_move_docs()
    step3_rename_backend()
    step4_create_init_files()
    step5_update_gitignore()
    step7_generate_makefile()

    print("\n" + "=" * 65)
    print("Phase 1 complete. Next steps:")
    print("  1. Review archive/debug_scripts/ and delete if confirmed")
    print("  2. Run: python -m pytest tests/ to verify nothing broke")
    print("  3. Run: make migrate to initialize Alembic")
    print("  4. Commit: git add -A && git commit -m 'chore: Phase 1 monorepo restructure'")
    print("=" * 65)

if __name__ == "__main__":
    main()
