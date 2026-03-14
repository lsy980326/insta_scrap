# 작업 이력 기록

이 문서는 프로젝트의 주요 작업 이력을 시간순으로 기록합니다.

---

### 2025-12-31 컨텍스트 엔지니어링 및 맥도날드식 워크플로우 구축

**요청**:

- AI 에이전트가 효율적으로 작업할 수 있도록 문서 구조화
- 맥도날드식 워크플로우 시스템 구축
- 도메인별 구조 문서 작성
- 컨텍스트 엔지니어링 가이드 작성

**구현 내용**:

#### 1. 워크플로우 문서 구조 구축

- `.workflow/` 디렉토리 생성 및 문서 구조화
- `START_HERE.md`: 빠른 시작 가이드
- `Agents.md`: AI 에이전트 가이드라인
- `workflow-checklist.md`: 작업 진행 상황 추적 체크리스트
- `COMMIT_MESSAGE.txt`: 커밋 메시지 템플릿

#### 2. 도메인별 구조 문서 작성

- `domain-scraping.md`: 스크래핑 도메인 API 및 구조
  - InstagramReelsScraper 클래스 API
  - ReelViewsTracker 클래스 API
  - 데이터 구조 및 흐름
  - 사용 예시
- `domain-web.md`: 웹 서비스 도메인 API 및 구조
  - Next.js 웹 서비스 API
  - 컴포넌트 구조
  - 데이터 흐름
  - 사용 예시

#### 3. 컨텍스트 엔지니어링 원칙 적용

- 문서 우선 접근 원칙
- 도메인별 구조화
- 필요한 정보만 효율적으로 수집
- 토큰 사용량 최적화
- 불필요한 파일 스캔 방지

**성과**:

- 맥도날드식 워크플로우 시스템 구축 완료
- AI 에이전트 가이드라인 문서화 완료
- 도메인별 구조 문서 작성 완료
- 컨텍스트 엔지니어링 원칙 적용
- 작업 추적 체크리스트 구축
- 커밋 메시지 템플릿 제공

---

### 2026-01-01 조회수 추적 모듈 구현

**요청**:

- 수집된 릴스 데이터에 조회수 추가 기능 구현
- 크리에이터별 reels 페이지에서 조회수 추출
- 무한 스크롤 지원 (최대 3번 스크롤)
- 로그인 기능 포함 (독립적인 로그인 프로세스)

**구현 내용**:

#### 1. ReelViewsTracker 클래스 구현 (`src/views_tracker.py`)

- 조회수 추적 전용 클래스
- 주요 메서드:
  - `__init__()`: 초기화 및 설정 로드
  - `login()`: 인스타그램 로그인 처리 (메인 페이지 → 로그인 링크 클릭 방식)
  - `track_views()`: 수집된 릴스 데이터에 조회수 추가
  - `_extract_views_from_creator_reels_page()`: 크리에이터별 reels 페이지에서 조회수 추출
  - `_extract_reel_id_from_link()`: 릴스 링크에서 reel ID 추출
  - `_parse_number()`: 숫자 파싱 (예: "502.9만" → 5029000)
  - `_handle_post_login_popup()`: 로그인 후 팝업 처리
  - `close()`: 브라우저 종료

#### 2. ReelData 모델 업데이트 (`src/models.py`)

- `views` 필드 추가: `Optional[int] = Field(default=None, ge=0, description="조회수")`
- 기존 필드와의 호환성 유지

#### 3. track_views.py 실행 스크립트 구현

- 명령행 인터페이스 제공
- 입력/출력 JSON 파일 지정 지원
- 자동 로그인 기능 (설정 파일 기반)
- 에러 처리 및 로깅

**성과**:

- 조회수 추적 모듈 구현 완료
- 독립적인 로그인 프로세스 구현 (scraper.py와 분리)
- 무한 스크롤 지원으로 더 많은 조회수 데이터 수집 가능
- 다양한 숫자 형식 파싱 지원
- 에러 처리 강화로 안정성 향상
- 코드 품질 개선 (PEP 8 준수, 린터 오류 없음)
- 문서 업데이트 완료 (domain-scraping.md에 ReelViewsTracker 추가)

---

### 2026-01-02 웹 서비스 구축 (Instagram Reels Ranking)

**요청**:

- DB에 있는 내용을 바탕으로 간단한 웹 서비스 구축
- 좋아요, 조회수 기준으로 랭킹 표시
- 카드 형태로 릴스 표시
- 클릭 시 추적된 내용(좋아요, 댓글, 조회수) 히스토리 표시
- Vercel에 무료로 배포 예정
- 등록 날짜 표시
- 날짜 범위로 검색 가능
- 일주일 단위로 끊어서 표시
- 프로필 이미지 표시 문제 해결

