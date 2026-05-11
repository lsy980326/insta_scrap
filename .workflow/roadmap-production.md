# 운영 환경 전환 로드맵 (최종)

**목표**: 1주일 내 운영 서버 투입 — **안정성 최우선**
**기준일**: 2026-03-11
**대상 국가**: KR / JP / **US** (3국가)
**인프라 확정**: Lightsail $24/국가 + NordVPN + 서버 Cron

---

## 현재 상태 (최종 업데이트: 2026-05-11)

> 이 섹션은 대화 시작 시 항상 확인 — 실제 서버/코드 상태 기준으로 갱신

### 서버 운영 상태

| 국가 | IP | 상태 | VPN | 비고 |
|------|----|------|-----|------|
| KR | `43.200.196.211` | ✅ 운영 중 | South Korea / Seoul | D9-A 스케줄 (09-13 + 15-21 KST) |
| JP | `43.201.192.125` | ✅ 운영 중 | Japan / **Osaka** | VPN 오사카 고정 (run_safe.sh 수정), 신규 계정(yamamoto980326) |
| US | `15.165.103.58` | ✅ 운영 중 (고정 IP) | United States / **Seattle** | git pull 불가(NordVPN 차단) → scp 배포 |

> **⚠️ 2026-05-11 장애 복구**: JP/US 수집 중단
> - JP: run_safe.sh vpn_country()가 `Japan`(도쿄)으로 매핑 → 도쿄 IP가 2FA 트리거 → 로그인 실패 루프. `Osaka`로 수정 후 복구
> - US: 수집 중 NordVPN WireGuard 라우팅 깨짐 → `ERR_NAME_NOT_RESOLVED`로 크래시. 재부팅 후 복구
> - 대응: run_safe.sh monitor_steal()에 수집 중 ping 체크 추가 — 라우팅 깨지면 자동 재연결 후 재시작
>
> **⚠️ 2026-04-10 장애 복구**: 3국 동시 수집 중단
> - JP: `.env` git-crypt 암호화 상태로 배포됨 → scp 재배포로 복구
> - KR/US: NordVPN WireGuard 라우팅 테이블 깨짐 → `disconnect && connect` 로 복구
> - `.env` 변경 시 반드시 scp로 3개 서버 전부 배포할 것 (server-settings.md 배포 절차 참조)

### 남은 TODO

| 항목 | 상태 | 비고 |
|------|------|------|
| 고객사 DB 테이블 명세서 전달 | ⏳ 대기 | 로드맵 하단 SQL 스펙 참조 |

### 완료된 주요 단계

- ✅ D1~D6: DB 테이블명 변경, S3 아카이빙, 알림/헬스체크, KR 서버 전체 셋업
- ✅ D7: JP 서버 셋업 (2026-03-20)
- ✅ D8: US 서버 셋업 (2026-04-03, KR 스냅샷 기반)
- ✅ D9: 버스트 크레딧 자동 관리 A/B/C/D (2026-03-31 ~ 2026-04-09)
  - A: 운영시간 축소 (09-13 + 15-21 KST), 3서버 동일 적용
  - B: run_safe.sh steal time 체크 (시작 전)
  - C: Chrome 렌더러 제한
  - D: 수집 중 steal 모니터링 + 종료 후 steal 수준별 추가 휴식 (5%=20분, 10%=30분, 20%=40분, 50%=60분)
- ✅ session_manager.py 세션 검증 버그 수정 (accounts/edit 사용, 2026-04-03)
- ✅ scraper.py 전체 로그인 전 쿠키 클리어 (만료 세션 간편로그인 화면 방지, 2026-04-09)
- ✅ track_views.py flock 중복 실행 방지 (2026-04-09)
- ✅ JP 신규 계정 적용 + 기존 JP 데이터 DB 초기화 (2026-04-08)
- ✅ JP VPN 도쿄 → 오사카 변경 (2026-04-10, 도쿄 IP가 2FA 트리거 → 오사카 정상)
- ✅ run_safe.sh: force-start 플래그 (`/tmp/insta-force-start-{profile}`) 추가 — 15분 steal 대기 1회 스킵 (2026-04-10)
- ✅ run_safe.sh: Slack 알림 추가 — 수집 시작, 휴식 시작(steal 수준별) (2026-04-10)
- ✅ notifier.py: send_scrape_start / send_rest_start / send_track_start / send_track_progress / send_track_summary(failed_count) 추가 (2026-04-10)
- ✅ views_tracker.py: span.x1vvkbs 기반 조회수 추출로 전면 교체 (Instagram div._aaj_ 클래스 제거 대응, 2026-04-10)
- ✅ views_tracker.py: 직접 URL 폴백 추가 (`/reels/{id}/`) — 크리에이터 페이지에 없는 오래된 릴스 대응 (2026-04-10)
- ✅ views_tracker.py: 일본어/영어 숫자 파싱 추가 (万/億/K/M, JP·US 추적 0건 문제 해결) (2026-04-10)
- ✅ views_tracker.py: track_from_db에 Slack 추적 진행 알림 연동 (2026-04-10)
- ✅ models.py: ReelMetric.recorded_at KST 저장 수정 (`func.current_timestamp()` UTC → Python-side `_kst_now()`, KR/JP/US 전체 배포) (2026-04-10)

---

## 고객사 요구사항 (확정)


| 항목        | 내용                                                                |
| --------- | ----------------------------------------------------------------- |
| 수집 국가     | 한국(KR), 미국(US), 일본(JP)                                            |
| 화면 기능     | 릴스별 좋아요/조회수 등 지표별 정렬 (UI는 고객사 개발)                                 |
| 납품 범위     | **수집 모듈 + DB 저장까지** (웹 화면은 고객사)                                   |
| DB        | 고객사 AWS RDS — `dbmaster` (운영 DB, 기존 데이터 삭제 금지)                    |
| 테이블 명명 규칙 | **접두사 `instagram_`** (예: `instagram_reels`, `instagram_creators`) |
| AWS 계정    | 고객사 계정에서 작업                                                       |


---

## 확정된 인프라 구조

```
[ Lightsail $24 - KR ]   [ Lightsail $24 - JP ]   [ Lightsail $24 - US ]
  NordVPN south_korea      NordVPN japan             NordVPN united_states
  --profile kr             --profile jp              --profile us
  Cron: 수집 + 추적        Cron: 수집 + 추적         Cron: 수집 + 추적
         │                        │                         │
         └────────────────────────┼─────────────────────────┘
                                  ▼
                    [ AWS RDS - dbmaster (고객사 공유 DB) ]
                    테이블: instagram_reels, instagram_reel_metrics 등
                                  │
                                  ▼
                    [ 고객사 웹 UI (고객사 개발) ]
```

### 비용 구조 (확정)


