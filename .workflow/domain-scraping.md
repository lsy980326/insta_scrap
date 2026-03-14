# 스크래핑 도메인 구조 문서

인스타그램 릴스 스크래핑 관련 API 및 구조를 문서화합니다.

## 📦 모듈 위치

- `src/scraper.py` - 인스타그램 릴스 스크래퍼 메인 클래스
- `src/shortrend_scraper.py` - 숏트렌드 스크래퍼 메인 클래스
- `src/views_tracker.py` - 릴스 조회수 추적 클래스
- `src/browser.py` - Playwright 브라우저 관리 클래스
- `src/main.py` - 메인 실행 파일
- `src/config.py` - 설정 관리
- `src/models.py` - 데이터 모델 (ReelData, ShortrendReelData)
- `track_views.py` - 조회수 추적 실행 스크립트
- `src/database/` - 데이터베이스 모듈
  - `connection.py` - PostgreSQL 연결 관리
  - `models.py` - SQLAlchemy ORM 모델 (Creator, Reel, ReelMetric, ScrapingSession). Reel에 country_code(계정/프로파일 기준) 포함.
  - `repositories/` - Repository 패턴 구현
    - `reel_repository.py` - 릴스 데이터 접근
    - `creator_repository.py` - 크리에이터 데이터 접근
    - `session_repository.py` - 세션 추적
- `src/profile_loader.py` - 프로파일 로더 (accounts.yaml 기반 계정별 설정)
- `main.py` (루트) - 실행 진입점 (`--profile`, `--list-profiles` 지원)
- `accounts.yaml` - 계정별 프로파일 정의 (kr, jp 등 지역/로케일/출력 경로)

## 프로파일 및 로케일

- **실행**: `poetry run python main.py --profile kr` / `--profile jp` / `--list-profiles`
- **accounts.yaml**: 프로파일별 `account_id`, `instagram_username`, `instagram_password`, `output_dir`, `browser_locale`, `browser_timezone` 등
- **로케일**: `.env` 또는 프로파일에서 `BROWSER_LOCALE`(예: `ja-JP`), `BROWSER_TIMEZONE`(예: `Asia/Tokyo`) 설정 시 브라우저 언어·타임존 적용
- **설정 우선순위**: 프로파일 오버라이드 → `.env` → 기본값

## 🔌 주요 API

### InstagramReelsScraper 클래스

#### 초기화

```python
InstagramReelsScraper(
    config: Optional[ScrapingConfig] = None,
    username: Optional[str] = None,
    password: Optional[str] = None
)
```

- 인스타그램 스크래퍼 인스턴스 생성
- `config`: 스크래핑 설정 객체 (선택, 없으면 기본값 사용)
- `username`: 인스타그램 사용자명 (선택, config보다 우선)
- `password`: 인스타그램 비밀번호 (선택, config보다 우선)
- 출력 디렉토리 자동 생성

#### 로그인

```python
login(username: Optional[str] = None, password: Optional[str] = None) -> bool
```

- 인스타그램에 로그인
- `username`: 인스타그램 사용자명 (None이면 기존 값 사용)
- `password`: 인스타그램 비밀번호 (None이면 기존 값 사용)
- 로그인 성공 여부 반환
- 브라우저 자동 시작 (아직 시작되지 않은 경우)
- 디버깅용 HTML/스크린샷 자동 저장
- **로그인 프로세스**:
  1. 로그인 폼 대기 (신규 인스타: `input[name="email"]`, `input[name="pass"]` 또는 기존 `#loginForm`)
  2. 로그인 버튼 클릭 (한국어 "로그인", 일본어 "ログイン", 영어 "Log in" 등 지원)
  3. 20초 대기 (로그인 처리 대기)
  4. 팝업 처리
  5. 로그인 상태 검증 (리다이렉트 감지)
  6. 홈 탭으로 이동
  7. 릴스 탭으로 이동
- **에러 처리**: 로그인 페이지로 리다이렉트되면 `LoginError` 발생
- **세션**: 파일 세션 사용 시 검증 URL은 계정이 이메일이면 `@` 앞 username만 사용 (예: `cxv963@naver.com` → `/cxv963/`)

