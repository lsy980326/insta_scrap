# 국가별 일일 랭킹 DB/웹 계획

인스타그램 릴스를 국가별로 수집하고 있고, 웹(`web/`)에서 **국가별 일일 랭킹**을 보여주기 위한 DB 구조 변경 및 연동 계획입니다.

---

## 1. 현재 상태 정리

| 구분 | 내용 |
|------|------|
| 수집 | `--profile kr` / `--profile jp` 로 국가(프로파일)별 실행, `accounts.yaml`에 프로파일 정의 |
| DB | `reels`, `reel_metrics`, `creators`, `scraping_sessions`, `account_sessions` — **국가 정보 없음** |
| 저장 | `_save_to_db(ReelData 리스트)` 만 호출, 프로파일(국가) 미전달 |
| 웹 API | `GET /api/reels/ranking` — `sortBy`, `limit`, `offset`, `startDate`, `endDate` 만 지원, **국가 필터 없음** |

**정책**: 사용한 **계정(프로파일)**에 따라 국가를 고정한다. `--profile kr`로 수집한 릴스는 KR, `--profile jp`로 수집한 릴스는 JP로만 분류하면 되므로, 별도 매핑 테이블 없이 **`reels`에 `country_code` 컬럼 하나**만 추가하면 됩니다.

---

## 2. DB 구조 변경 계획

### 2.1 방향: `reels`에 `country_code` 컬럼 추가

- **`reels` 테이블**: 컬럼 추가  
  - **`country_code`** (VARCHAR(10), nullable, index) — 예: `kr`, `jp` (수집 시 사용한 프로파일 이름).
- **`reel_metrics`**: 변경 없음.

규칙:

- **신규 저장**: 해당 수집에 사용한 프로파일(계정)의 국가 코드를 `country_code`에 저장.
- **기존 릴스 업데이트**(같은 reel_id로 메트릭만 추가): `country_code`는 **덮어쓰지 않음** (최초 수집 계정 기준 고정).

---

## 3. 백엔드(스크래퍼/설정/DB) 변경 계획

### 3.1 설정에 국가(프로파일) 반영

- **`ScrapingConfig`** (`src/config.py`)에 선택 필드 추가  
  - 예: `country_code: str | None = None`  
  - `load_profile("jp")` 호출 시 이 값에 프로파일 이름(`jp`) 설정.
- **`load_profile()`** (`src/profile_loader.py`)에서  
  - `accounts.yaml`의 프로파일 이름(예: `kr`, `jp`)을 읽어  
  - `ScrapingConfig`의 `country_code`에 설정.

### 3.2 DB 모델 및 Repository

- **`src/database/models.py`**
  - `Reel` 모델에 **`country_code`** 컬럼 추가 (String(10), nullable, index).
- **마이그레이션**
  - `ALTER TABLE reels ADD COLUMN country_code VARCHAR(10);`  
  - `CREATE INDEX ix_reels_country_code ON reels(country_code);` (선택)

### 3.3 저장 로직 (스크래퍼 ↔ DB)

- **`ReelRepository.create_or_update_reel(reel_data, country_code: str | None = None)`**
  - **신규 생성** 시: `country_code` 인자가 있으면 `reel.country_code = country_code` 설정.
  - **기존 릴스 업데이트** 시: `country_code`는 수정하지 않음 (기존 값 유지).
- **`InstagramReelsScraper._save_to_db()`**
  - `self.config.country_code`를 `create_or_update_reel(..., country_code=self.config.country_code)` 로 전달.

### 3.4 기존 데이터 보강 (선택)

- 이미 DB에 있는 reels는 `country_code`가 NULL.  
  - 과거 수집은 “국가 미구분”으로 두거나,  
  - `output_dir` 등으로 추정 가능하면 일괄 업데이트 스크립트로 보강 가능.

---

## 4. 웹 API 변경 계획

### 4.1 랭킹 API: 국가·일자 지원

- **`GET /api/reels/ranking`**
  - 기존: `sortBy`, `limit`, `offset`, `startDate`, `endDate`
  - 추가:
    - **`country`** (선택): 국가 코드 (예: `kr`, `jp`). 없으면 기존처럼 전체.
    - **일일 랭킹**: `startDate` = `endDate` = 같은 날짜면 해당 일자 스냅샷으로 랭킹.

쿼리 개요:

- `country` 파라미터 있으면 `WHERE r.country_code = $country` 조건 추가.
- `reel_metrics`는 기존처럼 LATERAL JOIN으로 최신 메트릭 또는, 일자 지정 시 해당 일자의 메트릭 사용.
- 정렬: `views` / `likes` 등 기존과 동일.

### 4.2 국가 목록 API (선택)

- **`GET /api/countries`**  
  - `SELECT DISTINCT country_code FROM reels WHERE country_code IS NOT NULL ORDER BY country_code`  
  - 또는 프론트에서 고정 목록 (`["kr", "jp"]` 등) 사용.

---

## 5. 웹 UI 변경 계획

- **국가 선택**: 메인 랭킹 페이지에 국가 드롭다운 (전체 / KR / JP) → `?country=kr` 등으로 전달.
- **일일 랭킹**: 날짜 선택 후 `startDate` = `endDate` = 해당 날짜로 요청해 그날 랭킹 표시.
- 기존 “일주일 단위 그룹화”는 유지하거나 일별 모드와 전환 가능하게.

---

## 6. 작업 순서 제안

| 순서 | 작업 | 비고 |
|------|------|------|
| 1 | `reels` 테이블에 `country_code` 컬럼 추가 (마이그레이션/SQL) | nullable, index |
| 2 | `ScrapingConfig`에 `country_code` 추가, `load_profile()`에서 설정 | |
| 3 | `Reel` ORM 모델에 `country_code` 추가, `create_or_update_reel()`에서 신규 시에만 설정 | |
| 4 | `_save_to_db()`에서 config의 `country_code`를 repository에 전달 | |
| 5 | `GET /api/reels/ranking`에 `country` 파라미터 및 일자별 메트릭 로직 반영 | |
| 6 | `GET /api/countries` 추가 또는 프론트 상수 | |
| 7 | 웹 UI: 국가 선택 + 일자 선택 후 일일 랭킹 표시 | |
| 8 | (선택) 기존 reels의 `country_code` 보강 스크립트 | |

---

## 7. 정리

- **DB**: `reels`에 **`country_code`** 컬럼만 추가. 계정(프로파일) 기준으로 고정.
- **수집**: 프로파일 이름을 config의 `country_code`로 넘기고, **신규 저장 시에만** `reels.country_code`에 기록. 업데이트 시에는 기존 값 유지.
- **웹**: 랭킹 API에 `country` + 날짜 범위(일일 = startDate=endDate) 반영하고, UI에서 국가·일자 선택 후 국가별 일일 랭킹 표시.

이 순서대로 적용하면 계정 기준으로 국가가 고정된 국가별 일일 랭킹을 도입할 수 있습니다.
