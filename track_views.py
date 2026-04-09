"""
조회수 추적 실행 스크립트

사용 방법:
1. Poetry 사용 (권장):
   python -m poetry run python track_views.py [입력파일] [출력파일]

2. 가상 환경 활성화 후:
   python -m poetry shell
   python track_views.py [입력파일] [출력파일]

3. 직접 실행 (가상 환경 필요):
   python track_views.py [입력파일] [출력파일]

예시:
   python track_views.py output/reels_data_20260101_143155.json
   python track_views.py output/reels_data_20260101_143155.json output/reels_with_views.json
"""

import fcntl
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.config import load_config
    from src.profile_loader import load_profile
    from src.views_tracker import ReelViewsTracker
    from src.utils.logger import setup_logger, get_logger
    from src.utils.notifier import get_notifier
    from src.utils.sentry import capture_exception, init_sentry
except ImportError as e:
    print("=" * 60)
    print("오류: 필요한 모듈을 찾을 수 없습니다.")
    print("=" * 60)
    print("\n해결 방법:")
    print("1. Poetry를 사용하여 실행하세요:")
    print("   python -m poetry run python track_views.py [입력파일]")
    print("\n2. 또는 가상 환경을 활성화한 후 실행하세요:")
    print("   python -m poetry shell")
    print("   python track_views.py [입력파일]")
    print("\n원본 오류:", str(e))
    print("=" * 60)
    sys.exit(1)


def main() -> None:
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Instagram Reels 조회수 추적")
    parser.add_argument("input_file", nargs="?", help="입력 JSON 파일 경로 (--from-db 미사용 시)")
    parser.add_argument("output_file", nargs="?", help="출력 JSON 파일 경로 (선택)")
    parser.add_argument("--profile", "-p", help="계정 프로파일 (예: kr, jp)")
    parser.add_argument("--from-db", action="store_true", help="DB에서 추적 대상 로드 (JSON 파일 불필요)")
    parser.add_argument("--days", type=int, default=7, help="--from-db 사용 시 최근 며칠치 추적 (기본 7)")
    args = parser.parse_args()

    if not args.from_db and not args.input_file:
        parser.error("--from-db를 사용하거나 input_file을 지정하세요.")

    # 중복 실행 방지 (동일 프로파일 추적이 이미 실행 중이면 즉시 종료)
    lock_path = f"/tmp/track-views-{args.profile or 'default'}.lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print(f"이미 추적 프로세스가 실행 중입니다 ({lock_path}). 종료합니다.")
        lock_fd.close()
        sys.exit(0)

    # 설정 로드 (프로파일 우선)
    config = load_profile(args.profile) if args.profile else load_config()

    # 로거 설정
    setup_logger(
        log_level=config.log_level,
        log_file=config.log_file,
        rotation=config.log_rotation,
        retention=config.log_retention,
    )

    logger = get_logger(__name__)
    profile = args.profile or "unknown"
    notifier = get_notifier(config)
    init_sentry(config.sentry_dsn, profile=profile)

    logger.info("=" * 60)
    logger.info("Instagram Reels 조회수 추적")
    logger.info("=" * 60)
    if args.profile:
        logger.info(f"프로파일: {args.profile} (계정: {config.instagram_username})")

    import time
    start_time = time.time()

    try:
        # 트래커 생성
        tracker = ReelViewsTracker(config=config)

        try:
            if args.from_db:
                # DB 기반 추적 (--from-db)
                country_code = config.country_code or profile
                logger.info(f"DB 기반 추적 시작: {country_code}, 최근 {args.days}일")
                tracked_count = tracker.track_from_db(country_code=country_code, days=args.days)
                duration = int(time.time() - start_time)
                logger.info("=" * 60)
                logger.info(f"DB 추적 완료: {tracked_count}개 릴스 업데이트")
                logger.info("=" * 60)
                if notifier:
                    notifier.send_track_summary(profile, tracked_count, duration)

            else:
                # 기존 JSON 파일 기반 추적
                input_file = Path(args.input_file)
                output_file = Path(args.output_file) if args.output_file else None

                if not input_file.exists():
                    logger.error(f"입력 파일을 찾을 수 없습니다: {input_file}")
                    sys.exit(1)

                logger.info(f"입력 파일: {input_file}")

                # 로그인 정보가 있으면 자동 로그인
                if config.instagram_username and config.instagram_password:
                    logger.info("로그인 정보가 설정되어 있습니다. 로그인을 시도합니다...")
                    try:
                        tracker.login()
                        logger.info("로그인 성공!")
                    except Exception as e:
                        logger.warning(f"로그인 실패: {e}")
                        capture_exception(e, event="login_failed")
                        if notifier:
                            notifier.send_login_error(profile, str(e))
                        logger.warning("로그인 없이 계속 진행합니다.")
                else:
                    logger.warning("로그인 정보가 없습니다.")

                result_file = tracker.track_views(input_file, output_file)
                duration = int(time.time() - start_time)
                logger.info("=" * 60)
                logger.info(f"조회수 추적 완료!")
                logger.info(f"결과 파일: {result_file}")
                logger.info("=" * 60)
                if notifier:
                    tracked_count = getattr(tracker, "tracked_count", 0)
                    notifier.send_track_summary(profile, tracked_count, duration)

        except KeyboardInterrupt:
            logger.info("\n사용자에 의해 중단되었습니다.")
        except Exception as e:
            logger.error(f"조회수 추적 중 오류 발생: {e}")
            capture_exception(e, event="tracking_error")
            if notifier:
                notifier._post(f"❌ *[{profile.upper()}] 추적 오류*\n```{str(e)[:300]}```")
            raise
        finally:
            # 브라우저 종료
            tracker.close()

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    main()

