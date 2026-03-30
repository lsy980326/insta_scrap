# 워크플로우 체크리스트

이 문서는 프로젝트 작업 진행 상황을 추적하는 체크리스트입니다.

## 현재 사이클

### 사이클 시작일: 2026-03-12
### 사이클 완료일: (진행 중)

### 작업 내용 — D3~D6 KR 서버 풀 셋업

- ✅ **로그 용량 관리 (D4.5)**: log_rotation/log_retention 환경변수 연동, 기본값 50MB/10개, server_setup.sh logrotate 적용
- ✅ **KR Lightsail 서버 셋업 (D3)**: server_setup.sh 실행 완료 (3.38.183.221)
- ✅ **KR E2E 검증**: 수집 10건↑, DB 저장(reels 20건, metrics 48건), 추적 정상
- ✅ **DB 초기화**: instagram_* 테이블 TRUNCATE
- ✅ **title 추출 버그 수정**: span:not(.xlyipyv) 선택자 + root 스코프 변경
- ✅ **Slack 알림 + 헬스체크 (D5)**: notifier.py, health_check.py, 국가 이모지 구별
- ✅ **수집 24/7 systemd 서비스**: insta-scraper@kr.service active (running)
- ✅ **추적 스케줄 변경**: 06:00 1회 → 12:00 + 00:00 2회
- ✅ **KR 운영 검증 (D6)**: 서버 장애 대응 완료 (중복 프로세스 제거 + flock 재발 방지)
- ✅ **Sentry 에러 트래킹 (D6.7)**: sentry-sdk 통합, 무료 플랜 (traces 비활성화)
- ✅ **collected_at 컬럼**: instagram_reels 수집 시각 컬럼 추가 + DB 마이그레이션
- ✅ **GPU 플래그 최적화 (D6.7)**: --disable-gpu, --disable-webgl 등 SwiftShader 부하 감소
- ✅ **Burst credit 회복 사이클 (D6.7)**: SCRAPE_RUN_MINUTES=20 + RestartSec=2400 (20분 수집/40분 휴식)
- ✅ **CPU Steal 모니터링 (D6.9)**: health_check.py check_cpu_steal(), notifier send_cpu_steal_warning()
- ✅ **collected_at KST 오류 수정 (D6.10)**: naive datetime으로 KST 시각 그대로 저장
- ✅ **Slack DNS 재시도 (D6.10)**: notifier._post() 3회 재시도, 5초 간격
- ✅ **썸네일 CDN DNS 재시도 (D6.10)**: thumbnail_archiver._download_and_convert() 3회 재시도, 3초 간격
- ✅ **KR Cron 정리 (D6.10)**: 잔존 JSON 추적 cron 제거, 시간대 분리 cron 확정
- ✅ **Sentry v2 API 수정 (D6.11)**: Hub.current.client → get_client().dsn, push_scope → new_scope
- ✅ **헬스체크 수집건수 오류 수정 (D6.11)**: created_at → collected_at(KST) 기준
- ✅ **헬스체크 import/contextmanager 버그 수정 (D6.11)**: get_db_session + @contextmanager
- ✅ **Slack 알림 전체 정상 동작 확인 (D6.11)**

### 진행 단계

- [x] 1단계: 로그 용량 관리 구현
- [x] 2단계: KR 서버 셋업 + 검증
- [x] 3단계: DB 초기화
- [x] 4단계: title 추출 버그 수정
- [x] 5단계: Slack 알림 + 헬스체크 + systemd 서비스
- [x] 6단계: KR 운영 검증 + 장애 대응 완료
- [x] 7단계: Sentry + GPU 최적화 + burst credit 회복 사이클
- [x] 8단계: 추적 모듈 DB 기반 전환 (track_from_db, --from-db, 이미지 차단, 배치 휴식, 시간대 분리 cron)
- [x] 9단계: KR 운영 안정화 완료 (collected_at KST, Slack/CDN DNS 재시도, Cron 정리, CPU Steal 모니터링)
- [ ] 10단계: JP 서버 셋업

- ✅ **KR 서버 재시작 복구 (D6.12)**: IP 변경(3.38.183.221 → 43.201.149.219), 수집 서비스 자동 재개 확인

### 완료 상태
진행 중 — KR 재가동 확인, JP 서버 셋업 대기 / KR 고정 IP 할당 필요

---

## 이전 사이클

### 사이클 시작일: 2026-03-11
### 사이클 완료일: 2026-03-12

### 작업 내용 — 운영 전환 준비 (D1~D2 완료)
- ✅ **DB 테이블명 변경**: `__tablename__` 5개 → `instagram_*` (고객사 요구사항)
- ✅ **S3 설정 추가**: config.py에 s3_enabled, s3_bucket, aws_* 필드
- ✅ **ThumbnailArchiver**: src/thumbnail_archiver.py 신규 (CDN → webp → S3, fallback 포함)
- ✅ **scraper.py 통합**: save_to_json()에서 batch_archive() 호출 (S3_ENABLED=false 시 건너뜀)
- ✅ **logger.py**: rotation="1 day", retention="30 days", compression="zip"
- ✅ **connection.py**: pool_pre_ping=True 확인
- ✅ **pyproject.toml**: boto3, pillow 추가

### 완료 상태
완료

---

## 이전 사이클 기록

### 2026-02-23 사이클
- 계정별 프로파일 (accounts.yaml), 브라우저 로케일, 로그인 셀렉터, 중복 감지, 루트 main.py --profile
- ✅ 완료

---

## 이전 사이클 기록

### 2026-01-07 사이클
- 추적 모듈 세션 쿠키 사용 기능 추가 (SessionManager 통합)
- 스크롤 횟수 증가, 통계 추출 개선, DB 저장 개선, 성능 최적화
- ✅ 완료

### 2026-01-02 사이클
- 데이터베이스 통합 및 로그인 리다이렉트 문제 해결
- 웹 서비스 구축
- 수집 모듈 복구 (홈 탭 클릭 기능 추가)
- 로그인 검증 로직 강화 (리다이렉트 감지 및 에러 처리)
- ✅ 완료

---

## 이전 사이클 기록

### 2026-01-01 사이클
- 조회수 추적 모듈 구현
- ✅ 완료

### 2025-12-17 사이클
- 숏트렌드 스크래퍼 구현
- ✅ 완료

### 2025-12-07 사이클
- 프로젝트 초기 설정
- ✅ 완료

---

## 작업 체크리스트 템플릿

### 새 사이클 시작 시

1. [ ] 작업 내용 정의
2. [ ] 관련 문서 확인
3. [ ] 구현 계획 수립

### 작업 중

1. [ ] 기능 구현
2. [ ] 테스트 작성/실행
3. [ ] 코드 리뷰
4. [ ] 문서 업데이트

### 완료 전

1. [ ] 린터 오류 확인
2. [ ] 타입 체크
3. [ ] 테스트 통과 확인
4. [ ] 문서 최신화 확인
5. [ ] PR 가이드 체크리스트 확인

---

## 참고

- 작업 완료 시 이 문서에 기록을 남기세요
- 각 사이클의 시작일과 완료일을 기록하세요
- 주요 변경 사항을 간단히 요약하세요