| 운영 국가        | 월 비용(USD) | 월 비용(원)   | 구성                           |
| ------------ | --------- | --------- | ---------------------------- |
| 1개국          | **$28**   | 약 4.0만 원  | Lightsail $24 + NordVPN ~$4  |
| 2개국          | **$52**   | 약 7.4만 원  | Lightsail $48 + NordVPN ~$4  |
| **3개국 (현재)** | **$76**   | 약 10.8만 원 | Lightsail $72 + NordVPN ~$4  |
| 5개국          | **$124**  | 약 17.6만 원 | Lightsail $120 + NordVPN ~$4 |
| 국가 추가        | **+$24**  | +약 3.4만 원 | Lightsail 1대 추가 (VPN 동일 계정)  |


> NordVPN: 1계정 최대 10대 → 국가 늘어도 VPN 비용 고정 (~$4/월, 연간 선결제 기준)

---

## 핵심 변경 사항

### 1. DB 테이블명 접두사 변경 (고객사 요구)


| 기존 테이블명             | 변경 후 테이블명                     |
| ------------------- | ----------------------------- |
| `reels`             | `instagram_reels`             |
| `reel_metrics`      | `instagram_reel_metrics`      |
| `creators`          | `instagram_creators`          |
| `scraping_sessions` | `instagram_scraping_sessions` |
| `account_sessions`  | `instagram_account_sessions`  |


**영향 파일**: `src/database/models.py` — `__tablename__` 변경 (5개)
→ 앱 코드는 ORM 경유라 SQL 직접 참조 없음, `__tablename__`만 변경하면 됨

### 2. 3국가 프로파일 (KR / JP / US)

- **KR**: `accounts.yaml` - `cxv963@naver.com` (기존)
- **JP**: `accounts.yaml` - `98inya@gmail.com` (기존)
- **US**: `accounts.yaml` - ⚠️ **실계정 입력 필요** (`YOUR_US_INSTAGRAM_ACCOUNT`)
  - 미국 IP NordVPN exit node: `nordvpn connect united_states`
  - 브라우저 로케일: `en-US`, 타임존: `America/New_York`

### 3. 썸네일 URL 만료 (반드시 해결)

Instagram CDN URL은 **24~48시간 후 만료** → 웹 이미지 깨짐

- 해결: 수집 직후 S3 webp 압축 저장 → DB URL 교체
- S3 비용: 50GB 이하 **$1~2/월** (무시 가능)
- **고객사 AWS 계정에 S3 버킷 생성 필요** → AWS 콘솔(`517994519587`)에서 생성

---

## .env 핵심 변경 내역

```diff
- DB_HOST=ls-ecc3f...     (기존 개발 DB)
+ DB_HOST=ls-54260...     (고객사 운영 DB)
- DB_NAME=instagram_reels_scraper
+ DB_NAME=dbmaster
- DB_PASSWORD=OMDa{iNn6...
+ DB_PASSWORD=trendboard
- PLAYWRIGHT_HEADLESS=false
+ PLAYWRIGHT_HEADLESS=true
- SESSION_STORAGE_TYPE=file
+ SESSION_STORAGE_TYPE=db
- LOG_FILE=
+ LOG_FILE=logs/scraper.log
+ S3_ENABLED=false         (버킷 생성 후 활성화)
+ S3_BUCKET=               (TODO: 고객사 버킷명 입력)
+ AWS_ACCESS_KEY_ID=       (TODO: 고객사 IAM 키 입력)
+ AWS_SECRET_ACCESS_KEY=   (TODO: 고객사 IAM 키 입력)
```

---

## 주간 로드맵 (D1~D7)

### D1 (3/12) — DB 테이블명 변경 + 코드 안정화 ✅ 완료

- ✅ `src/database/models.py` — `__tablename__` 5개 → `instagram_*` 변경
- ✅ `src/config.py` — S3 설정 필드 추가 (s3_enabled, s3_bucket, aws_*)
- ✅ `src/utils/logger.py` — rotation="1 day", retention="30 days", compression="zip"
- ✅ `src/database/connection.py` — `pool_pre_ping=True` 확인
- ✅ `pyproject.toml` — boto3, pillow 추가
- ⏳ **고객사 DB 연결 확인** — 운영 서버 투입 전 .env 적용 후 테스트 필요

---

### D2 (3/13) — 썸네일 S3 아카이빙 모듈 ✅ 완료

- ✅ `src/thumbnail_archiver.py` — ThumbnailArchiver 구현 (CDN → webp → S3)
  - `archive_reel_thumbnail()`, `archive_profile_image()`, `batch_archive()`
  - 실패 시 원본 CDN URL fallback (수집 중단 없음)
- ✅ `src/scraper.py` — `save_to_json()` 내 `batch_archive()` 통합 (`S3_ENABLED=false` 시 건너뜀)

**S3 저장 경로**: `instagram/thumbnails/{kr|jp|us}/{reel_id}.webp`, `instagram/profiles/{username}.webp`

**고객사 S3 버킷 생성** ✅ 완료

- 버킷명: `trendboard-mda`
- `.env` `S3_ENABLED=true`, `S3_BUCKET=trendboard-mda`, IAM 키 설정 완료

---

### D2.5 (3/12~13) — 로컬 기능 테스트 ✅ 완료

**서버 투입 전 로컬에서 End-to-End 검증 필수**

#### 수집 모듈 테스트

```bash
# 1. 환경 확인
poetry install

# 2. KR 프로파일로 수집 테스트 (headless=false로 육안 확인)
PLAYWRIGHT_HEADLESS=false poetry run python main.py --profile kr

# 기대 결과:
# - 로그인 성공
# - 릴스 수집 (최소 10건 이상)
# - DB에 instagram_reels, instagram_reel_metrics 저장 확인
# - output/kr/*.json 파일 생성 확인
```

#### 추적 모듈 테스트

```bash
# 수집 결과 JSON으로 추적 테스트
poetry run python track_views.py output/kr/reels_data_YYYYMMDD_*.json

# 기대 결과:
# - 로그인 성공 (세션 재사용 or 신규 로그인)
# - 각 릴스의 views/likes/comments 추출
# - instagram_reel_metrics 시계열 저장 확인
```

#### DB 저장 확인 쿼리

```sql
-- 수집 확인
SELECT country_code, COUNT(*) FROM instagram_reels GROUP BY country_code;

-- 지표 확인
SELECT r.reel_id, m.views, m.likes, m.comments, m.recorded_at
FROM instagram_reels r
JOIN instagram_reel_metrics m ON m.reel_id = r.id
ORDER BY m.recorded_at DESC LIMIT 10;
```

**통과 기준**: KR 10건 이상 수집 + DB 저장 정상 확인 → D3 진행

---

### D2.5 테스트 결과 기록

> 테스트 일자: 2026-03-12

#### KR 수집 모듈 테스트

