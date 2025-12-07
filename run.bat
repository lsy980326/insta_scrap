@echo off
REM Instagram Reels Scraper 실행 스크립트 (Windows)
echo ========================================
echo Instagram Reels Scraper 실행
echo ========================================
echo.

REM Poetry 가상 환경 확인
python -m poetry --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Poetry가 설치되어 있지 않습니다.
    echo pip install poetry 또는 pip install --user poetry 로 설치하세요.
    pause
    exit /b 1
)

REM Poetry로 실행
echo Poetry 가상 환경에서 실행 중...
python -m poetry run python main.py

pause

