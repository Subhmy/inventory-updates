@echo off
title 📊 ALL DASHBOARDS UPDATER
color 0A

echo ========================================
echo    UPDATING ALL DASHBOARDS
echo ========================================
echo.

cd /d D:\inventory-updates
call venv\Scripts\activate

:: Install packages if needed
pip install --quiet pandas pymongo python-dotenv requests

echo.
echo ========================================
echo [1/3] 🏭 33/11kV Sub-Station Dashboard
echo ========================================
python update_substation_33_11kv.py
echo.

echo ========================================
echo [2/3] ⚡ 33kV Line Dashboard
echo ========================================
python update_line_33kv.py
echo.

echo ========================================
echo [3/3] 🔌 11kV Line Dashboard
echo ========================================
python update_line_11kv.py
echo.

echo ========================================
echo ✅ ALL DASHBOARDS UPDATED SUCCESSFULLY!
echo ========================================
echo 📅 Completed at: %date% %time%
pause