| 항목 | 결과 | 비고 |
| --- | --- | --- |
| 로그인 성공 | ✅ | |
| 릴스 수집 건수 | ✅ | 10건 이상 확인 |
| instagram_reels 저장 | ✅ | 20건 확인 |
| instagram_reel_metrics 저장 | ✅ | 48건 확인 |
| output/kr/*.json 생성 | ✅ | 수집 성공으로 생성 확인 |
| 이슈 | - | |

#### KR 추적 모듈 테스트

| 항목 | 결과 | 비고 |
| --- | --- | --- |
| 로그인 성공 (세션 재사용) | ✅ | |
| views/likes/comments 추출 | ✅ | |
| instagram_reel_metrics 시계열 저장 | ✅ | |
| 이슈 | ✅ 수정 완료 | 로그인 실패 후 `_is_logged_in=False` 상태로 track_views() 진입 시 재로그인 안 되는 버그. 크리에이터 페이지 로그인 리다이렉트 시 재로그인 미시도 버그. 두 군데 수정. |

#### 종합 판정

- [x] KR E2E 통과 → D3 서버 셋업 진행 가능

---

### D3 (3/14) — Lightsail 서버 셋업 + NordVPN (3대) ✅ KR 완료

> NordVPN 설치 및 로그인 완료 ✅

**서버 초기 셋업** — `scripts/server_setup.sh` 한 번 실행으로 완료:

```bash
# 서버에서 실행 (KR 서버 예시)
git clone {repo_url} /srv/insta_scrap
cd /srv/insta_scrap
bash scripts/server_setup.sh kr   # kr | jp | us
```

스크립트가 자동 처리하는 항목:
- Ubuntu 의존성 패키지 설치
- 서버 타임존 설정 (국가별 자동)
- Poetry + 프로젝트 의존성 설치
- Playwright Chromium 설치
- NordVPN systemd 자동 연결 서비스 등록
- Cron 등록 (수집 02:00 + 추적 06:00)

**서버 초기 셋업 (수동 참고)** (국가당 1회 반복):



e9f2ab45bb6497b40839803bb987c3191365f8556ae108f808f78b2487ea634b

```bash
# 1. Ubuntu 기본
sudo apt update && sudo apt install -y git curl

# 2. Python / Poetry
sudo apt install -y python3 python3-pip
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc

# 3. NordVPN 설치 + 국가별 연결
sh <(curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh)
nordvpn login
# KR 서버: south_korea / JP: japan / US: united_states
nordvpn set autoconnect on south_korea
nordvpn connect

# 4. 프로젝트 세팅
git clone {repo_url} /srv/insta_scrap
cd /srv/insta_scrap
poetry install --no-dev
poetry run playwright install chromium
poetry run playwright install-deps chromium

# 5. 헤드리스 Linux stealth 검증 (핵심 — 통과해야 진행)
poetry run python main.py --profile kr
# → 정상 수집 확인 필수
```

**NordVPN 재부팅 자동 연결** (`/etc/systemd/system/nordvpn-autoconnect.service`):

```ini
[Unit]
After=nordvpnd.service network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/nordvpn connect south_korea
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

**Linux 헤드리스 stealth 이슈 대응**:

- `--no-sandbox`, `--disable-dev-shm-usage` 플래그 확인 (`src/browser.py`)
- User-Agent 재검토 (macOS → Linux UA 변경 필요 시)
- 스크린샷 저장해서 로그인 상태 확인

---

### D3.5 (3/12) — 버그 수정 ✅ 완료

- ✅ `src/scraper.py` — title 추출 버그 수정 완료
  - 기존: 음악 span과 동일 CSS 클래스 공유 → 음악 제목이 title로 잘못 수집
  - 수정: `span.x6ikm8r.x10wlt62.xuxw1ft:not(.xlyipyv)` — 음악 span(`xlyipyv` 클래스)을 CSS 레벨에서 제외
  - fallback: `div[dir="auto"]` 탐색 (오디오 링크 내부 제외)
  - root 범위로 스코프 변경 (page → root, 현재 릴스 컨테이너 기준)

---

### D4 (3/13) — Cron + 자동 파이프라인 ✅ KR 완료

**각 서버 crontab 설정** (서버별로 독립 등록):

```cron
# KR 서버 — /etc/cron.d/insta-scraper-kr
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

# 매일 02:00 KR 릴스 수집 — 로그는 loguru 파일로만 기록 (cron stdout 버림)
0 2 * * * scraper cd /srv/insta_scrap && poetry run python main.py --profile kr > /dev/null 2>&1

# 매일 06:00 KR 조회수 추적
0 6 * * * scraper cd /srv/insta_scrap && poetry run python track_views.py output/kr/$(date +\%Y\%m\%d)*.json --profile kr > /dev/null 2>&1

# 매주 일요일 03:00 output JSON 파일 30일 이상 삭제
0 3 * * 0 scraper find /srv/insta_scrap/output -name "*.json" -mtime +30 -delete
```

> ⚠️ cron stdout을 일별 파일로 리다이렉션하면 로그가 2중으로 쌓임 (loguru 파일 + cron 별도 파일).
> loguru가 이미 `logs/scraper.log`에 기록하므로 cron에서는 `/dev/null`로 버린다.

---

### D4.5 — 로그 용량 관리 (Lightsail 80GB 디스크 보호)

**문제 분석**: Lightsail $24 = 80GB SSD. OS + Chromium + Poetry 환경으로 여유 공간 ~65GB.
수집/추적 각 1회 = Playwright 로그 포함 시 **5~30MB** → 일 2회 × 30일 = 최대 **1.8GB/월**.
정상 운영 시 허용 범위지만, 에러 폭발(traceback 반복) 시 GB 단위로 급증 가능.

**현재 설정 문제점**:

| 문제 | 내용 |
| --- | --- |
| cron 이중 로그 | `>> logs/collect_YYYYMMDD.log` + loguru 파일 → 동일 로그 2배 |
| retention 30일 | zip 압축해도 30개 × 최대 50MB = 최대 1.5GB 상시 점유 |
| 운영 로그 레벨 | DEBUG/INFO 모두 파일 기록 → Playwright 상세 로그 포함 시 과다 |
| output JSON 누적 | 매일 생성되는 JSON이 삭제 정책 없으면 무제한 누적 |

**개선 방안 (D4.5 적용)**:

#### 1. `src/utils/logger.py` — 운영 환경 rotation 조정

```python
# 운영 서버: 크기 기반 rotation + 짧은 retention
setup_logger(
    log_level="WARNING",       # 운영: WARNING 이상만 파일 저장 (INFO → stderr)
    log_file=Path("logs/scraper.log"),
    rotation="50 MB",          # 크기 기반 (1일 대신) — 에러 폭발 방어
    retention=10,              # 최대 10개 파일 보관 (~500MB 상한)
)
```

> `.env`에서 `LOG_LEVEL=WARNING` + `LOG_ROTATION=50 MB` + `LOG_RETENTION=10` 환경변수로 제어 권장.

#### 2. `src/config.py` — 로그 설정 필드 추가

```python
log_level: str = Field(default="INFO", description="로그 레벨")
log_rotation: str = Field(default="50 MB", description="로그 rotation 기준")
log_retention: int | str = Field(default=10, description="보관 파일 수 또는 기간")
```

#### 3. 시스템 logrotate — `/etc/logrotate.d/insta-scraper`

```
/srv/insta_scrap/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

> loguru rotation과 logrotate 둘 다 설정 시 loguru를 size 기반으로, logrotate를 time 기반 백업용으로 사용.

#### 4. 디스크 용량 모니터링 (`scripts/health_check.py`에 추가)

```python
import shutil

def check_disk_usage(path: str = "/srv/insta_scrap", threshold_pct: float = 70.0) -> bool:
    """디스크 사용률이 threshold 초과 시 알림"""
    total, used, free = shutil.disk_usage(path)
    used_pct = used / total * 100
    if used_pct >= threshold_pct:
        notifier.send_error("disk", f"디스크 사용률 {used_pct:.1f}% (임계값 {threshold_pct}%)")
        return False
    return True
```

#### 5. output JSON 자동 정리

```cron
# 매주 일요일 03:00 — output JSON 30일 이상, logs zip 10일 이상 삭제
0 3 * * 0 scraper find /srv/insta_scrap/output -name "*.json" -mtime +30 -delete
0 3 * * 0 scraper find /srv/insta_scrap/logs -name "*.zip" -mtime +10 -delete
```

**용량 상한 설계 목표**: 로그 + output JSON = **최대 3GB 이하** 상시 유지

> JP 서버: `--profile jp`, `output/jp/`
> US 서버: `--profile us`, `output/us/` (EST 기준 시간 조정 고려)

**US 서버 시간대 고려**:

- 서버 타임존을 `America/New_York`으로 설정하거나
- KR/JP와 동일한 UTC 기준으로 cron 시간만 조정

**파이프라인 흐름**:

```
[ 07:00~23:00 수집 전용 ]
systemd insta-scraper@{국가}   ← 20분 수집/40분 휴식 사이클
  → 로그인 (세션 캐시 → 실패 시 전체 로그인)
  → start_collecting_reels()
  → ThumbnailArchiver.batch_archive()    ← S3 저장
  → _save_to_db()  ← instagram_* 테이블에 저장

[ 00:00~07:00 추적 전용 ]
Cron 00:00 track_views.py --from-db --days 7 --profile {국가}
  → DB SELECT 최근 7일 릴스 → 크리에이터별 그룹화
  → 배치 추적 (TRACK_BATCH_SIZE개 → sleep → 반복)
  → instagram_reel_metrics INSERT

[ Cron 07:00 ] systemctl start insta-scraper@{국가}  ← 수집 재개
[ Cron 23:00 ] systemctl stop insta-scraper@{국가}   ← 수집 중단
[ Cron 매시간 ] health_check.py --profile {국가}
  → Slack: VPN/DB/수집건수/디스크 상태 전송
```

---

### D5 (3/13) — 알림 + 헬스체크 ✅ 완료

**신규 파일**: `src/utils/notifier.py`, `scripts/health_check.py`

**알림 조건 (국가 구별: 🇰🇷/🇯🇵/🇺🇸)**:

- 수집 0건 → `send_zero_collect(profile)`
- `LoginError` 발생 → `send_login_error(profile, detail)`
- DB 연결 실패 → `send_db_error(profile, detail)`
- S3 업로드 실패 → `send_s3_error(profile, fail_count)`
- 디스크 70% 초과 → `send_disk_warning(profile, used_pct)`
- 수집/추적 완료 → `send_summary` / `send_track_summary`

**헬스체크 cron (매시간)**:

```bash
0 * * * * ubuntu cd /srv/insta_scrap && poetry run python scripts/health_check.py --profile kr > /dev/null 2>&1
```

확인 항목: NordVPN 연결 상태, DB ping, 오늘 수집 건수, 디스크 사용률(70% 임계값)

---

### D6 (3/14) — KR 운영 검증 + 서버 장애 대응 ✅ 완료

#### 장애 발생 및 조치 (2026-03-14 00:54 KST)

**증상**: 운영 서버 속도 급격히 저하

**원인 분석**:

| 항목 | 상태 |
|------|------|
| RAM | 3.7GB 전부 사용 (여유 104MB), 스왑 없음 |
| CPU steal | **86.7%** — AWS Lightsail CPU 버스트 크레딧 소진 |
| 부하 평균 | 10.15 (2코어 대비 5배 과부하) |
| Chrome 프로세스 | **18개** 동시 실행 |
| main.py 프로세스 | **2개** 동시 실행 (PID 15140 Mar13 좀비 + PID 31124 신규) |

**근본 원인**: `Restart=always` 서비스가 이전 프로세스가 살아있는 상태에서 새 인스턴스를 띄워 Chrome이 18개까지 누적됨

**조치 내용**:

```bash
# 1. 좀비 프로세스 강제 종료
kill -9 15140 15139 31124

# 2. 잔여 Chrome 전부 정리 (kill 후 자동 종료됨)
ps aux | grep -E 'chrome|playwright' | grep -v grep | awk '{print $2}'
# → 출력 없음 (이미 정리됨)

# 3. 중복 실행 방지 래퍼 스크립트 생성
# /srv/insta_scrap/run_safe.sh
#!/bin/bash
PROFILE="${1:-kr}"
LOCKFILE="/tmp/insta-scraper-${PROFILE}.lock"
exec flock -n "$LOCKFILE" /home/ubuntu/.local/bin/poetry run python main.py --profile "$PROFILE"

chmod +x /srv/insta_scrap/run_safe.sh

# 4. systemd 서비스 업데이트
# /etc/systemd/system/insta-scraper@.service 주요 변경:
#   ExecStart=/srv/insta_scrap/run_safe.sh %i       ← flock 래퍼로 교체
#   KillMode=control-group                           ← 자식 Chrome 포함 전부 킬
#   TimeoutStopSec=30                                ← 30초 내 안 죽으면 강제 킬
#   StandardOutput=journal / StandardError=journal  ← journalctl로 로그 확인 가능

sudo systemctl daemon-reload
sudo systemctl start insta-scraper@kr.service

# 5. 결과 확인
# RAM: 3.7GB → 539MB 사용으로 3.2GB 확보
# 부하: 10.15 → 정상화
```

**중복 방지 원리**: `flock -n`은 락 파일을 획득하지 못하면 즉시 종료(exit 1) → systemd가 `Restart=always`로 재시도하지만 이미 실행 중이면 매번 즉시 종료됨

**서버 로그 확인 명령어**:
```bash
# 실시간 로그
journalctl -u insta-scraper@kr -f

# 최근 100줄
journalctl -u insta-scraper@kr -n 100

# 서비스 상태
sudo systemctl status insta-scraper@kr
```

- ✅ systemd 서비스 active (running) 확인
- ✅ Slack 헬스체크 알림 연결 확인
- ✅ 서버 장애 대응 완료 (중복 프로세스 제거 + 재발 방지)
- ✅ .env git-crypt 암호화 문제 발견 → scp로 직접 배포 방식 확정
- ⏳ 고객사에 DB 테이블 구조 명세서 전달

---

### D6.5 (3/14) — KR 서버 성능 최적화 ✅ 완료

**문제**: 릴스 수집 속도 저하 (릴스당 40초+, CPU steal 86.7%)

**원인 분석 및 조치**:

| 문제 | 원인 | 조치 |
|---|---|---|
| 릴스 페이지 로딩 후 4분 멈춤 | SwiftShader가 비디오 소프트웨어 렌더링으로 CPU 100%+ 사용 → 버스트 크레딧 소진 | 비디오 스트림 차단 |
| 릴스 전환 후 31초 대기 | `page.route("**/*")` 전체 라우팅으로 모든 요청이 Python IPC 경유 | 패턴별 개별 route 등록으로 변경 |
| 마우스 휠 데드락 | `--disable-gpu-compositing` 플래그가 스크롤 이벤트 차단 | 컴포지팅 관련 플래그 제거 |

