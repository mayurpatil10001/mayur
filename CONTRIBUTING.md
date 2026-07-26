# Contributing to Sierra Chart Trade Optimization Platform

Thank you for contributing! This document details environment setup, branch naming, commit standards, and PR requirements.

---

## Branch Naming & Commit Convention

Follow **Conventional Commits**:
- `feat: add new API endpoint for account risk metrics`
- `fix: correct BH-FDR threshold comparison in time_bin_analyzer`
- `chore: update dependencies and Docker multi-stage build`
- `refactor: clean up backend session dependency`
- `docs: update API reference table in README`

Branch naming format: `feature/<short-desc>`, `bugfix/<issue-desc>`, or `chore/<topic>`.

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
   ```

3. **Backend setup (Python 3.11+):**
   ```bash
   pip install -r backend/requirements.txt
   pip install ruff mypy pytest pytest-cov
   ```

4. **Frontend setup (Node 18+):**
   ```bash
   cd frontend
   npm ci
   ```

---

## Standard Makefile Commands

```bash
make dev         # Run backend + frontend concurrently
make test        # Run unit & integration test suite
make lint        # Run ruff + mypy + eslint
make docker-up   # Launch containerized stack
```

---

## PR Checklist

- [ ] All unit and integration tests pass (`make test`).
- [ ] No linter or type-checker warnings (`make lint`).
- [ ] Added unit test for any core logic modification.
- [ ] Verified `.env` and `*.db` files are ignored by git.

