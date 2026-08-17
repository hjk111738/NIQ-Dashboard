@echo off
chcp 65001 > nul
title 롯데웰푸드 마켓 인텔리전스 대시보드 서버

echo ======================================================
echo    📊 롯데웰푸드 마켓 인텔리전스 대시보드를 실행합니다
echo ======================================================
echo.

:: 1. 현재 배치 파일이 위치한 폴더로 작업 경로 이동
cd /d "%~dp0"

:: 2. 기본 브라우저로 대시보드 URL 2초 후 자동 열기 (백그라운드 실행)
start "" cmd /c "timeout /t 2 /nobreak > nul & start http://127.0.0.1:8000"

:: 3. FastAPI Uvicorn 서버 실행
echo [서버 구동 중...] 창을 닫으면 대시보드가 종료됩니다.
echo 접속 주소: http://127.0.0.1:8000
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8000

pause