**적용된 최적화**:
- `browser.py` 뷰포트 1920×1080 → 1280×800
- `browser.py` 비디오/폰트/트래킹 리소스 차단 (패턴별 개별 route)
- `browser.py` SwiftShader 렌더링 최적화 플래그 (`--num-raster-threads=1` 등)
- `scraper.py` navigate_to_reels_tab: 탭 클릭 → `page.goto('/reels/')` 직접 이동
- `scraper.py` sleep 3+2 → 1+1 단축
- `scraper.py` `evaluate()` 개별 호출 → `evaluate_all()` 배치 처리
- `scraper.py` `_find_button_scope_with_fallback` timeout 300ms → 50ms

**결과**: CPU steal 86.7% → **0%**, 릴스당 **5초** 수준으로 안정화

---

### D6.7 (3/14) — Sentry 에러 트래킹 + burst credit 회복 로직 ✅ 완료

#### 추가 성능 최적화 (2차)

| 항목 | 내용 |
|------|------|
| `--disable-gpu` 플래그 추가 | GPU 프로세스(SwiftShader) 자체 비활성화 시도 (Playwright 내부 강제 플래그로 완전 제거는 불가, 77% → 37%로 감소) |
| `--disable-webgl`, `--disable-webgl2`, `--disable-3d-apis` | WebGL/3D API 비활성화 → SwiftShader 작업량 추가 감소 |

