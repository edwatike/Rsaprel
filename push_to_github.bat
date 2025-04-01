@echo off
echo Pushing files to GitHub...
git add rss_bot.py
git commit -m "Auto-update %date% %time%"
git push origin main
echo Done!
pause