**구현 내용**:

#### 1. Next.js 프로젝트 구조 생성

- TypeScript, Tailwind CSS 설정
- Vercel 배포 설정 (`vercel.json`)
- Next.js 14 App Router 사용
- 이미지 최적화 설정 (Instagram CDN 도메인 허용)

#### 2. 데이터베이스 연결 설정

- PostgreSQL 연결 풀 설정 (`web/lib/db.ts`)
- SSL 연결 지원 (AWS RDS 등 클라우드 DB 대응)
- 환경 변수 기반 설정 (`.env.local`)

#### 3. API 라우트 구현

**랭킹 조회 API** (`/api/reels/ranking`):
- 조회수/좋아요 기준 정렬
- 날짜 범위 필터링 (startDate, endDate)
- 페이지네이션 지원 (limit, offset)
- 최신 메트릭과 함께 릴스 정보 반환

**메트릭 히스토리 API** (`/api/reels/[reelId]/metrics`):
- 특정 릴스의 시계열 통계 조회
- 최대 100개 기록 반환
- 시간순 정렬 (최신순)

**이미지 프록시 API** (`/api/image-proxy`):
- Instagram CDN 이미지 CORS 문제 해결
- 서버에서 이미지를 가져와 클라이언트에 전달
- 캐시 헤더 설정 (24시간)

#### 4. 프론트엔드 컴포넌트 구현

**ReelCard 컴포넌트**:
- 릴스 썸네일 표시
- 랭킹 배지 표시
- 조회수/좋아요 통계 오버레이
- 크리에이터 프로필 이미지 및 정보
- 등록 날짜 표시
- 프로필 이미지 로드 실패 시 대체 UI (사용자명 첫 글자)

**MetricModal 컴포넌트**:
- 릴스 상세 정보 표시
- 시계열 메트릭 히스토리 테이블
- 변화율 계산 및 색상 표시 (증가: 초록, 감소: 빨강)
- 인스타그램 링크 제공

**메인 페이지**:
- 조회수/좋아요 기준 정렬 버튼
- 날짜 범위 필터 (시작일/종료일)
- 일주일 단위 그룹화 표시
- 반응형 그리드 레이아웃
- 다크 테마 UI

#### 5. 기능 구현

**정렬 기능**:
- 조회수 기준 정렬
- 좋아요 기준 정렬
- 실시간 정렬 변경

**날짜 필터링**:
- 시작일/종료일 선택
- 날짜 범위 내 릴스만 표시
- 필터 초기화 버튼

**일주일 단위 그룹화**:
- 등록일 기준으로 주 단위 그룹화
- 주의 시작일(월요일) 기준
- 주별로 섹션 구분하여 표시
- 주별로 정렬 (최신순)

**프로필 이미지 처리**:
- Instagram CDN 이미지 CORS 문제 해결
- 이미지 프록시 API를 통한 표시
- 로드 실패 시 사용자명 첫 글자로 대체

**문제 해결**:

1. **PostgreSQL SSL 연결 문제**:
   - AWS RDS 등은 SSL 연결을 요구
   - 기본적으로 SSL 활성화하도록 수정
   - `DB_SSL=false`로 명시적으로 비활성화 가능

2. **프로필 이미지 CORS 오류**:
   - Instagram CDN 이미지는 직접 로드 불가 (`ERR_BLOCKED_BY_RESPONSE.NotSameOrigin`)
   - Next.js API 라우트를 통한 이미지 프록시 구현
   - 서버에서 이미지를 가져와 클라이언트에 전달

3. **프로필 이미지 로드 실패 처리**:
   - 이미지 로드 실패 시 엑스박스 대신 사용자명 첫 글자 표시
   - 일관된 UI 유지

**성과**:

- Next.js 기반 웹 서비스 구축 완료
- 데이터베이스 연결 및 API 구현 완료
- 랭킹 페이지 구현 완료 (조회수/좋아요 기준)
- 날짜 범위 검색 기능 구현 완료
- 일주일 단위 그룹화 구현 완료
- 등록 날짜 표시 구현 완료
- 프로필 이미지 표시 문제 해결 (CORS 우회)
- 반응형 디자인 구현
- 다크 테마 UI 구현
- Vercel 배포 준비 완료

---

### 2026-01-02 ~ 2026-01-07 데이터베이스 통합, 수집 모듈 복구 및 로그인 개선

**요청**:

- PostgreSQL 데이터베이스 통합
  - 수집 모듈(scraper.py)에서 DB 저장 기능 추가
  - 추적 모듈(views_tracker.py)에서 DB 업데이트 기능 추가
  - 중복 처리 (reel_id 기준)
  - 시계열 통계 추적 (reel_metrics)
- 수집 모듈 복구 (홈 탭 클릭 기능 추가)
- 로그인 리다이렉트 문제 해결
  - 로그인 후 홈 탭 클릭이 로그인 페이지로 리다이렉트되는 문제 해결
  - 로그인 성공 확인 로직 개선
- 웹 서비스 복구 (Next.js 기반 랭킹 페이지)

**구현 내용**:

#### 1. 데이터베이스 설계 및 구현

- PostgreSQL 스키마 설계:
  - `creators`: 크리에이터 정보 (username UNIQUE)
  - `reels`: 릴스 기본 정보 (reel_id UNIQUE, 중복 체크 기준)
  - `reel_metrics`: 통계 정보 시계열 추적 (views, likes, comments, recorded_at)
  - `scraping_sessions`: 수집 세션 추적 (session_type, status, total_reels)
- SQLAlchemy ORM 모델 구현 (`src/database/models.py`):
  - `Creator`, `Reel`, `ReelMetric`, `ScrapingSession` 모델 정의
  - 관계 설정 (Creator ↔ Reel, Reel ↔ ReelMetric)
- Repository 패턴 구현:
  - `ReelRepository`: 릴스 데이터 CRUD, 중복 체크, 통계 추가
  - `CreatorRepository`: 크리에이터 데이터 CRUD
  - `ScrapingSessionRepository`: 세션 추적 (생성, 상태 업데이트, 종료)
- 데이터베이스 연결 관리 (`src/database/connection.py`):
  - 연결 풀링 지원 (pool_size, max_overflow)
  - 자동 재연결 기능
  - 세션 생성 및 관리

#### 2. 수집 모듈 통합 및 복구

- `_save_to_db()` 메서드 추가 (`src/scraper.py`):
  - 릴스 수집 시 자동 DB 저장
  - 크리에이터 저장/업데이트
  - 릴스 저장/업데이트 (reel_id 기준 중복 체크)
  - 통계 정보 추가 (좋아요, 댓글, 조회수)
- 로그인 프로세스 개선:
  - 로그인 후 20초 대기 후 홈 탭 클릭 기능 추가 (`_navigate_to_home_tab()`)
  - 로그인 리다이렉트 감지 및 에러 처리 강화
  - 팝업 처리 후 로그인 상태 최종 검증
- `ReelData` 모델에 `views` 필드 추가

#### 3. 조회수 추적 모듈 복구

- `views_tracker.py` 복구:
  - `ReelViewsTracker` 클래스 복구
  - DB 조회수 업데이트 로직 구현 (`_update_views_in_db()`)
  - 시계열 통계 기록 (reel_metrics 테이블)
- `track_views.py` 실행 스크립트 추가

#### 4. 웹 서비스 복구

- Next.js 기반 랭킹 페이지:
  - 조회수/좋아요 기준 정렬
  - 날짜 범위 필터링
  - 일주일 단위 그룹화
- 이미지 프록시 API 구현 (`/api/image-proxy`)
- DB 연결 및 API 엔드포인트 (`/api/reels/ranking`, `/api/reels/[reelId]/metrics`)

**성과**:

- PostgreSQL 데이터베이스 통합 완료
- 수집 모듈 및 추적 모듈에 DB 저장/업데이트 기능 추가
- 중복 처리 (reel_id 기준) 및 시계열 통계 추적 구현
- 로그인 프로세스 개선 (홈 탭 클릭 기능 추가, 리다이렉트 감지)
- 웹 서비스 복구 완료 (Next.js 기반 랭킹 페이지)
- 코드 품질 개선 (PEP 8 준수, 린터 오류 없음)
- 조회수 추적 모듈 복구 완료
- 이미지 프록시 API를 통한 CORS 문제 해결
- 반응형 웹 UI 구현 (다크 테마)
- 데이터베이스 기반 랭킹 시스템 구축

---

### 2026-01-07 네트워크 응답 가로채기 기반 데이터 추출 및 Global Cache 전략 구현

**요청**:

- 좋아요/댓글 수 추출 로직 개선 (UI 기반 → 네트워크 응답 기반)
- Instagram GraphQL 응답에서 직접 데이터 추출
- 여러 릴스가 배치로 전송되는 경우 처리
- 게시일자(posted_date) 및 조회수(views) 추출 추가
- 성능 최적화 (대기 시간 단축)
- DB 저장 시 created_at, updated_at을 게시일로 설정