#### Sentry 에러 트래킹 통합

- `src/utils/sentry.py` — **신규**: `init_sentry()`, `capture_exception()` 헬퍼
- `pyproject.toml` — `sentry-sdk ^2.0.0` 추가
- `src/config.py` — `sentry_dsn` 필드 (미설정 시 완전 비활성화)
- `main.py`, `track_views.py` — 시작 시 `init_sentry()`, 예외 지점에 `capture_exception()`
- **비용 설계**: `traces_sample_rate=0` + `profiles_sample_rate=0` → 에러 캡처만 (무료 플랜 5K/월)

#### `collected_at` 컬럼 추가

- `src/database/models.py` — `instagram_reels`에 `collected_at TIMESTAMP` 추가 (수집 시각)
- DB 마이그레이션: `ALTER TABLE instagram_reels ADD COLUMN collected_at TIMESTAMP DEFAULT NOW()`

#### Burst Credit 회복 사이클 (근본 해결)

**문제**: Lightsail $24 = burstable CPU → 24/7 Chrome 운영 시 크레딧 고갈 → CPU steal 80%+ → 속도 급저하

**해결**: 20분 수집 → 40분 휴식 사이클

```
[20분 수집] → 정상 종료 → [systemd 40분 대기] → [20분 수집] → 반복
```

- `src/config.py` — `scrape_run_minutes: int | None` 추가
- `src/scraper.py` — `while True` 루프에 `run_deadline` 체크 (시간 초과 시 정상 종료)
- `.env` — `SCRAPE_RUN_MINUTES=20`
- systemd — `RestartSec=60` → `RestartSec=2400` (40분)
- **크레딧 회복 원리**: 프로세스 완전 종료(Chrome 포함) → CPU ~0% → 40분간 크레딧 적립

---

### D6.8 (3/14) — 추적 모듈 DB 기반 전환 ✅ 완료

**문제**: 현재 `track_views.py`는 당일 JSON 파일만 읽어 오늘 수집분만 추적
→ DB에 누적된 과거 릴스는 첫 수집 이후 metrics가 영구 단절됨

**목표**: 추적 대상을 JSON 파일이 아닌 DB 기반으로 전환

#### 수정 범위

| 파일 | 변경 내용 |
|------|-----------|
| `src/views_tracker.py` | `track_from_db(days: int = 7)` 메서드 추가 — DB에서 최근 N일 릴스 로드 후 추적 |
| `track_views.py` | `--from-db` / `--days N` 플래그 추가 (기존 JSON 방식과 병행 유지) |
| cron (각 서버) | 07:00 수집 start / 23:00 수집 stop / 00:00 추적 실행으로 시간대 완전 분리 |

#### 동작 흐름 (변경 후) — 시간대 분리 방식

```
00:00 ~ 07:00  추적 전용   track_views.py --from-db --days 7 (배치 휴식 포함)
07:00 ~ 23:00  수집 전용   insta-scraper@kr.service (20분 수집/40분 휴식 사이클)
23:00          수집 서비스 stop (cron)
```

**Chrome 완전 시간 분리** → 동시 실행 불가, 크레딧 충돌 없음, stop/start 래퍼 불필요

```cron
# 07:00 수집 시작
0 7 * * * ubuntu sudo systemctl start insta-scraper@kr.service

# 23:00 수집 중단 (추적 준비)
0 23 * * * ubuntu sudo systemctl stop insta-scraper@kr.service

# 00:00 추적 시작 (7시간 여유, 배치 휴식 포함해도 충분)
0 0 * * * ubuntu cd /srv/insta_scrap && poetry run python track_views.py --from-db --days 7 --profile kr > /dev/null 2>&1
```

#### `days` 기준 설계

| days | 대상 | 이유 |
|------|------|------|
| 7일 | 최근 7일 수집 릴스 | 바이럴 피크가 보통 1주일 이내 |
| 30일 | 장기 트렌드 추적 원하면 | 추적 시간 증가 (릴스 수 × 크롤링 시간) |

> 초기값 `--days 7` 권장. 릴스 누적량에 따라 조정.

#### 추적 모듈 burst credit 문제 및 최적화

**문제**: 7일치 릴스가 수백 개 쌓이면 추적 1회 실행 시간이 길어짐 → 수집과 동일한 크레딧 고갈 문제 발생

**해결 방향**:

1. **추적 중간 휴식**: `TRACK_BATCH_SIZE`개 추적 후 일정 시간 sleep (크레딧 소모 속도 조절)
   ```
   100개 추적 → 5분 sleep → 100개 추적 → 5분 sleep → ...
   ```

2. **수집 최적화와 동일한 렌더링 플래그 적용**: 추적 모듈도 동일한 `BrowserManager` 사용하므로 이미 적용됨 (`--disable-gpu` 등)

3. **추적 대상 우선순위화**: 최근 수집일수록 먼저 추적 (조회수 변화가 큰 구간)
   ```sql
   ORDER BY collected_at DESC  -- 최신 릴스 먼저
   ```

