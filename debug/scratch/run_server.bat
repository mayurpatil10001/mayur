@echo off
set PYTHONPATH=.
python -m uvicorn trading_platform.api.main:create_app --factory --host 0.0.0.0 --port 8000