**구현 내용**:

#### 1. 네트워크 응답 가로채기 구현

- `_register_global_network_listener()` 메서드 추가:
  - Playwright `page.on("response")` 이벤트 리스너 등록
  - GraphQL 쿼리, API 엔드포인트 응답 감지
  - 원본 JSON 데이터 자동 저장 (디버깅용: `output/debug/network_responses/`)
- `_handle_network_response()` 메서드:
  - 관련 URL 패턴 필터링 (`graphql/query`, `/api/v1/feed/`, `/api/v1/media/`, `/info/`, `web_info`)
  - JSON 응답 파싱 및 캐시 저장
  - 에러 처리 및 로깅

#### 2. Global Cache 전략 구현

- 클래스 레벨 `_reels_cache: dict[str, dict]` 추가:
  - Key: 릴스 shortcode (예: "DTIvbyJgNCt")
  - Value: 추출된 데이터 (likes, comments, views, posted_date, shortcode)
- `_parse_and_cache_reels()` 메서드:
  - **유연한 JSON 구조 탐색**:
    - `possible_roots` 리스트로 다양한 JSON 키 패턴 지원:
      - `xdt_api__v1__feed__timeline__connection`
      - `xdt_api__v1__clips__home__connection_v2`
      - `xdt_api__v1__media__shortcode__media`
    - Fallback: `edges` 키를 가진 딕셔너리 자동 탐색
  - **배치 처리**: 한 응답에 여러 릴스가 포함되어도 모두 캐시에 저장
  - **데이터 추출**:
    - `shortcode` (또는 `code`) 추출
    - `like_count` (fallback: `edge_media_preview_like.count`, `edge_media_to_like.count`)
    - `comment_count` (fallback: `edge_media_to_comment.count`)
    - `video_view_count` (fallback: `view_count`, `play_count`, `edge_media_preview.video_view_count`)
    - `posted_date` (from `taken_at_timestamp`, `taken_at`, `timestamp`)

#### 3. 데이터 추출 로직 개선

- `_extract_current_reel_data()` 메서드 개선:
  - 현재 페이지 URL에서 `target_code` (shortcode) 추출
  - `_reels_cache`에서 해당 shortcode로 데이터 조회
  - **Retry 메커니즘**: 데이터가 아직 캐시에 없으면 최대 5초 대기 (10회 × 0.5초)
  - Generic `/reels/` URL인 경우, 캐시에서 찾은 `reel_id`로 구체적인 링크 재구성
- UI 기반 추출 로직 제거:
  - 기존의 XPath/CSS 선택자, 좌표 기반 탐색, 메타 태그 파싱 등 제거
  - 네트워크 응답 기반으로 완전 전환

#### 4. 게시일자 및 조회수 추출 추가

- `ReelData` 모델에 필드 추가:
  - `views: Optional[int]` - 조회수
  - `posted_date: Optional[str]` - 게시일자 (ISO 8601 형식)
- 네트워크 응답에서 `taken_at_timestamp` 등으로 게시일자 추출
- `video_view_count` 등으로 조회수 추출

#### 5. 성능 최적화

- `page.goto()` 대기 시간 단축:
  - `wait_until="networkidle"` → `wait_until="domcontentloaded"`
  - 타임아웃: 30초 → 15초
- 대기 시간 단축:
  - 데이터 추출 대기: 5초 → 3초
  - 릴스 전환 대기: 4초 → 2초
  - 포스터 변경 대기: 3.6초 → 2초
  - 간격 대기: 500ms → 300ms
  - 이동 후 대기: 1초 → 0.5초

#### 6. 데이터 출력 개선

- `_print_reel_summary()` 메서드 추가:
  - 수집된 릴스 정보를 포맷팅하여 콘솔에 출력
  - 작성자, 제목, 좋아요, 댓글, 조회수, 게시일자, 음악, 링크 표시
  - 중복 제거 후 출력

#### 7. DB 저장 로직 개선

- `ReelRepository.create_or_update_reel()` 수정:
  - `posted_date`가 있으면 파싱하여 `datetime` 객체로 변환
  - **새 릴스 생성 시**: `created_at`, `updated_at` 모두 게시일로 설정
  - **기존 릴스 업데이트 시**: `updated_at`만 게시일로 업데이트 (created_at은 유지)

**성과**:

