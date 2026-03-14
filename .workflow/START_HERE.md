# 맥도날드 시스템 시작 가이드

이 프로젝트에 "맥도날드 시스템"을 적용했습니다. 이는 AI 에이전트(Cursor, Claude Code 등)가 효율적으로 작업할 수 있도록 구조화된 문서와 가이드라인을 제공하는 시스템입니다.

## 🚀 빠른 시작

### 0. 신규 프로젝트 초기화 (최초 1회)

**이 파일을 읽는 신규 프로젝트라면, 먼저 초기화 스크립트를 실행하세요:**

#### macOS/Linux:
```bash
.workflow/init-new-project.sh <프로젝트-이름>
```

#### Windows:
```cmd
.workflow\init-new-project.bat <프로젝트-이름>
```

**초기화 스크립트가 자동으로 설정하는 것들:**
- ✅ 맥도날드 워크플로우 디렉토리 구조
- ✅ git-crypt 환경 변수 암호화 설정
- ✅ .gitattributes 및 .gitignore 설정
- ✅ Git pre-commit hook (자동 암호화 확인)
- ✅ 공유 키 지원 (여러 프로젝트에서 동일한 키 사용 가능)

**공유 키 사용:**
- 첫 프로젝트에서 공유 키를 생성하면, 다른 프로젝트에서도 동일한 키로 암호화/복호화 가능
- 자세한 내용: `.workflow/shared-key-guide.md`

## 🚀 빠른 시작 (기존 프로젝트)

### 1. AI 에이전트를 사용하는 경우

**작업 시작 전:**

1. `Agents.md` 읽기 - AI 에이전트 가이드라인
2. `context-engineering.md` 읽기 - 컨텍스트 엔지니어링 가이드
3. 작업할 도메인의 구조 문서 확인 (`.workflow/domain-*.md`)

**작업 후:**

1. `pr-guide.md` 체크리스트 확인
2. 관련 문서 업데이트
3. `workflow-checklist.md`에 작업 완료 기록

### 2. 개발자를 위한 가이드

**코드 작업 시:**

- 도메인별 구조 문서를 참조하여 API 사용법 확인
- 새 기능 추가 시 관련 문서도 함께 업데이트

**PR 생성 시:**

- `pr-guide.md`의 체크리스트 확인
- 관련 문서 업데이트 여부 확인

## 📚 문서 구조

### 핵심 가이드 문서

- `Agents.md` - AI 에이전트가 따라야 할 가이드라인
- `pr-guide.md` - PR 생성 시 체크리스트 및 문서 업데이트 가이드
- `context-engineering.md` - 컨텍스트 엔지니어링 가이드
- `workflow-checklist.md` - 작업 진행 상황 추적 체크리스트

### 도메인별 구조 문서

- `.workflow/domain-scraping.md` - 스크래핑 도메인 API 및 구조
  - InstagramReelsScraper 클래스 API
  - 데이터 구조 및 흐름
  - 사용 예시
- `.workflow/domain-web.md` - 웹 서비스 도메인 API 및 구조
  - Next.js 웹 서비스 API
  - 컴포넌트 구조
  - 데이터 흐름
  - 사용 예시

### 참고 문서

- `mcdonald-workflow-guide.md` - 맥도날드식 워크플로우 구축 가이드
- `shared-key-guide.md` - 공유 키 사용 가이드 (여러 프로젝트에서 동일한 키 사용)
- `env-secrets-management.md` - 환경 변수 암호화 방법 비교

## 🎯 주요 원칙

### 1. 문서 우선 접근

- 작업 전 관련 문서를 먼저 확인
- 불필요하게 많은 파일을 grep하지 않기

### 2. 도메인별 구조화

- 각 도메인별로 API, 컴포넌트 구조, 데이터 흐름을 문서화
- 필요한 정보만 빠르게 찾을 수 있도록 구조화

### 3. 문서 최신화

