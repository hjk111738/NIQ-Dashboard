@echo off
title Dashboard Auto Update

echo ======================================================
echo    Dashboard Auto Update Process
echo ======================================================
echo.

git status
echo.

set /p commit_msg="Enter commit message (Press Enter for default): "

if "%commit_msg%"=="" (
    set commit_msg=Update dashboard data and codes
)

git add .
git commit -m "%commit_msg%"
git push origin main

echo.
echo ======================================================
echo    Upload Complete! (Render updates in 1-2 mins)
echo ======================================================
echo.
pause