- 네트워크 응답 기반 데이터 추출로 안정성 대폭 향상
- Global Cache 전략으로 타이밍 이슈 해결
- 다양한 JSON 키 패턴 지원으로 Instagram 구조 변경에 대응
- 게시일자 및 조회수 추출 추가
- 성능 최적화로 수집 속도 개선
- DB 저장 시 게시일 기반 타임스탬프 설정
- 디버깅을 위한 원본 네트워크 응답 자동 저장
- UI 렌더링 지연 문제 완전 해결

**기술적 개선사항**:

- UI 기반 추출의 한계 극복 (렌더링 지연, DOM 구조 변경)
- 네트워크 레벨에서 직접 데이터 추출로 정확도 향상
- 배치 응답 처리로 효율성 향상
- Retry 메커니즘으로 타이밍 이슈 해결
- 유연한 JSON 파싱으로 Instagram API 변경에 대응

---

### 2026-01-07 추적 모듈 개선 - 세션 쿠키 사용, 통계 추출 확장, 성능 최적화

**요청**:

- 추적 모듈에 세션 쿠키 사용 기능 추가
- 스크롤 횟수 증가 (3회 → 5회)
- 조회수뿐 아니라 좋아요, 댓글 수도 함께 추출
- HTML 구조에 맞는 정확한 통계 추출
- 로그 개선 (모든 통계 표시)
- 좋아요, 댓글도 DB에 저장
- 성능 최적화 (속도 향상)

**구현 내용**:

#### 1. 세션 관리 통합

- `SessionManager` 통합 (`src/views_tracker.py`):
  - 저장된 세션(쿠키 + User-Agent) 로드 및 재사용
  - 세션 검증 후 유효하면 로그인 생략
  - 로그인 성공 후 세션 자동 저장
  - 스크래퍼(`InstagramReelsScraper`)와 동일한 세션 관리 방식 적용
- `login()` 메서드 개선:
  - 기존: 매번 새로운 로그인 수행
  - 개선: 저장된 세션 확인 → 유효하면 재사용 → 무효하면 새 로그인

#### 2. 통계 추출 확장

- 조회수뿐 아니라 좋아요, 댓글 수도 함께 추출:
  - 반환 타입: `dict[str, int]` → `dict[str, dict[str, Optional[int]]]`
  - 각 릴스별로 `{views, likes, comments}` 딕셔너리 반환
- HTML 구조 기반 정확한 추출:
  - 실제 HTML 구조 분석 (`reels.txt` 참고)
  - `div._aaj-` 내부의 `ul > li` 구조:
    - 첫 번째 `li`: 좋아요 수 (예: "3.6만")
    - 두 번째 `li`: 댓글 수 (예: "544")
  - `div._aaj_` 내부의 조회수 아이콘 옆 숫자: 조회수 (예: "445.4만")
- JavaScript 추출 로직 개선:
  - 각 통계별로 정확한 위치에서 추출
  - 아이콘의 `aria-label` 확인하여 정확한 매칭
  - 부모 요소 순회하면서 가장 가까운 숫자 찾기

#### 3. 스크롤 횟수 증가

- 최대 스크롤 횟수: 3회 → 5회
- 더 많은 릴스를 확인하여 추출 성공률 향상

#### 4. 로그 개선

- 개별 릴스 로그:
  - 기존: 찾은 통계만 표시
  - 개선: 좋아요, 댓글, 조회수 모두 표시 (없으면 "없음")
  - 예: `릴스 ID 'xxx' - 좋아요: 36000, 댓글: 544, 조회수: 445.4만`
- 크리에이터별 요약 로그:
  - 각 크리에이터 처리 후 추출된 통계 요약 표시
  - 예: `크리에이터 'xxx'에서 1개 릴스 통계 추출 완료 (좋아요: 1개, 댓글: 1개, 조회수: 1개)`

#### 5. 데이터베이스 저장 개선

- 좋아요, 댓글도 DB에 저장:
  - `_update_views_in_db()` 메서드 개선
  - `reel_metrics` 테이블에 시계열 데이터로 저장
  - 조회수, 좋아요, 댓글 수 모두 추적 가능
- 저장 로직 개선:
  - 추출된 값이 있으면 사용, 없으면 기존 값 사용
  - 하나라도 값이 있으면 DB에 저장

#### 6. 성능 최적화

- 페이지 로드 대기 시간 단축:
  - 기존: `time.sleep(3)` + `random_delay(1.0, 2.0)` = 최대 5초
  - 개선: `time.sleep(1)` + `random_delay(0.5, 1.0)` = 최대 2초
  - 절약: 약 2-3초
