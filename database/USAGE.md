# 데이터베이스 사용 가이드

## 1. 데이터베이스 설정

`.env` 파일에 다음 설정을 추가하세요:

```env
# PostgreSQL 데이터베이스 설정
DB_ENABLED=true
DB_HOST=your-db-host
DB_PORT=5432
DB_NAME=instagram_reels_scraper
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

## 2. 테이블 생성

SQL 스크립트를 실행하여 테이블을 생성합니다:

```bash
psql -h your-db-host \
     -p 5432 \
     -U your-db-user \
     -d instagram_reels_scraper \
     -f database/schema.sql
```

## 3. 의존성 설치

```bash
poetry install
```

## 4. 사용 방법

### 수집 모듈 (scraper.py)

DB가 활성화되면 자동으로 데이터베이스에 저장됩니다:

```python
from src.config import load_config
from src.scraper import InstagramReelsScraper

config = load_config()
scraper = InstagramReelsScraper(config=config)

# 로그인
scraper.login()

# 릴스 수집 (자동으로 DB에 저장됨)
scraper.start_collecting_reels()
```

### 추적 모듈 (views_tracker.py)

DB가 활성화되면 조회수 추적 시 자동으로 DB에 업데이트됩니다:

```python
from pathlib import Path
from src.config import load_config
from src.views_tracker import ReelViewsTracker

config = load_config()
tracker = ReelViewsTracker(config=config)

# 로그인
tracker.login()

# 조회수 추적 (자동으로 DB에 업데이트됨)
input_file = Path("output/reels_data_20260101_143155.json")
tracker.track_views(input_file)
```

## 5. 데이터베이스 비활성화

파일 저장만 사용하려면 `.env`에서:

```env
DB_ENABLED=false
```

또는 설정을 제거하면 기본값(false)이 사용됩니다.

## 6. 중복 처리

- **reel_id 기준 중복 체크**: 같은 reel_id는 한 번만 저장됩니다
- **크리에이터는 여러 릴스 가질 수 있음**: author 필드는 UNIQUE가 아닙니다
- **시계열 추적**: reel_metrics 테이블에 시간별로 통계를 기록합니다

## 7. 데이터 조회 예시

```sql
-- 최근 수집된 릴스 조회
SELECT r.reel_id, r.author, r.title, rm.views, rm.likes, rm.recorded_at
FROM reels r
LEFT JOIN LATERAL (
    SELECT views, likes, recorded_at
    FROM reel_metrics
    WHERE reel_id = r.id
    ORDER BY recorded_at DESC
    LIMIT 1
) rm ON true
ORDER BY r.created_at DESC
LIMIT 10;

-- 크리에이터별 릴스 수
SELECT author, COUNT(*) as reel_count
FROM reels
WHERE author IS NOT NULL
GROUP BY author
ORDER BY reel_count DESC;

-- 조회수 변화 추적
SELECT 
    r.reel_id,
    r.author,
    rm.recorded_at,
    rm.views,
    rm.likes,
    rm.comments
FROM reel_metrics rm
JOIN reels r ON rm.reel_id = r.id
WHERE r.reel_id = 'DS4U0UKgGt9'
ORDER BY rm.recorded_at DESC;
```

## 8. 트러블슈팅

### 연결 실패
- DB 설정이 올바른지 확인
- 네트워크 연결 확인
- 데이터베이스가 실행 중인지 확인

### 테이블이 없음
- `database/schema.sql` 스크립트를 실행했는지 확인

### 중복 오류
- `reels.reel_id`는 UNIQUE 제약이 있습니다
- 같은 reel_id는 자동으로 업데이트됩니다 (새로 생성되지 않음)

