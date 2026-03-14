# 웹 서비스 도메인 구조 문서

인스타그램 릴스 랭킹 웹 서비스 관련 API 및 구조를 문서화합니다.

## 📦 모듈 위치

- `web/` - Next.js 웹 서비스 프로젝트
  - `app/` - Next.js App Router 구조
    - `page.tsx` - 메인 페이지 (랭킹 목록)
    - `api/reels/ranking/route.ts` - 랭킹 조회 API
    - `api/countries/route.ts` - 국가 목록 API
    - `api/reels/[reelId]/metrics/route.ts` - 메트릭 히스토리 API
    - `api/image-proxy/route.ts` - 이미지 프록시 API (CORS 우회)
  - `components/` - React 컴포넌트
    - `ReelCard.tsx` - 릴스 카드 컴포넌트
    - `MetricModal.tsx` - 통계 추적 모달 컴포넌트
  - `lib/db.ts` - PostgreSQL 연결 관리

## 🔌 주요 API

### 랭킹 조회 API

**엔드포인트**: `GET /api/reels/ranking`

**쿼리 파라미터**:
- `sortBy` (선택): 정렬 기준 (`views` | `likes`), 기본값: `views`
- `limit` (선택): 조회 개수, 기본값: `1000`
- `offset` (선택): 오프셋, 기본값: `0`
- `country` (선택): 국가 코드 (예: `kr`, `jp`). 없으면 전체.
- `startDate` (선택): 시작일 (YYYY-MM-DD 형식)
- `endDate` (선택): 종료일 (YYYY-MM-DD 형식). `startDate`와 같으면 해당 일자 스냅샷(일일 랭킹).

**응답 형식**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "reel_id": "DS4U0UKgGt9",
      "link": "https://www.instagram.com/reel/...",
      "thumbnail_url": "...",
      "author": "username",
      "creator_profile_image": "...",
      "title": "...",
      "music": "...",
      "created_at": "2026-01-02T...",
      "likes": 1000,
      "comments": 50,
      "views": 50000,
      "recorded_at": "2026-01-02T..."
    }
  ],
  "total": 100
}
```

**사용 예시**:
```typescript
// 조회수 기준 정렬
const response = await fetch('/api/reels/ranking?sortBy=views&limit=50')
const result = await response.json()

// 날짜 범위 필터링
const response = await fetch('/api/reels/ranking?startDate=2026-01-01&endDate=2026-01-31')

// 국가별 일일 랭킹
const response = await fetch('/api/reels/ranking?country=kr&startDate=2026-01-15&endDate=2026-01-15')
```

### 국가 목록 API

**엔드포인트**: `GET /api/countries`

**응답 형식**: `{ "success": true, "data": ["kr", "jp", ...] }` (reels에 존재하는 country_code 목록)

### 메트릭 히스토리 API

**엔드포인트**: `GET /api/reels/[reelId]/metrics`

**경로 파라미터**:
- `reelId`: Instagram 릴스 ID (예: `DS4U0UKgGt9`)

**응답 형식**:
```json
{
  "success": true,
  "data": {
    "reel": {
      "reel_id": "DS4U0UKgGt9",
      "link": "...",
      "thumbnail_url": "...",
      "author": "username",
      "creator_profile_image": "...",
      "title": "...",
      "music": "..."
    },
    "metrics": [
      {
        "id": 1,
        "likes": 1000,
        "comments": 50,
        "views": 50000,
        "recorded_at": "2026-01-02T..."
      }
    ]
  }
}
```

**사용 예시**:
```typescript
const response = await fetch('/api/reels/DS4U0UKgGt9/metrics')
const result = await response.json()
```

### 이미지 프록시 API

**엔드포인트**: `GET /api/image-proxy`

**쿼리 파라미터**:
- `url` (필수): 프록시할 이미지 URL

**응답**: 이미지 바이너리 데이터

**사용 예시**:
```typescript
const imageUrl = 'https://scontent-xxx.cdninstagram.com/...'
const proxyUrl = `/api/image-proxy?url=${encodeURIComponent(imageUrl)}`
```

**목적**: Instagram CDN 이미지의 CORS 문제를 우회하기 위한 프록시

## 🏗️ 컴포넌트 구조

### ReelCard 컴포넌트

**위치**: `web/components/ReelCard.tsx`

**Props**:
- `reel`: Reel 객체 (id, reel_id, link, thumbnail_url, author, creator_profile_image, title, music, likes, comments, views, created_at)
- `rank`: 랭킹 순위 (number)
- `onClick`: 클릭 핸들러 함수
- `formatNumber`: 숫자 포맷팅 함수
- `formatDate`: 날짜 포맷팅 함수

**기능**:
- 릴스 썸네일 표시
- 랭킹 배지 표시
- 조회수/좋아요 통계 오버레이
- 크리에이터 프로필 이미지 및 정보
- 등록 날짜 표시
- 프로필 이미지 로드 실패 시 대체 UI (사용자명 첫 글자)

### MetricModal 컴포넌트

**위치**: `web/components/MetricModal.tsx`

**Props**:
- `reel`: Reel 객체
- `onClose`: 모달 닫기 핸들러 함수

**기능**:
- 릴스 상세 정보 표시
- 시계열 메트릭 히스토리 테이블
- 변화율 계산 및 색상 표시 (증가: 초록, 감소: 빨강)
- 인스타그램 링크 제공

### 메인 페이지

**위치**: `web/app/page.tsx`

**기능**:
- 조회수/좋아요 기준 정렬
- 날짜 범위 필터링
- 일주일 단위 그룹화 표시
- 반응형 그리드 레이아웃
- 다크 테마 UI

## 🔄 데이터 흐름

```
1. 사용자 요청
   ↓