- 스크롤 후 대기 시간 단축:
  - 기존: `time.sleep(2)` + `random_delay(1.0, 2.0)` = 최대 4초
  - 개선: `time.sleep(1)` + `random_delay(0.5, 1.0)` = 최대 2초
  - 절약: 약 1.5-2초 (스크롤 1회당)
- 크리에이터 간 딜레이 단축:
  - 기존: `random_delay(2.0, 4.0)` = 최대 4초
  - 개선: `random_delay(1.0, 2.0)` = 최대 2초
  - 절약: 약 1-2초 (크리에이터당)
- 네트워크 대기 최적화:
  - `networkidle` → `domcontentloaded`로 변경 (더 빠른 응답)
  - 타임아웃: 5초 → 3초

**성과**:

- 세션 쿠키 재사용으로 로그인 횟수 감소 및 봇 감지 위험 감소
- 통계 추출 확장으로 더 많은 데이터 수집 가능 (조회수 + 좋아요 + 댓글)
- HTML 구조 기반 추출로 정확도 향상
- 성능 최적화로 실행 시간 약 30-40% 단축 (크리에이터당 약 4-6초 절약)
- 로그 개선으로 디버깅 및 모니터링 용이
- DB 저장 개선으로 시계열 통계 추적 가능

**기술적 개선사항**:

- 세션 관리 통합으로 코드 일관성 향상
- 실제 HTML 구조 분석 및 반영
- 정확한 통계 위치 파악 및 추출
- 대기 시간 최적화로 속도 향상 (안정성 유지)

---

### 2026-02-23 계정별 프로파일, 브라우저 로케일, 로그인 셀렉터, 중복 감지 수정

**요청**:

- 계정별 지역 설정 (한국/일본 등)을 DB 말고 accounts.yaml + --profile로 관리
- 브라우저 로케일/타임존 설정 (일본 IP·계정 시 일본어 UI)
- 신규 인스타그램 로그인 폼 대응 (한국/일본/영어)
- 세션 검증 URL 버그 수정 (이메일 계정 시 username만 사용)
- 릴스 수집 시 썸네일 기반 중복 false positive 수정, 연속 중복 N개 시 루프 종료
- .env / env.example / accounts.yaml 구조·주석 통일

**구현 내용**:

#### 1. 프로파일 및 실행 진입점

- `accounts.yaml`: kr/jp 프로파일 정의 (account_id, instagram_username, instagram_password, output_dir, browser_locale, browser_timezone)
- `src/profile_loader.py`: 프로파일 로더 (accounts.yaml 읽어 config 오버라이드, output_dir 등 Path 변환)
- 루트 `main.py`: `--profile`, `--list-profiles` 인자 추가, `load_profile(args.profile)` 또는 `load_config()` 호출

#### 2. 브라우저 로케일

- `src/config.py`: `browser_locale`, `browser_timezone` 필드 추가
- `src/browser.py`: locale/timezone을 config에서 읽어 사용, Accept-Language·navigator.languages 오버라이드
- `.env` / `env.example`: BROWSER_LOCALE, BROWSER_TIMEZONE 항목 추가

#### 3. 로그인 셀렉터

- `src/browser.py`: `#loginForm` 없을 때 `input[name="email"]`, `input[name="pass"]` 등으로 로그인 폼 대기
- `src/scraper.py`: username `input[name="email"]` 등, password `input[name="pass"]` 등, 로그인 버튼 "로그인"/"ログイン"/"Log in" div+span/button 셀렉터 추가

#### 4. 세션 검증 URL

- `src/utils/session_manager.py`: account_id가 이메일이면 `@` 앞 username만 사용해 검증 URL 생성 (예: cxv963@naver.com → /cxv963/)

#### 5. 중복 감지 수정

- `src/scraper.py`: reel_id가 정상 추출된 경우 썸네일 중복 체크 생략 (공통 UI 이미지 false positive 방지)
- 연속 중복 N개(기본 10) 시 수집 루프 종료 (`consecutive_duplicates`, `max_consecutive_duplicates`)

#### 6. 기타

- `.env`, `env.example`, `accounts.yaml`: 섹션 구분·순서·주석 통일
- `pyproject.toml`: pyyaml 의존성 추가
- ruff --fix 적용, B018 1건 수정 (views_tracker.py)

**성과**:

- 계정별 프로파일(kr/jp)로 지역·로케일 전환 가능
- 신규 인스타 로그인 폼(한국/일본/영어) 대응
- 세션 검증 URL 버그 수정
- 릴스 중복 감지 false positive 제거 및 연속 중복 종료
- env/profile 문서 일관화

---