4. **크리에이터 페이지 방문 최소화**: 현재 크리에이터별 그룹화 이미 적용됨 (1크리에이터 = 1페이지 방문). 유지.

**추가 구현 항목**:

| 항목 | 내용 |
|------|------|
| `config.py` | `track_batch_size: int = 100`, `track_batch_sleep: int = 300` (초) 추가 |
| `views_tracker.py` | `track_from_db()` 내 배치 단위로 sleep 삽입 |

#### 추적 모듈 전용 브라우저 최적화 (필수)

**추적 페이지 특성**: 크리에이터 프로필 페이지 (`/reels/` 탭) — 해당 크리에이터의 **모든 릴스 썸네일 그리드**가 로드됨
- 수집과 달리 영상 재생 없음 → 비디오 스트림 차단 이미 효과적
- **문제**: 썸네일 이미지 수십~수백 장이 한 번에 로드 → 이미지 요청 폭증 → 렌더링 부하
- **문제**: 스크롤 다운하며 릴스 찾을 때 DOM 계속 증가 → 메모리/CPU 상승

**추가 차단 대상** (수집엔 없는 추적 전용):
```python
# 크리에이터 릴스 그리드의 썸네일 이미지 차단 (views 수집엔 img 불필요)
for _pat in ("**/*.jpg", "**/*.jpeg", "**/*.png", "**/*.webp", "**/*.gif"):
    page.route(_pat, _abort)
```

> ⚠️ 수집 모듈에는 적용 금지 — 수집은 thumbnail_url(CDN) 추출이 필요하므로

**기타 추적 전용 최적화**:
- `playwright_timeout` 추적은 더 짧게 설정 가능 (페이지 단순, 로그인 상태)
- 크리에이터 페이지 로드 후 필요한 릴스만 찾으면 즉시 다음 크리에이터로 이동 (스크롤 최소화)

---

### D6.9 (3/14) — CPU Steal / Burst Credit 모니터링 ✅ 완료

**구현 내용**:

| 항목 | 내용 |
|------|------|
| `scripts/health_check.py` | `check_cpu_steal()` 추가 — `/proc/stat` 2회 측정(1초 간격)으로 steal% 계산 |
| 임계값 | steal > 30% 시 Slack 경고 (`⚠️ CPU steal XX% — 버스트 크레딧 고갈`) |
| 헬스체크 요약 | 매시간 메시지에 `CPU steal: X.X%` 항목 추가 |
| `notifier.py` | `send_cpu_steal_warning(profile, steal_pct)` 추가 |

---

### D6.10 (3/14) — 운영 안정화 패치 ✅ 완료

#### `collected_at` KST 시각 오류 수정

- **문제**: `datetime.now(KST)` 저장 시 SQLAlchemy가 UTC로 변환 → DB에 +9시간 오차
- **수정**: `.replace(tzinfo=None)` — naive datetime으로 KST 시각 그대로 저장
- **파일**: `src/database/repositories/reel_repository.py`

#### Slack DNS 실패 재시도 로직

- **문제**: NordVPN DNS가 `hooks.slack.com` 못 찾는 경우 알림 소실
- **수정**: `notifier._post()` — 3회 재시도, 5초 간격
- **파일**: `src/utils/notifier.py`

#### 썸네일 이미지 다운로드 DNS 실패 재시도

- **문제**: NordVPN DNS가 `instagram.fcdp1-1.fna.fbcdn.net` (프로필 이미지 CDN) 해석 실패 반복
- **수정**: `_download_and_convert()` — 3회 재시도, 3초 간격
- **파일**: `src/thumbnail_archiver.py`

#### KR 서버 Cron 정리

- **문제**: 이전 JSON 기반 추적 cron이 `/etc/cron.d/insta-scraper-kr`에 잔존
- **수정**: cron 재정비 — 07:00 start / 23:00 stop / 00:00 DB 추적 / 매시간 헬스체크 / 주1회 정리

---

### D6.11 (3/14) — Sentry + 헬스체크 버그 수정 ✅ 완료

#### Sentry sentry-sdk v2 API 호환 수정

- **문제**: `sentry_sdk.Hub.current.client` → v2에서 deprecated, 항상 `False` 반환 → 에러 캡처 전혀 안 됨
- **문제**: `push_scope()` → v2에서 deprecated
- **수정**: `_is_sentry_enabled()` → `sentry_sdk.get_client().dsn`, `push_scope()` → `new_scope()`
- **파일**: `src/utils/sentry.py`

#### 서버 SENTRY_DSN 누락

- **문제**: 서버 `.env`에 `SENTRY_DSN` 미설정 → Sentry 초기화 자체가 안 됨
- **수정**: 로컬 `.env` scp로 서버에 복구 (git stash drop으로 인해 git-crypt 블롭으로 덮어씌워짐)

#### 헬스체크 `수집 0건` 오경보 수정

- **문제**: `Reel.created_at` (Instagram 게시일) 기준으로 오늘 수집 건수 계산 → 오늘 게시된 릴스 없으면 항상 0
- **수정**: `Reel.collected_at` (수집 시각, KST) 기준으로 변경
- **파일**: `scripts/health_check.py`

#### 헬스체크 `get_session` import 오류 수정

- **문제**: `from src.database.connection import get_session` → 함수명 불일치 (`get_db_session`)
- **수정**: `get_db_session` + `init_db` 호출로 수정
- **파일**: `scripts/health_check.py`

#### `get_db_session` contextmanager 누락 수정

- **문제**: `@contextmanager` 없이 raw generator → `with get_db_session()` 실패
- **수정**: `@contextmanager` 데코레이터 추가
- **파일**: `src/database/connection.py`

#### Slack 알림 체계 확인 완료

현재 발송되는 Slack 알림 종류:

| 알림 | 시점 |
|------|------|
| 🇰🇷 헬스체크 요약 (VPN/DB/수집건수/디스크/CPU steal) | 매시간 정각 (cron) |
| 🇰🇷 수집 완료 (건수 + 소요시간) | 20분 수집 종료 시 |
| 🇰🇷 추적 완료 (건수 + 소요시간) | 00:00 추적 완료 시 |
| ⚠️ NordVPN / DB / 수집 0건 / 디스크 / CPU steal 이상 | 헬스체크 감지 즉시 |
| ⚠️ 로그인 실패 / S3 실패 | 발생 즉시 |
| ❌ 수집/추적 오류 (예외 전체) | 발생 즉시 |

Sentry → Slack `#트렌드보드-인스타-알림`: 신규 에러 이슈 발생 시

---

### D6.12 (3/16) — KR 서버 재시작 후 복구

- **원인**: Lightsail 서버 재시작으로 퍼블릭 IP 변경 (3.38.183.221 → 43.201.149.219)
- **영향**: 2026-03-14 13:01 ~ 2026-03-16 16:02 수집/추적 공백 (약 51시간)
- **복구**: 서비스 자동 재시작 확인 (`insta-scraper@kr.service` active), 수집 정상 재개
- **고정 IP 할당 완료**: `43.200.196.211` (Lightsail Static IP) ✅