#### 스크래핑

```python
scrape_reels(
    hashtag: Optional[str] = None,
    url: Optional[str] = None,
    max_reels: Optional[int] = None
) -> list[ReelData]
```

- 릴스 스크래핑 실행
- `hashtag`: 해시태그로 검색 (예: "#fitness")
- `url`: 특정 릴스 URL로 스크래핑
- `max_reels`: 최대 수집 개수
- 반환: `ReelData` 객체 리스트

#### 데이터 추출

```python
_extract_current_reel_data(page: Page) -> Optional[ReelData]
```

- 현재 페이지에서 릴스 데이터 추출
- `page`: Playwright Page 객체
- 반환: `ReelData` 객체 또는 None
- **네트워크 응답 기반 추출**:
  - Instagram GraphQL/API 응답을 가로채서 데이터 추출
  - Global Cache (`_reels_cache`)에서 데이터 조회
  - Retry 메커니즘: 데이터가 없으면 최대 5초 대기
- **추출 데이터**:
  - 썸네일, 좋아요, 댓글, 조회수, 게시일자, 작성자, 제목, 음악, 링크

#### 데이터 저장

```python
save_to_json(
    data: list[ReelData],
    filename: Optional[str] = None,
    db_only_new_count: Optional[int] = None,
) -> Path
save_to_csv(data: list[ReelData], filename: Optional[str] = None) -> Path
```

- 스크래핑한 데이터를 파일로 저장
- `data`: 저장할 `ReelData` 객체 리스트
- `filename`: 파일명 (None이면 타임스탬프 자동 생성)
- `db_only_new_count`: 지정 시 DB에는 `data[db_only_new_count:]`만 전달 (reel_metrics 중복 방지). 수집 루프 내 주기 저장 시 사용.
- 반환: 저장된 파일 경로
- JSON/CSV 형식 지원
- **데이터베이스 저장**: `DB_ENABLED=true` 설정 시 자동으로 PostgreSQL에 저장 (중복 체크 포함). 프로파일(계정) 기준 `reels.country_code` 저장. 주기 저장 시 신규 수집 구간만 DB에 넣어 `reel_metrics` 중복 삽입 방지.
- **크리에이터/썸네일**: 로케일 독립적 추출(href 기반) 및 한국어/일본어/영어 aria-label·alt 지원. 네트워크 응답 캐시에서 thumbnail·author·profile_image fallback (DOM 갱신 지연 시 썸네일 중복 방지).

#### 중복 감지 (수집 루프)

- **reel_id 기준**: reel_id가 정상 추출된 경우에는 reel_id로만 중복 판단 (썸네일 URL로 중복 체크하지 않음, UI 공통 이미지 false positive 방지)
- **썸네일 기준**: reel_id가 없을 때만 썸네일 URL로 중복 여부 확인
- **연속 중복 종료**: 연속 N개(기본 10) 중복 시 수집 루프 종료 (`max_consecutive_duplicates`)

### BrowserManager 클래스

브라우저 자동화 관리를 담당하는 클래스

#### 초기화

```python
BrowserManager(config: ScrapingConfig)
```

- 브라우저 관리자 인스턴스 생성
- 설정 객체를 통한 브라우저 옵션 구성

#### 주요 메서드

```python
start() -> None  # 브라우저 시작
get_page() -> Page  # 페이지 객체 가져오기
close() -> None  # 브라우저 종료
```

## 🏗️ 컴포넌트 구조

```
InstagramReelsScraper
├── __init__()                      # 초기화
├── login()                         # 로그인 처리 (세션 관리 포함)
├── start_collecting_reels()        # 메인 수집 로직
├── _register_global_network_listener()  # 네트워크 리스너 등록
├── _handle_network_response()      # 네트워크 응답 처리
├── _parse_and_cache_reels()        # 응답 파싱 및 캐시 저장
├── _extract_current_reel_data()   # 현재 릴스 데이터 추출
├── _save_to_db()                   # 데이터베이스 저장
├── _print_reel_summary()           # 수집 데이터 요약 출력
├── save_to_json()                  # JSON 파일로 저장
└── save_to_csv()                   # CSV 파일로 저장

BrowserManager
├── __init__()           # 초기화
├── start()              # 브라우저 시작
├── get_page()           # 페이지 객체 가져오기
└── close()              # 브라우저 종료
```

