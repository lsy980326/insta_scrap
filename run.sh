#!/bin/bash
# Instagram Reels Scraper 실행 스크립트 (Linux/Mac)

echo "========================================"
echo "Instagram Reels Scraper 실행"
echo "========================================"
echo ""

# Poetry 가상 환경 확인
if ! command -v poetry &> /dev/null; then
    echo "[오류] Poetry가 설치되어 있지 않습니다."
    echo "pip install poetry 또는 pip install --user poetry 로 설치하세요."
    exit 1
fi

# Poetry로 실행
echo "Poetry 가상 환경에서 실행 중..."
poetry run python main.py