- 코드 변경 시 관련 문서도 함께 업데이트
- PR 시 문서 업데이트 여부 확인

### 4. 컨텍스트 엔지니어링

- 토큰 사용량 최적화
- 필요한 정보만 효율적으로 수집

## 📝 사용 예시

### 예시 1: 새 기능 추가

1. 관련 도메인 문서 확인 (`.workflow/domain-*.md`) → 구조 파악
2. 기존 코드 패턴 확인
3. 기능 구현
4. 관련 도메인 문서 업데이트 (새 API/기능 추가)
5. `workflow-checklist.md`에 작업 기록
6. `pr-guide.md` 체크리스트 확인

### 예시 2: 버그 수정

1. 관련 도메인 문서 확인
2. 문제 발생 지점 파악
3. 최소한의 변경으로 수정
4. 필요 시 문서 업데이트

## 🔄 문서 업데이트 워크플로우

```
코드 변경
  ↓
관련 문서 확인 (도메인 문서, 아키텍처 문서)
  ↓
문서 업데이트 필요 여부 판단
  ↓
문서 업데이트
  ↓
PR 생성 시 pr-guide.md 체크리스트 확인
```

## 💡 팁

- **AI 에이전트 사용 시**: `Agents.md`와 `context-engineering.md`를 먼저 읽히세요
- **문서 찾기**: 도메인별 작업은 `.workflow/domain-*.md`를 먼저 확인
- **작업 추적**: `workflow-checklist.md`에 작업 진행 상황을 기록하세요
- **PR 시**: `pr-guide.md` 체크리스트를 반드시 확인
- **토큰 최적화**: 도메인 문서를 먼저 확인하여 불필요한 파일 스캔 방지

## 🔐 환경 변수 암호화 (git-crypt)

이 프로젝트는 git-crypt를 사용하여 `.env` 파일을 암호화하여 Git에 저장합니다.

### 자동 암호화

- **커밋 시 자동 암호화**: `.env` 파일을 커밋하면 자동으로 암호화되어 저장됩니다
- **로컬에서는 평문**: 편집 시에는 평문으로 보이고, Git에 저장될 때만 암호화됩니다
- **Pre-commit hook**: 커밋 전에 암호화 여부를 자동으로 확인합니다

### 공유 키 사용

여러 프로젝트에서 동일한 키를 사용하려면:

```bash
# 첫 프로젝트에서 공유 키 생성
git-crypt export-key ~/.git-crypt-shared-key

# 다른 프로젝트에서 사용
git-crypt unlock ~/.git-crypt-shared-key
```

자세한 내용: `.workflow/shared-key-guide.md`

### 다른 환경에서 사용

```bash
# 저장소 클론 후
git clone <repository-url>
cd project-name

# 공유 키로 복호화 (또는 프로젝트별 키)
git-crypt unlock ~/.git-crypt-shared-key
# 또는
git-crypt unlock ~/git-crypt-backups/project-name-*.key
```

자세한 내용: `.git-crypt-setup.md`

## 📖 더 알아보기

- [맥도날드 시스템 원문](https://yozm.wishket.com/magazine/detail/3457/) - 삼양식품의 실제 적용 사례
- `mcdonald-workflow-guide.md` - **다른 프로젝트에 맥도날드식 워크플로우를 적용하는 종합 가이드**
- `Agents.md` - 상세한 AI 에이전트 가이드라인
- `pr-guide.md` - PR 가이드 및 체크리스트
- `workflow-checklist.md` - 작업 진행 상황 추적 체크리스트
- `context-engineering.md` - 컨텍스트 엔지니어링 가이드
- `shared-key-guide.md` - 공유 키 사용 가이드
- `env-secrets-management.md` - 환경 변수 암호화 방법 비교

---

**이 시스템의 목적은 AI 에이전트와 개발자가 효율적으로 협업할 수 있도록 하는 것입니다. 문서를 최신 상태로 유지하고, 작업 전 관련 문서를 확인하는 습관을 기르세요.**

