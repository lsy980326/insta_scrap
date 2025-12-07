# Instagram Reels Scraper

인스타그램 릴스를 스크래핑하고 크롤링하는 엔터프라이즈급 Python 프로젝트입니다.

## ✨ 주요 특징

- 🏢 **엔터프라이즈급 안정성**: 타입 안전성, 예외 처리, 로깅 시스템
- 📦 **Poetry 기반**: 의존성 관리 및 프로젝트 빌드
- 🔒 **타입 안전성**: Pydantic을 사용한 데이터 검증
- 📝 **포괄적 로깅**: Loguru를 사용한 구조화된 로깅
- 🧪 **테스트 지원**: pytest 기반 테스트 프레임워크
- 🎯 **코드 품질**: Black, Ruff, MyPy를 사용한 코드 품질 관리

## 📋 수집 정보

- 썸네일
- 좋아요 수
- 댓글 수
- 작성자 이름
- 배경음악 정보
- 링크

> **참고**: 영상 파일은 수집하지 않습니다.

## 🚀 시작하기

### 사전 요구사항

- Python 3.10 이상
- Poetry (패키지 관리 도구)

### Poetry 설치

```bash
# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Linux/Mac
curl -sSL https://install.python-poetry.org | python3 -

# 또는 pip로 설치
pip install poetry
```

### 프로젝트 설정

1. **의존성 설치**

```bash
poetry install

# Playwright 브라우저 설치 (필수)
poetry run playwright install
```

2. **가상 환경 활성화**

```bash
poetry shell
```

3. **환경 변수 설정**

`.env` 파일을 생성하고 설정을 추가하세요:

```bash
cp env.example .env
# .env 파일을 편집하여 설정 추가
```

4. **실행**

```bash
# 방법 1: Windows 배치 파일 사용 (가장 간단)
run.bat

# 방법 2: 프로젝트 루트의 main.py 실행 (권장)
python -m poetry run python main.py

# 방법 3: 패키지로 실행
python -m poetry run python -m src

# 방법 4: Poetry 스크립트로 실행
python -m poetry run insta-scraper

# 방법 5: 가상 환경 활성화 후
python -m poetry shell
python main.py
```

**⚠️ 중요**: `python main.py`를 직접 실행하면 모듈을 찾을 수 없습니다. 반드시 Poetry를 통해 실행하세요!

## 📁 프로젝트 구조

```
insta_scrap/
├── src/
│   ├── __init__.py
│   ├── main.py              # 메인 실행 파일
│   ├── scraper.py           # 스크래퍼 클래스
│   ├── config.py            # 설정 관리 (Pydantic)
│   ├── models.py            # 데이터 모델 (Pydantic)
│   ├── exceptions.py        # 커스텀 예외 클래스
│   └── utils/
│       ├── __init__.py
│       └── logger.py        # 로깅 유틸리티
├── tests/                   # 테스트 코드
│   ├── __init__.py
│   └── test_scraper.py
├── .workflow/               # 워크플로우 문서
├── pyproject.toml          # Poetry 설정 파일
├── .pre-commit-config.yaml  # Pre-commit 훅 설정
├── README.md               # 프로젝트 설명
└── .gitignore              # Git 제외 파일
```

## ⚙️ 설정

### 환경 변수

`.env` 파일을 생성하여 다음 설정을 추가할 수 있습니다:

```env
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
HASHTAG=#your_hashtag
OUTPUT_DIR=output
OUTPUT_FORMAT=json
LOG_LEVEL=INFO
```

### 설정 옵션

- `INSTAGRAM_USERNAME`: 인스타그램 사용자명
- `INSTAGRAM_PASSWORD`: 인스타그램 비밀번호
- `HASHTAG`: 해시태그 (예: #fitness)
- `TARGET_URL`: 특정 릴스 URL
- `OUTPUT_DIR`: 출력 디렉토리 (기본값: output)
- `OUTPUT_FORMAT`: 출력 형식 (json, csv)
- `PLAYWRIGHT_HEADLESS`: 헤드리스 모드 (기본값: true)
- `PLAYWRIGHT_TIMEOUT`: 타임아웃 밀리초 (기본값: 30000)
- `PLAYWRIGHT_BROWSER`: 브라우저 타입 (chromium, firefox, webkit, 기본값: chromium)
- `MAX_REELS`: 최대 수집 개수
- `REQUEST_DELAY`: 요청 간 딜레이 초 (기본값: 2.0)
- `LOG_LEVEL`: 로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FILE`: 로그 파일 경로

## 🛠️ 개발

### 코드 포맷팅

```bash
# Black으로 포맷팅
poetry run black src tests

# Ruff로 린팅
poetry run ruff check src tests
poetry run ruff check --fix src tests

# MyPy로 타입 체크
poetry run mypy src
```

### 테스트 실행

```bash
# 모든 테스트 실행
poetry run pytest

# 커버리지 포함
poetry run pytest --cov=src --cov-report=html

# 특정 테스트만 실행
poetry run pytest tests/test_scraper.py
```

### Pre-commit 훅 설정

```bash
poetry run pre-commit install
```

## 📦 의존성 관리

### 의존성 추가

```bash
# 프로덕션 의존성
poetry add package-name

# 개발 의존성
poetry add --group dev package-name
```

### 의존성 업데이트

```bash
poetry update
```

### 의존성 확인

```bash
poetry show
poetry show --tree
```

## 🔧 사용 예시

```python
from src.config import load_config
from src.scraper import InstagramReelsScraper

# 설정 로드
config = load_config()

# 스크래퍼 생성
scraper = InstagramReelsScraper(config=config)

# 로그인
scraper.login()

# 스크래핑
reels = scraper.scrape_reels(hashtag="#fitness", max_reels=10)

# JSON으로 저장
scraper.save_to_json(reels, "fitness_reels.json")

# CSV로 저장
scraper.save_to_csv(reels, "fitness_reels.csv")
```

## 📝 개발 가이드

이 프로젝트는 맥도날드식 워크플로우를 사용합니다. 작업 전 `.workflow/START_HERE.md`를 확인하세요.

## 🧪 테스트

```bash
# 모든 테스트 실행
poetry run pytest

# 커버리지 리포트 생성
poetry run pytest --cov=src --cov-report=html

# 특정 마커로 테스트 실행
poetry run pytest -m unit
poetry run pytest -m integration
```

## 📚 참고 문서

- `.workflow/START_HERE.md` - 시작 가이드
- `.workflow/Agents.md` - AI 에이전트 가이드라인
- `.workflow/pr-guide.md` - PR 가이드
- `.workflow/domain-scraping.md` - 스크래핑 도메인 문서

## ⚠️ 주의사항

- 인스타그램의 이용약관을 준수해야 합니다
- 과도한 요청은 IP 차단을 유발할 수 있으므로 적절한 딜레이를 설정하세요
- 로그인 정보는 안전하게 관리하세요 (환경 변수 사용 권장)

## 📄 라이선스

이 프로젝트는 개인 사용 목적으로 개발되었습니다.