### 2026-03-12 운영 전환 준비 — DB 테이블 접두사, S3 썸네일 아카이빙, 추적 모듈 버그 수정, 웹 최신화

**요청**:

- 고객사 AWS RDS 운영 DB 전환 (테이블명 접두사 `instagram_` 적용)
- Instagram CDN URL 만료 문제 해결 (S3 webp 압축 저장)
- 추적 모듈 로그인 버그 수정
- `track_views.py` `--profile` 지원 추가
- 웹 서비스 운영 DB / 테이블명 최신화
- 이미지 프록시 S3 AWS SDK 지원

**구현 내용**:

#### 1. DB 테이블명 변경 (`src/database/models.py`)

- `__tablename__` 5개 → `instagram_*` 접두사 적용
  - `reels` → `instagram_reels`
  - `reel_metrics` → `instagram_reel_metrics`
  - `creators` → `instagram_creators`
  - `scraping_sessions` → `instagram_scraping_sessions`
  - `account_sessions` → `instagram_account_sessions`
- `instagram_reel_metrics.reel_id` FK도 `instagram_reels.id` 참조로 변경

#### 2. S3 썸네일 아카이빙 (`src/thumbnail_archiver.py` 신규)

- `ThumbnailArchiver` 클래스 구현:
  - `archive_reel_thumbnail(reel_id, cdn_url, country_code)` → S3 webp 저장
  - `archive_profile_image(username, cdn_url)` → S3 webp 저장
  - `batch_archive(reels, country_code)` → 릴스 리스트 일괄 처리
  - 실패 시 원본 CDN URL fallback (수집 중단 없음)
- S3 저장 경로: `instagram/thumbnails/{kr|jp|us}/{reel_id}.webp`, `instagram/profiles/{username}.webp`
- `build_archiver_from_config(config)`: `S3_ENABLED=false` 이면 None 반환
- `src/scraper.py` `save_to_json()` 내 `batch_archive()` 통합

#### 3. Config / 의존성 (`src/config.py`, `pyproject.toml`)

- `ScrapingConfig`에 S3 설정 필드 추가: `s3_enabled`, `s3_bucket`, `aws_region`, `aws_access_key_id`, `aws_secret_access_key`
- `pyproject.toml`: `boto3`, `pillow` 의존성 추가

#### 4. Logger rotation (`src/utils/logger.py`)

- 기본 rotation: `"10 MB"` → `"1 day"`, retention: `"7 days"` → `"30 days"`, compression `"zip"` 추가

#### 5. 추적 모듈 버그 수정 (`src/views_tracker.py`)

- `track_views()` 내 로그인 체크: `browser_manager is None` 기준 → `_is_logged_in` 기준으로 변경 (로그인 실패 후 재시도 누락 버그 수정)
- `_extract_views_from_creator_reels_page()`:
  - URL 리다이렉트 외 인페이지 로그인 오버레이 감지 추가 (DOM 체크)
  - 로그인 리다이렉트 감지 시 `return {}` → 재로그인 1회 시도 후 재시도

#### 6. `track_views.py` 프로파일 지원

- `argparse` 도입: `--profile kr` 옵션 추가
- `load_profile(args.profile)` 우선, 없으면 `load_config()` fallback
- 실행 예: `poetry run python track_views.py --profile kr output/kr/reels_*.json`

#### 7. 웹 서비스 최신화 (`web/`)

- API 쿼리 테이블명 3개 파일 일괄 변경: `reels` → `instagram_reels`, `reel_metrics` → `instagram_reel_metrics`
- `.env.local`: 개발 DB → 운영 DB (`dbmaster`, 운영 비밀번호)
- `next.config.js`: S3 이미지 도메인 `trendboard-mda.s3.ap-northeast-2.amazonaws.com` 추가
- `image-proxy/route.ts`: S3 URL 감지 → AWS SDK(`@aws-sdk/client-s3`)로 서버사이드 fetch (버킷 비공개 유지)
- `ReelCard.tsx`: 썸네일 이미지 프록시 통해 로드, `crossOrigin="anonymous"` 제거

**성과**:

- 고객사 운영 DB(`dbmaster`)에 `instagram_*` 테이블로 저장 가능
- 수집 직후 썸네일 S3 webp 압축 저장 (17~27 KB, CDN 만료 문제 해결)
- 추적 모듈 로그인 안정화
- `track_views.py` 프로파일 기반 실행 지원
- 웹 운영 DB 연결 + S3 이미지 정상 표시

---

### 2026-03-14 KR 운영 서버 장애 대응 — 중복 프로세스 제거 + flock 중복 실행 방지

**요청**: 운영 서버 속도가 갑자기 느려진 원인 파악 및 조치

