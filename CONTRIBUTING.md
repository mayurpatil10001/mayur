# Contributing to Sierra Chart Trade Optimization Platform

Thank you for your interest in contributing. This document explains how to set up your environment, run tests, and submit changes.

---

## Setting Up Your Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mayurpatil10001/mayur.git
   cd mayur
   ```

2. **Copy the environment template:**
   ```bash
   cp .env.example .env
   # Edit .env with your local paths if needed
   ```

3. **Install Python dependencies (Python 3.11+ required):**
   ```bash
   pip install -r requirements.txt
   pip install pytest flake8 ruff
   ```

4. **Start the backend:**
   ```bash
   python main.py
   ```
   API available at `http://localhost:8000/docs`.

5. **Start the frontend (Node 18+ required):**
   ```bash
   cd frontend
   npm install
   npm start
   ```
   Dashboard at `http://localhost:3000`.

---

## Running Tests

```bash
# Run the full test suite
pytest tests/ --ignore=tests/old_unused_tests/ --ignore=tests/ui/ -v

# Run only fast unit tests
pytest tests/test_binary_parser.py tests/test_bh_correction.py tests/test_open_close_pairing.py -v

# Run the out-of-sample audit (requires trading_platform.db to exist)
python scripts/run_out_of_sample_audit.py
```

---

## Code Style

- **Python formatter:** `ruff format trading_platform/ scripts/`
- **Linter:** `ruff check trading_platform/ scripts/ --ignore E501`
- **Max line length:** 130 characters

---

## Contribution Rules

1. **Never commit `.env` or any file containing real credentials.** The `.gitignore` enforces this, but please double-check.
2. **Never commit `dataset/` or `*.db` files.** These contain private trading data.
3. **For any change to `trading_platform/services/binary_log_parser.py`**, add or update a unit test in `tests/test_binary_parser.py` that covers your change.
4. **For any change to `trading_platform/services/time_bin_analyzer.py`** (BH-FDR logic), add a test in `tests/test_bh_correction.py`.
5. **All PRs must pass CI** (GitHub Actions runs lint + tests automatically on push).
6. **Statistical validity:** Do not introduce any code path that allows the test window (`2025-01-01` onwards) to influence slot selection criteria. The test window is used for evaluation only.

---

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes with clear, descriptive commits.
3. Ensure `pytest tests/` passes locally before pushing.
4. Open a PR with a description explaining: what changed, why, and how you verified it.

---

## Reporting Issues

Open a GitHub Issue with:
- A clear description of the bug or feature request.
- Steps to reproduce (if a bug).
- The relevant account/symbol/date range if it is a data issue.
- **Do not include raw trade data or account identifiers in issues.**
