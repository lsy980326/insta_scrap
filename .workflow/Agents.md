# AI 에이전트 가이드라인 (Agents.md)

이 문서는 AI 에이전트(Cursor, Claude Code 등)가 이 프로젝트에서 작업할 때 따라야 할 가이드라인입니다.

## 📋 작업 원칙

### 1. 문서 우선 접근

- 작업 전에 관련 문서를 먼저 확인하세요
- `.workflow/` 디렉토리의 도메인별 구조 문서를 참조하세요
- `client/docs/` 디렉토리의 아키텍처 문서를 참조하세요
- 도메인별 구조 문서(`.workflow/domain-*.md`)를 확인하세요
- 불필요하게 많은 파일을 grep하지 마세요

### 2. 컨텍스트 엔지니어링

- 작업에 필요한 최소한의 컨텍스트만 사용하세요
- 관련 도메인 문서만 읽고 작업하세요
- 전체 코드베이스를 스캔하는 것은 피하세요

### 3. 문서 최신화

- **중요**: 코드 변경 시 관련 문서도 함께 업데이트하세요
- PR 생성 시 `pr-guide.md`를 참조하여 문서 업데이트를 확인하세요
- 문서는 항상 최신 상태를 유지해야 합니다

### 4. 코드 품질

- Python PEP 8 스타일 가이드를 준수하세요
- 타입 힌트를 적절히 사용하세요 (Pydantic 모델 활용)
- 명확한 함수/클래스 명명 규칙을 따르세요
- Black, Ruff, MyPy를 사용한 코드 품질 관리
- Poetry를 사용한 의존성 관리

### 5. 모듈화 원칙

- 각 모듈은 독립적인 책임을 가져야 합니다
- 새로운 기능은 기존 모듈을 확장하거나 새로운 모듈로 분리하세요
- 적절한 패키지 구조를 유지하세요

## 🏗️ 프로젝트 구조 이해

### 주요 디렉토리

- `src/` - 소스 코드
  - `scraper.py` - 인스타그램 릴스 스크래퍼 메인 클래스
  - `browser.py` - Playwright 브라우저 관리 클래스
  - `main.py` - 메인 실행 파일
  - `config.py` - 설정 관리 (Pydantic Settings)
  - `models.py` - 데이터 모델 (Pydantic)
  - `exceptions.py` - 커스텀 예외 클래스
  - `utils/` - 유틸리티 모듈
    - `logger.py` - 로깅 유틸리티 (Loguru)
    - `human_behavior.py` - 사용자 행동 시뮬레이션
    - `wait_utils.py` - 대기 유틸리티
  - `database/` - 데이터베이스 모듈
    - `connection.py` - PostgreSQL 연결 관리
    - `models.py` - SQLAlchemy ORM 모델
    - `repositories/` - Repository 패턴 구현
- `web/` - Next.js 웹 서비스
  - `app/` - Next.js App Router
    - `page.tsx` - 메인 페이지
    - `api/` - API 라우트
  - `components/` - React 컴포넌트
  - `lib/` - 유틸리티
- `tests/` - 테스트 코드 (pytest)
- `.workflow/` - 워크플로우 문서
- `output/` - 스크래핑 결과 데이터 (생성됨)

### 주요 모듈/클래스

- `InstagramReelsScraper` (`src/scraper.py`)

  - 인스타그램 릴스 스크래핑을 담당하는 메인 클래스
  - 수집 정보: 썸네일, 좋아요 수, 댓글 수, 작성자 이름, 배경음악 정보, 링크
  - 주요 메서드: `login()`, `scrape_reels()`, `extract_reel_data()`, `save_to_json()`, `save_to_csv()`

- `BrowserManager` (`src/browser.py`)

  - Playwright 기반 브라우저 자동화 관리
  - 봇 감지 우회 설정 (스텔스 모드)
  - 브라우저 상태 저장/로드 지원

- `ScrapingConfig` (`src/config.py`)

  - Pydantic Settings를 통한 타입 안전한 설정 관리
  - 환경 변수 기반 설정 로드

- `ReelData` (`src/models.py`)
  - Pydantic BaseModel을 사용한 릴스 데이터 모델
  - 타입 검증 및 데이터 구조 보장

## 🔍 작업 시 확인 사항

### 코드 수정 전

1. 관련 도메인별 구조 문서 확인 (`.workflow/domain-*.md`)
2. 관련 아키텍처 문서 확인 (있는 경우)
3. 관련 타입/데이터 구조 확인
4. 기존 유사 기능의 구현 패턴 확인
5. 컨텍스트 엔지니어링 가이드 확인 (`.workflow/context-engineering.md`)

### 코드 수정 중

1. Python 스타일 가이드 준수 (PEP 8)
2. 타입 힌트 적절히 사용
3. 기존 API 호환성 유지 (breaking change 시 문서화)
4. 에러 처리 추가
5. 주석 및 문서 업데이트

### 코드 수정 후

1. 관련 문서 업데이트 (`.workflow/domain-*.md`)
2. 모듈 구조 확인 (새 모듈 추가 시)
3. 데이터 구조 정의 확인
4. `workflow-checklist.md`에 작업 완료 기록
5. **PR 가이드 체크리스트 확인** (`.workflow/pr-guide.md`) - **반드시 확인**

## 📚 참조 문서 우선순위

1. **도메인별 구조 문서** (`.workflow/domain-*.md`)

   - API 목록, 컴포넌트 구조, 데이터 흐름 등
   - 작업 전 반드시 확인
   - 예: `domain-scraping.md` - 스크래핑 관련 API 및 구조

2. **FAQ & 트러블슈팅** (`.workflow/faq-troubleshooting.md`)

   - 자주 발생하는 문제와 해결 방법
   - 문제 발생 시 먼저 확인

3. **아키텍처 문서** (있는 경우)

   - 전체 시스템 흐름 이해

4. **기술 문서** (있는 경우)

   - 특정 기술 영역 이해

5. **타입/데이터 구조 정의**
   - 데이터 구조 이해

## ⚠️ 주의사항

- **Human in the loop**: 의도치 않은 변경 시 사용자에게 확인 요청
- **git worktree**: 여러 작업을 동시에 진행할 때 활용
- **토큰 최적화**: 필요한 문서만 읽고, 불필요한 파일 스캔 방지
- **문서 최신화**: 코드 변경 시 반드시 관련 문서도 업데이트

## 🎯 작업 예시

### 새 기능 추가 시

1. `.workflow/domain-*.md`에서 관련 도메인 구조 확인
2. 기존 유사 기능의 패턴 파악 (`src/scraper.py` 참조)
3. 데이터 구조 정의 추가
4. 모듈 구현
5. 모듈 구조 확인
6. 관련 문서 업데이트 (`.workflow/domain-*.md`)
7. `workflow-checklist.md`에 작업 기록
8. PR 가이드 체크리스트 확인 (`.workflow/pr-guide.md`)

### 버그 수정 시

1. 관련 도메인 문서 확인
2. 문제 원인 파악
3. 최소한의 변경으로 수정
4. 관련 테스트 확인 (있는 경우)
5. 문서 업데이트 (필요 시)

### 리팩토링 시

1. 영향 범위 파악 (도메인 문서 참조)
2. 코드 품질 유지 (PEP 8, 타입 힌트)
3. API 호환성 확인
4. 모든 관련 문서 업데이트
5. `pr-guide.md` 체크리스트 확인

