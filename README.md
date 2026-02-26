# 한국 계정으로 실행
poetry run python main.py --profile kr

# 일본 계정으로 실행
poetry run python main.py --profile jp

# 프로파일 목록 확인
poetry run python main.py --list-profiles

# --profile 없으면 .env 기본값 그대로 실행
poetry run python main.py