## 🔄 데이터 흐름

```
1. InstagramReelsScraper 인스턴스 생성
   ↓
2. login() - 인스타그램 로그인 (세션 관리 포함)
   ↓
3. start_collecting_reels() - 릴스 수집 시작
   ↓
4. _register_global_network_listener() - 네트워크 응답 리스너 등록
   ↓
5. _handle_network_response() - GraphQL/API 응답 가로채기
   ↓
6. _parse_and_cache_reels() - 응답에서 릴스 데이터 추출 및 캐시 저장
   ↓
7. _extract_current_reel_data() - 현재 릴스 데이터 추출 (캐시에서 조회)
   ↓
8. _save_to_db() - 데이터베이스 저장 (중복 체크 포함)
   ↓
9. save_to_json() - 결과를 JSON 파일로 저장
```

## 📊 수집 데이터 구조

### ReelData 모델 (Pydantic BaseModel)

각 릴스에서 수집하는 정보:

- **thumbnail** (`Optional[str]`): 썸네일 이미지 URL
- **likes** (`Optional[int]`): 좋아요 수 (0 이상)
- **comments** (`Optional[int]`): 댓글 수 (0 이상)
- **views** (`Optional[int]`): 조회수 (0 이상)
- **posted_date** (`Optional[str]`): 게시일자 (ISO 8601 형식)
- **author** (`Optional[str]`): 작성자 사용자명 (검증: 빈 문자열은 None으로 변환)
- **creator_profile_image** (`Optional[str]`): 크리에이터 프로필 이미지 URL
- **title** (`Optional[str]`): 릴스 제목/캡션
- **music** (`Optional[str]`): 배경음악 정보 (곡명, 아티스트 등)
- **link** (`Optional[HttpUrl]`): 릴스 URL (Pydantic HttpUrl 타입)

> **참고**: 영상 파일은 수집하지 않습니다.

모든 필드는 선택적(Optional)이며, Pydantic을 통한 타입 안전성 보장

## 🎯 사용 예시

### 기본 사용법

```python
from src.config import load_config
from src.profile_loader import load_profile
from src.scraper import InstagramReelsScraper

# 프로파일로 설정 로드 (예: kr, jp)
config = load_profile("jp")  # 또는 load_config()로 .env만 사용

# 스크래퍼 생성
scraper = InstagramReelsScraper(config=config)

# 로그인 (필요한 경우)
scraper.login()

# 해시태그로 스크래핑
reels = scraper.scrape_reels(hashtag="#fitness", max_reels=10)

# 또는 특정 URL로 스크래핑
reels = scraper.scrape_reels(url="https://www.instagram.com/reel/...")

# JSON으로 저장
scraper.save_to_json(reels, "fitness_reels.json")

# CSV로 저장
scraper.save_to_csv(reels, "fitness_reels.csv")
```

### CLI 실행 (프로파일)

```bash
# 프로파일 목록
poetry run python main.py --list-profiles

# 한국 계정(kr)으로 실행
poetry run python main.py --profile kr

# 일본 계정(jp)으로 실행
poetry run python main.py --profile jp
```

### 설정 파일 사용

```python
# .env 파일에 설정
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
OUTPUT_DIR=output
LOG_LEVEL=INFO
PLAYWRIGHT_HEADLESS=true

# 코드
from src.scraper import InstagramReelsScraper

scraper = InstagramReelsScraper()
scraper.login()
reels = scraper.scrape_reels(hashtag="#fitness")
```

## 🔌 ShortrendScraper 클래스

숏트렌드(Shortrend) 사이트에서 릴스 데이터를 수집하는 스크래퍼

### 초기화

```python
ShortrendScraper(
    config: Optional[ScrapingConfig] = None,
    email: Optional[str] = None,
    password: Optional[str] = None
)
```

- 숏트렌드 스크래퍼 인스턴스 생성
- `config`: 스크래핑 설정 객체 (선택, 없으면 기본값 사용)
- `email`: 숏트렌드 이메일 (선택, config보다 우선)
- `password`: 숏트렌드 비밀번호 (선택, config보다 우선)

