@echo /off
cd /d "%~dp0"
python test_resolve.py -v
exit /b %ERRORLEVEL%