**원인**: `Restart=always` systemd 서비스가 이전 프로세스(PID 15140, Mar13 기동)가 종료되지 않은 채 새 인스턴스(PID 31124)를 띄움 → Chrome 18개 누적 → RAM 3.7GB 포화, CPU steal 86.7%

**조치**:

1. **좀비 프로세스 강제 종료**: `kill -9 15140 15139 31124`
   - RAM: 3.7GB → 539MB 사용 / 3.2GB 확보

2. **`/srv/insta_scrap/run_safe.sh` 신규 생성**:
   - `flock -n /tmp/insta-scraper-{profile}.lock` 으로 동일 프로파일 중복 실행 원천 차단
   - 락 획득 실패 시 즉시 종료 (systemd가 재시도해도 이미 실행 중이면 튕김)

3. **`/etc/systemd/system/insta-scraper@.service` 수정**:
   - `ExecStart` → `run_safe.sh %i` 교체
   - `KillMode=control-group` 추가 (서비스 종료 시 Chrome 자식 프로세스 전부 킬)
   - `TimeoutStopSec=30` 추가 (30초 내 미종료 시 강제 킬)
   - `StandardOutput/Error=journal` 변경 (`journalctl -u insta-scraper@kr -f` 로 실시간 로그 확인)

4. `sudo systemctl daemon-reload && sudo systemctl start insta-scraper@kr`

**결과**: 서비스 정상화, 프로세스 1개 (PID 31938), RAM 정상 범위 유지

---

### 2026-02-27 국가별 일일 랭킹, reel_metrics 중복 방지, 썸네일/크리에이터 추출 개선

**요청**:

- 국가별 수집 데이터를 웹에서 국가별 일일 랭킹으로 표시
- DB 구조 변경 (계정 기준 국가 코드)
- 수집 모듈만 돌릴 때 reel_metrics에 중복 데이터 적재되는 문제 해결
- 일본 로케일 등에서 프로필 이미지·영상 썸네일이 20개 이후부터 제대로 수집되지 않는 문제 해결
- 웹 기본 정렬 좋아요 순, 필터 UI 개선

**구현 내용**:

#### 1. DB 및 백엔드

- `reels.country_code` 컬럼 추가 (계정/프로파일 기준, 신규 저장 시에만 설정)
- `ScrapingConfig`에 `country_code` 추가, `load_profile()`에서 프로파일 이름 설정
- `ReelRepository.create_or_update_reel(reel_data, country_code)` — 신규 시에만 country_code 반영
- `database/migrations/001_add_reels_country_code.sql` — 마이그레이션 스크립트
- **reel_metrics 중복 방지**: `save_to_json(..., db_only_new_count)` 도입, 주기 저장 시 `data[last_db_saved_count:]`만 `_save_to_db`에 전달

#### 2. 썸네일·크리에이터 추출

- **로케일 독립**: `/username/reels/` href 기반 author·프로필 이미지 1순위, 한국어/일본어/영어 aria-label·alt fallback
- **네트워크 캐시**: `_parse_and_cache_reels`에서 thumbnail·author·profile_image 추출 후 캐시 저장
- **썸네일**: 캐시에 값이 있으면 DOM poster 대신 캐시 값 사용 (슬롯 재사용으로 인한 동일 썸네일 반복 방지)
- API 응답 여러 경로 지원 (image_versions2, carousel_media, thumbnail_resources, thumbnail_src 등)

#### 3. 웹

- **API**: `GET /api/reels/ranking`에 `country` 파라미터, 일일 랭킹( startDate=endDate ) 시 해당 일자 메트릭 스냅샷 사용
- **API**: `GET /api/countries` — reels에 존재하는 country_code 목록
- **UI**: 국가 선택(한국/일본 표기), 정렬 기본값 좋아요 순·좋아요 버튼 왼쪽 배치, 필터 카드 레이아웃, 수집일(recorded_at) 기준 주차 그룹·"N월 M째 주 (날짜)" 형식

#### 4. 기타

- `views_tracker.py`: `return views_dict` → `return metrics_dict` 버그 수정
- 린터: scraper/views_tracker W293, B007, UP038, B904, F841 반영, ScrapingSessionRepository 미사용 제거

**성과**:

- 국가별·일자별 랭킹 조회 및 웹 UI 지원
- 수집 한 번에 릴스당 reel_metrics 1건만 적재되도록 중복 제거
- 일본 등 다국어 로케일에서 썸네일·author·프로필 이미지 수집 안정화
- 웹 필터/정렬 UX 개선

---