---

### D7 (3/15~3/20) — JP / US 서버 확장 ✅ JP 완료

#### JP 서버 셋업 ✅ 완료 (2026-03-20)

- IP: `43.201.192.125` (고정)
- KR 스냅샷 기반 생성 → NordVPN Japan 연결, autoconnect 설정
- OOM + VPN 수정 완료 (2026-03-20)
- systemd `insta-scraper@jp.service` active (running)
- cron: 07:00 start / 23:00 stop / 00:00 DB 추적 / 매시간 헬스체크
- `nordvpn-autoconnect.service`에 `User=ubuntu` + `Environment=HOME=/home/ubuntu` 추가

#### US 서버 셋업 ⏳ 계정 확보 후

- `accounts.yaml` - `YOUR_US_INSTAGRAM_ACCOUNT` → 실계정 교체 필요
- NordVPN: `nordvpn connect united_states`
- 타임존: `America/New_York` (서버 및 브라우저 설정)
- JP와 동일한 절차로 셋업

---

### D8 (미정) — US 서버 셋업 ← **다음 단계**

**전제 조건**: 미국 Instagram 계정 확보

- `accounts.yaml` us 프로파일 계정 입력
- KR 스냅샷 → US 리전 인스턴스 생성
- NordVPN: `nordvpn connect united_states`
- 타임존: `America/New_York`
- JP와 동일한 절차로 셋업 (`.workflow/server-settings.md` 참조)

---

## D9 — 버스트 크레딧 자동 관리 ✅ 완료 (2026-03-31)

**배경**: 2026-03-25, 2026-03-31 KR/JP 버스트 크레딧 소진 반복 → 수동 서비스 중지 필요
**방향**: A → B → C 순서로 하나씩 작업 → 서버 테스트 → 커밋 반복

### 배경 지식

| 항목 | 내용 |
|------|------|
| 인스턴스 | Lightsail $24 (2 vCPU, 4GB RAM) |
| 베이스라인 CPU | ~40% (이 이상 사용 시 크레딧 소모) |
| 수집 중 평균 CPU | ~150% (2 vCPU 기준) → 크레딧 순소모 |
| 크레딧 직접 조회 | 불가 (Lightsail IMDSv2 제한, CloudWatch 접근 없음) |
| 크레딧 간접 측정 | **`/proc/stat` steal time** — 하이퍼바이저에 막힌 CPU 시간 = 크레딧 소진 지표 |
| 현행 사이클 | 20분 수집 / 40분 휴식, 07:00~23:00 (16h) |

**문제**: 16시간 운영 중 크레딧 회복이 소비를 못 따라잡아 장기 하향세

---

### D9-A — 운영 시간 축소 + 점심 강제 휴식 ✅ 완료 (2026-03-31)

**작업 범위**: KR/JP 서버 cron 파일만 수정 (코드 변경 없음)

```
현재: 07:00 ──────────────────────── 23:00  (16h 운영, 야간 회복 8h)
변경: 09:00 ── 13:00[2h 휴] ── 15:00 ── 21:00  (10h 운영, 야간 회복 12h)
```

변경 내용:
- 시작 07:00 → 09:00 (야간 크레딧 회복 2h 추가)
- 종료 23:00 → 21:00 (야간 크레딧 회복 2h 추가)
- 13:00 ~ 15:00 점심 강제 휴식 추가 (2h 크레딧 회복)
- 순 운영 시간: 16h → 10h (37.5% 감소)

```cron
# /etc/cron.d/insta-{국가} 변경안
0 9  * * * ubuntu sudo systemctl start insta-scraper@{국가}.service
0 13 * * * ubuntu sudo systemctl stop  insta-scraper@{국가}.service
0 15 * * * ubuntu sudo systemctl start insta-scraper@{국가}.service
0 21 * * * ubuntu sudo systemctl stop  insta-scraper@{국가}.service
```

---

### D9-B — Steal time 기반 자동 대기 ✅ 완료 (2026-03-31)

**작업 범위**: `run_safe.sh` 수정 (서버 직접 배포)

매 사이클 시작 전 steal time을 측정하고, 크레딧 소진 상태면 자동 대기 후 재도전.

```
20분 수집 종료 → systemd 40분 대기 → run_safe.sh 실행
                                           ↓
                                     steal time 측정 (2초 샘플)
                                   ┌── ≤5% → 수집 바로 시작
                                   └── >5% → 60초 대기 후 재측정 (최대 1시간)
```

- steal > 5% = 크레딧 소진 상태, 최대 1시간 대기 후 강제 시작
- `server-settings.md`의 `run_safe.sh` 참조

---

### D9-C — Chrome 렌더러 제한으로 CPU 소모 감소 ✅ 완료 (2026-03-31)

**작업 범위**: `src/browser.py` + `.env`

```python
# src/browser.py — 추가된 플래그
"--renderer-process-limit=1",            # 렌더러 프로세스 1개로 제한
"--js-flags=--max-old-space-size=512",   # V8 힙 512MB 상한
```

```env
REQUEST_DELAY=3.0   # 기존 2.0 → 3.0초
```

---

### D9 진행 결과

| 순서 | 작업 | 상태 | 비고 |
|------|------|------|------|
| D9-A | cron 운영 시간 축소 | ✅ 완료 | KR/JP 서버 cron 업데이트 완료 |
| D9-B | run_safe.sh steal 체크 | ✅ 완료 | KR/JP run_safe.sh 업데이트 완료 |
| D9-C | Chrome 렌더러 제한 | ✅ 완료 | browser.py + config.py 수정, 서버 배포 완료 |

### 현황 (2026-03-31)

- KR/JP 서버 모두 D9-A/B/C 적용 완료 + git pull 배포 완료
- 2026-03-31 하루 수집 중단: 버스트 크레딧 풀 회복 목적으로 cron start 라인 주석 처리
- **재개 시**: 각 서버 cron 파일 start 라인 주석 해제 필요

---

## 전체 변경 파일 요약


