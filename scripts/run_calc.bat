@echo off
if exist "C:\SierraChart\SC results WF\trading_platform\services\__pycache__" (
    echo Clearing pycache...
    rmdir /s /q "C:\SierraChart\SC results WF\trading_platform\services\__pycache__"
)
echo Running calculation script...
python "C:\SierraChart\SC results WF\calc_bad_pnl.py"
