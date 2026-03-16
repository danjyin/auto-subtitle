@echo off
:: Auto Screen Subtitle launcher
:: A dialog will appear on startup to pick language and scan area.

echo Starting Auto Screen Subtitle...
echo A settings dialog will open. Choose your language and click Start.
echo Press Escape or right-click the bar to quit.
echo.

python translator.py
pause