2. 프론트엔드 (page.tsx)
   - 정렬 기준 선택 (조회수/좋아요)
   - 날짜 범위 필터 선택
   ↓
3. API 호출 (/api/reels/ranking)
   - PostgreSQL에서 데이터 조회
   - 정렬 및 필터링 적용
   ↓
4. 데이터 반환
   - 릴스 목록 및 최신 메트릭
   ↓
5. 프론트엔드 처리
   - 일주일 단위 그룹화
   - ReelCard 컴포넌트로 렌더링
   ↓
6. 사용자 상호작용
   - 카드 클릭 → MetricModal 표시
   - 메트릭 히스토리 API 호출
   - 시계열 데이터 표시
```

## 📊 데이터 구조

### Reel 인터페이스

```typescript
interface Reel {
  id: number
  reel_id: string
  link: string
  thumbnail_url: string | null
  author: string | null
  creator_profile_image: string | null
  title: string | null
  music: string | null
  country_code: string | null
  likes: number | null
  comments: number | null
  views: number | null
  recorded_at: string | null
  created_at: string
}
```

### WeekGroup 인터페이스

```typescript
interface WeekGroup {
  weekStart: Date
  weekEnd: Date
  reels: Reel[]
}
```

## 🎨 UI 특징

- **다크 테마**: 그라데이션 배경 (gray-900 → gray-800)
- **반응형 디자인**: 모바일/태블릿/데스크톱 지원
  - 모바일: 1열
  - 태블릿: 2열
  - 데스크톱: 3-4열
- **호버 효과**: 카드 확대 및 그림자 효과
- **색상 표시**: 변화율에 따른 색상 (증가: 초록, 감소: 빨강)

## 🔧 설정

### 환경 변수

`.env.local` 파일에 다음 변수를 설정:

```env
DB_HOST=your-db-host
DB_PORT=5432
DB_NAME=instagram_reels_scraper
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_SSL=true
```

### 데이터베이스 연결

- PostgreSQL 연결 풀 사용
- SSL 연결 지원 (AWS RDS 등 클라우드 DB 대응)
- 연결 풀 크기: 최대 20개

## 🚀 배포

### Vercel 배포

1. Vercel에 프로젝트 연결
2. 환경 변수 설정 (Vercel 대시보드)
3. Root Directory를 `web`으로 설정 (필요 시)
4. 자동 배포

### 빌드 명령어

```bash
cd web
npm install
npm run build
```

## 📝 사용 예시

### 기본 사용

```typescript
// 메인 페이지에서 자동으로 랭킹 조회
// 정렬 기준 변경
setSortBy('likes')

// 날짜 범위 필터링
setStartDate('2026-01-01')
setEndDate('2026-01-31')
```

### 컴포넌트 사용

```typescript
// ReelCard 사용
<ReelCard
  reel={reel}
  rank={1}
  onClick={() => handleReelClick(reel)}
  formatNumber={formatNumber}
  formatDate={formatDate}
/>

// MetricModal 사용
<MetricModal
  reel={selectedReel}
  onClose={() => setShowModal(false)}
/>
```

## ⚠️ 주의사항

1. **프로필 이미지 CORS 문제**: Instagram CDN 이미지는 직접 로드할 수 없으므로 프록시 API 사용
2. **SSL 연결**: AWS RDS 등은 SSL 연결을 요구하므로 `DB_SSL=true` 설정 필요
3. **이미지 최적화**: Next.js Image 컴포넌트는 Instagram CDN 도메인을 `next.config.js`에 추가해야 함

## 🔗 관련 문서

- `database/schema.sql` - 데이터베이스 스키마
- `database/USAGE.md` - 데이터베이스 사용 가이드
- `web/README.md` - 웹 서비스 사용 가이드