### 로그인

```python
login(email: Optional[str] = None, password: Optional[str] = None) -> bool
```

- 숏트렌드에 로그인
- 로그인 후 자동으로 필터 설정 (날짜: 오늘, 새 영상만 보기: 활성화)
- 로그인 성공 여부 반환
- 브라우저 자동 시작 (아직 시작되지 않은 경우)

### 릴스 수집

```python
collect_reels(max_count: int = 100) -> list[ShortrendReelData]
```

- 무한 스크롤로 릴스 데이터 수집
- `max_count`: 최대 수집 개수 (기본: 100)
- 반환: `ShortrendReelData` 객체 리스트
- 중복 제거 (썸네일 URL 기반)

### 데이터 저장

```python
save_to_json(data: list[ShortrendReelData], filename: Optional[str] = None) -> Path
```

- 스크래핑한 데이터를 JSON 파일로 저장
- `data`: 저장할 `ShortrendReelData` 객체 리스트
- `filename`: 파일명 (None이면 타임스탬프 자동 생성)
- 반환: 저장된 파일 경로

### 브라우저 제어

```python
keep_browser_open() -> None  # 브라우저를 열어둔 상태로 유지
close() -> None  # 브라우저 종료
```

## 📊 ShortrendReelData 모델 (Pydantic BaseModel)

숏트렌드에서 수집하는 릴스 정보:

- **기본 정보**
  - `thumbnail_url`: 썸네일 이미지 URL
  - `video_url`: 비디오 URL (현재 추출하지 않음)
  - `instagram_link`: Instagram 게시물 링크

- **랭킹 정보**
  - `rank`: 랭킹 텍스트 (예: "TOP 1")
  - `rank_number`: 랭킹 번호
  - `date`: 릴스 날짜 (예: "12월 14일")
  - `growth_rate`: 증가율 (예: "+999%")

- **통계 정보**
  - `views`, `likes`, `comments`: 조회수, 좋아요 수, 댓글 수
  - `views_daily_change`, `views_weekly_change`: 조회수 일일/주간 변화율
  - `likes_daily_change`, `likes_weekly_change`: 좋아요 일일/주간 변화율
  - `comments_daily_change`, `comments_weekly_change`: 댓글 일일/주간 변화율

- **작성자 정보**
  - `author_username`: 작성자 사용자명 (예: "@moon_tae_hwan")
  - `author_display_name`: 작성자 표시 이름 (예: "문태환")
  - `author_followers`: 작성자 팔로워 수

- **콘텐츠 정보**
  - `title`: 릴스 제목/캡션
  - `duration`: 영상 길이 (예: "0:11")

모든 필드는 선택적(Optional)이며, Pydantic을 통한 타입 안전성 보장

## 🎯 ShortrendScraper 사용 예시

```python
from src.config import ScrapingConfig
from src.shortrend_scraper import ShortrendScraper

# 설정 로드
config = ScrapingConfig()

# 스크래퍼 생성
scraper = ShortrendScraper(config=config)

# 로그인 (필터 설정 자동 완료)
scraper.login()

# 릴스 수집
reels = scraper.collect_reels(max_count=100)

# JSON으로 저장
filepath = scraper.save_to_json(reels)
print(f"데이터 저장 완료: {filepath}")

# 브라우저 닫기
scraper.close()
```

### 설정 파일 사용

```python
# .env 파일에 설정
SHORTREND_EMAIL=your_email@example.com
SHORTREND_PASSWORD=your_password

# 코드
from src.shortrend_scraper import ShortrendScraper

scraper = ShortrendScraper()
scraper.login()
reels = scraper.collect_reels(max_count=100)
```

## 🔌 ReelViewsTracker 클래스

수집된 릴스 데이터에 조회수, 좋아요, 댓글 수를 추가하는 추적 모듈

### 초기화

```python
ReelViewsTracker(config: Optional[ScrapingConfig] = None)
```

- 통계 추적 인스턴스 생성
- `config`: 스크래핑 설정 객체 (선택, 없으면 기본값 사용)
- 출력 디렉토리 자동 생성
- SessionManager 통합 (세션 쿠키 관리)