| 파일                           | 변경 내용                                      | 상태      |
| ---------------------------- | ------------------------------------------ | ------- |
| `.env`                       | 고객사 DB 연결, 운영 설정 적용                        | ✅ 완료    |
| `accounts.yaml`              | us 프로파일 추가 (계정 입력 필요)                      | ✅ 완료    |
| `src/database/models.py`     | `__tablename__` 5개 → `instagram_*`         | ✅ 완료    |
| `src/config.py`              | S3 설정 필드 추가                                | ✅ 완료    |
| `src/thumbnail_archiver.py`  | **신규** S3 아카이빙 모듈                          | ✅ 완료    |
| `src/scraper.py`             | `save_to_json()` 내 `batch_archive()` 통합, title 추출 버그 수정 | ✅ 완료    |
| `src/utils/logger.py`        | rotation="1 day", retention="30 days", zip | ✅ 완료    |
| `src/database/connection.py` | `pool_pre_ping=True` 확인                    | ✅ 완료    |
| `pyproject.toml`             | boto3, pillow 추가                           | ✅ 완료    |
| `src/config.py`              | log_rotation/log_retention 필드 추가           | ✅ 완료      |
| `src/utils/logger.py`        | rotation/retention 환경변수 연동, 기본값 50MB/10개 | ✅ 완료      |
| `main.py` / `src/main.py` / `track_views.py` | setup_logger에 rotation/retention 전달 | ✅ 완료 |
| `scripts/server_setup.sh`    | cron `/dev/null` 변경, logrotate 설정 추가       | ✅ 완료      |
| `src/utils/notifier.py`      | **신규** Slack 알림 모듈 (국가 구별 이모지)             | ✅ 완료    |
| `scripts/health_check.py`    | **신규** 헬스체크 (NordVPN, DB, 수집건수, 디스크)       | ✅ 완료    |
| `scripts/insta-scraper@.service` | **신규** systemd 수집 서비스 (24/7 자동 재시작)     | ✅ KR 완료 |
| `crontab` (각 서버)             | 추적 12:00+00:00 + 헬스체크 매시간 + 파일정리 주1회  | ✅ KR 완료 |
| `src/database/models.py`     | `instagram_reels`에 `collected_at` 컬럼 추가   | ✅ 완료    |
| `src/utils/sentry.py`        | **신규** Sentry 에러 트래킹 헬퍼 (무료 플랜, traces 비활성화) | ✅ 완료 |
| `src/config.py`              | `sentry_dsn`, `scrape_run_minutes` 필드 추가   | ✅ 완료    |
| `src/scraper.py`             | `scrape_run_minutes` 기반 실행 시간 제한 (burst credit 회복) | ✅ 완료 |
| `src/browser.py`             | `--disable-gpu`, `--disable-webgl` 등 GPU 부하 감소 플래그 추가 | ✅ 완료 |
| systemd `RestartSec`         | 60초 → 2400초 (40분 휴식 사이클)                  | ✅ KR 적용 |
| `src/views_tracker.py`      | `track_from_db()`, `_block_images_for_tracking()`, 배치 휴식 | ✅ 완료 |
| `track_views.py`            | `--from-db`, `--days` 플래그 추가                | ✅ 완료    |
| `src/config.py`             | `track_batch_size`, `track_batch_sleep` 추가     | ✅ 완료    |
| cron (KR 서버)              | 07:00 수집 start / 23:00 stop / 00:00 DB 추적   | ✅ KR 적용 |
| `src/database/repositories/reel_repository.py` | `collected_at` KST 시각 저장 수정 | ✅ 완료 |
| `src/utils/notifier.py`     | Slack DNS 실패 재시도 (3회, 5s)                   | ✅ 완료    |
| `src/thumbnail_archiver.py` | 이미지 CDN DNS 실패 재시도 (3회, 3s)               | ✅ 완료    |
| `scripts/health_check.py`   | CPU steal 모니터링 + 매시간 Slack 요약             | ✅ 완료    |


---

## 고객사 DB 테이블 구조 (납품 스펙)

```sql
-- 고객사에 전달할 테이블 명세

instagram_reels
  id            BIGINT PK
  reel_id       VARCHAR(255) UNIQUE  -- Instagram 릴스 shortcode
  link          TEXT                 -- https://www.instagram.com/reel/xxx/
  thumbnail_url TEXT                 -- S3 URL (webp) or CDN URL
  author        VARCHAR(255)         -- 크리에이터 username
  creator_profile_image TEXT         -- S3 URL or CDN URL
  title         TEXT                 -- 릴스 캡션
  music         TEXT                 -- 배경음악
  country_code  VARCHAR(10)          -- 'kr', 'jp', 'us' (수집 국가)
  created_at    TIMESTAMP
  updated_at    TIMESTAMP

instagram_reel_metrics              -- 시계열 지표 (좋아요/조회수/댓글 추적)
  id            BIGINT PK
  reel_id       BIGINT FK → instagram_reels.id
  likes         INTEGER
  comments      INTEGER
  views         INTEGER
  recorded_at   TIMESTAMP           -- 측정 시각

instagram_creators
  id            BIGINT PK
  username      VARCHAR(255) UNIQUE
  profile_image_url TEXT
  first_seen_at TIMESTAMP
  last_seen_at  TIMESTAMP

-- 정렬 예시 (고객사 UI용 쿼리)
SELECT r.*, m.views, m.likes, m.comments
FROM instagram_reels r
JOIN LATERAL (
  SELECT * FROM instagram_reel_metrics
  WHERE reel_id = r.id ORDER BY recorded_at DESC LIMIT 1
) m ON true
WHERE r.country_code = 'kr'
ORDER BY m.views DESC   -- 또는 m.likes DESC, m.comments DESC
LIMIT 50;
```

---

## 남은 TODO 목록


| 항목                            | 담당      | 상태    |
| ----------------------------- | ------- | ----- |
| 미국 Instagram 계정 확보            | 담당자     | ⏳ 대기 |
| 고객사 S3 버킷 생성 + IAM 키 발급       | 고객사 AWS | ✅ 완료 |
| NordVPN 계정 공유 (서버용)           | 담당자     | ✅ 완료 |
| 고객사 DB 기존 데이터 확인 (테이블명 충돌 여부) | 담당자     | ✅ 완료 |
| 고객사 DB 테이블 구조 명세서 전달          | 담당자     | ⏳ 대기 |
| **KR Lightsail 고정 IP 할당**     | 담당자     | ✅ 완료 (43.200.196.211) |
| **JP 서버 셋업**                  | 담당자     | ✅ 완료 (43.201.192.125, 2026-03-20) |
| US 서버 셋업                      | 담당자     | ⏳ 계정 확보 후 |


---

## 리스크 및 대응


| 리스크                   | 확률  | 대응                                        |
| --------------------- | --- | ----------------------------------------- |
| NordVPN IP 인스타 차단     | 중   | Residential 프록시(Smartproxy $5/5GB)로 전환 준비 |
| Linux 헤드리스 stealth 실패 | 중   | D3에서 `--no-sandbox` 등 플래그 검증 필수           |
| 미국 계정 확보 지연           | 중   | KR/JP 먼저 투입 후 US 추가 (독립 서버이므로 분리 가능)      |
| 기존 DB 테이블명 충돌         | 저   | `instagram_` 접두사로 기존 테이블과 분리됨             |
| Instagram 로그인 세션 만료   | 저   | SessionManager 구현됨, 자동 재로그인 동작 확인         |
| S3 업로드 실패             | 저   | 원본 CDN URL fallback (수집 중단 없음)            |
| **디스크 용량 초과 (로그 폭발)** | **중** | **logrotate + rotation="50 MB" + health_check 디스크 모니터링 (D4.5)** |
| **버스트 크레딧 지속 하향** | **중** | **D9 완료 (운영시간 축소 + steal 자동대기 + Chrome 제한) — 모니터링 중** |