### 로그인

```python
login(username: Optional[str] = None, password: Optional[str] = None) -> bool
```

- 인스타그램에 로그인 (세션 관리 포함)
- `username`: 인스타그램 사용자명 (None이면 config에서 가져옴)
- `password`: 인스타그램 비밀번호 (None이면 config에서 가져옴)
- 로그인 성공 여부 반환
- **세션 관리 플로우**:
  1. 저장된 세션(쿠키 + User-Agent) 로드 시도
  2. 세션이 있으면 브라우저에 설정하고 검증
  3. 세션이 유효하면 로그인 완료 (전체 로그인 생략)
  4. 세션이 없거나 무효하면 전체 로그인 진행
  5. 로그인 성공 후 세션 저장
- 브라우저 자동 시작 (아직 시작되지 않은 경우)

### 통계 추적

```python
track_views(input_file: Path, output_file: Optional[Path] = None) -> Path
```

- 수집된 릴스 데이터에 조회수, 좋아요, 댓글 수 추가
- `input_file`: 입력 JSON 파일 경로 (수집된 릴스 데이터)
- `output_file`: 출력 JSON 파일 경로 (None이면 자동 생성)
- 반환: 출력 파일 경로
- 크리에이터별로 그룹화하여 reels 페이지 접근
- 무한 스크롤 지원 (최대 5번 스크롤)
- **HTML 구조 기반 추출**:
  - `div._aaj-` 내부의 `ul > li`에서 좋아요(첫 번째), 댓글(두 번째) 추출
  - `div._aaj_` 내부의 조회수 아이콘 옆 숫자 추출
- 통계 추출 실패 시에도 계속 진행
- **데이터베이스 업데이트**: `DB_ENABLED=true` 설정 시 자동으로 PostgreSQL에 조회수, 좋아요, 댓글 수 업데이트됨 (시계열 통계 기록)
- **성능 최적화**: 대기 시간 단축으로 약 30-40% 속도 향상

### 브라우저 제어

```python
close() -> None  # 브라우저 종료
```

## 📊 ReelData 모델

`ReelData` 모델의 통계 필드:

- **views** (`Optional[int]`): 조회수 (0 이상)
- **likes** (`Optional[int]`): 좋아요 수 (0 이상)
- **comments** (`Optional[int]`): 댓글 수 (0 이상)

> **참고**: 추적 모듈(`ReelViewsTracker`)은 조회수, 좋아요, 댓글 수를 모두 추출하여 업데이트합니다.

## 🎯 ReelViewsTracker 사용 예시

```python
from pathlib import Path
from src.config import load_config
from src.views_tracker import ReelViewsTracker

# 설정 로드
config = load_config()

# 트래커 생성
tracker = ReelViewsTracker(config=config)

# 로그인 (선택)
tracker.login()

# 조회수 추적 실행
input_file = Path("output/reels_data_20260101_143155.json")
result_file = tracker.track_views(input_file)

print(f"결과 파일: {result_file}")

# 브라우저 닫기
tracker.close()
```

### 명령행 실행

```bash
# Poetry 사용
poetry run python track_views.py output/reels_data_20260101_143155.json

# 출력 파일 지정
poetry run python track_views.py input.json output.json
```

## ⚠️ 주의사항

- 인스타그램의 이용약관을 준수해야 합니다
- 숏트렌드의 이용약관을 준수해야 합니다
- 과도한 요청은 IP 차단을 유발할 수 있으므로 적절한 딜레이를 설정하세요
- 로그인 정보는 안전하게 관리하세요 (환경 변수 또는 설정 파일 사용)

## 🔗 관련 문서

- `src/scraper.py` - InstagramReelsScraper 실제 구현 코드
- `src/shortrend_scraper.py` - ShortrendScraper 실제 구현 코드
- `src/views_tracker.py` - ReelViewsTracker 실제 구현 코드
- `src/main.py` - 실행 예시
- `track_views.py` - 조회수 추적 실행 스크립트
- `test_shortrend.py` - ShortrendScraper 테스트 스크립트
- `env.example` - 설정 파일 예시

