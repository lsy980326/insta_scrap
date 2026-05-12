"""
프로젝트 루트에서 실행 가능한 메인 파일

실행 방법:
  poetry run python main.py                # .env 기본값 사용
  poetry run python main.py --profile kr   # 한국 계정 (accounts.yaml)
  poetry run python main.py --profile jp   # 일본 계정 (accounts.yaml)
  poetry run python main.py --list-profiles
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.config import load_config
    from src.profile_loader import list_profiles, load_profile
    from src.scraper import InstagramReelsScraper
    from src.utils.logger import get_logger, setup_logger
    from src.utils.notifier import get_notifier
    from src.utils.sentry import capture_exception, init_sentry
except ImportError as e:
    print("=" * 60)
    print("오류: 필요한 모듈을 찾을 수 없습니다.")
    print("해결: poetry run python main.py")
    print("원본 오류:", str(e))
    print("=" * 60)
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Instagram Reels Scraper")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="accounts.yaml 프로파일 이름 (예: kr, jp). 없으면 .env 기본값 사용.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="사용 가능한 프로파일 목록 출력 후 종료",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 프로파일 목록 출력
    if args.list_profiles:
        profiles = list_profiles()
        print("사용 가능한 프로파일:")
        for p in profiles:
            print(f"  - {p}")
        return

    # 설정 로드: --profile 있으면 accounts.yaml, 없으면 .env
    if args.profile:
        config = load_profile(args.profile)
    else:
        config = load_config()

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

    logger.info("=" * 50)
    logger.info("Instagram Reels Scraper")
    logger.info("=" * 50)

    if args.profile:
        logger.info(f"프로파일: {args.profile} "
                    f"(locale={config.browser_locale}, tz={config.browser_timezone})")
    logger.info(f"계정: {config.instagram_username}")

    import time
    start_time = time.time()

    scraper = None
    try:
        # 스크래퍼 인스턴스 생성
        scraper = InstagramReelsScraper(config=config)

        # 로그인 정보가 있으면 자동 로그인 및 릴스 탭 이동
        if config.instagram_username and config.instagram_password:
            logger.info("로그인 정보가 설정되어 있습니다. 로그인을 시도합니다...")

            # 지수 백오프 재시도 (5분 → 15분 → 30분)
            _retry_waits = [300, 900, 1800]
            for _attempt in range(len(_retry_waits) + 1):
                try:
                    scraper.login()
                    break
                except Exception as e:
                    capture_exception(e, event=f"login_failed_attempt_{_attempt + 1}")
                    if _attempt < len(_retry_waits):
                        _wait = _retry_waits[_attempt]
                        logger.warning(
                            f"로그인 실패 ({_attempt + 1}/{len(_retry_waits) + 1}) — "
                            f"{_wait // 60}분 후 재시도: {e}"
                        )
                        time.sleep(_wait)
                    else:
                        logger.error(f"로그인 {len(_retry_waits) + 1}회 모두 실패: {e}")
                        if notifier:
                            notifier.send_login_error(profile, str(e))
                        raise

            logger.info("로그인 성공! 릴스 탭까지 이동 완료.")

            # 릴스 수집 시작
            logger.info("릴스 수집을 시작합니다...")
            logger.info("수집을 중단하려면 Ctrl+C를 누르세요.")
            run_minutes = getattr(config, "scrape_run_minutes", 20) or 20
            if notifier:
                notifier.send_scrape_start(profile, run_minutes)
            scraper.start_collecting_reels()

            # 수집 완료 알림
            duration = int(time.time() - start_time)
            collect_count = len(getattr(scraper, "collected_reels", []))
            if notifier:
                if collect_count == 0:
                    notifier.send_zero_collect(profile)
                else:
                    notifier.send_summary(profile, collect_count, duration)
        else:
            logger.warning("로그인 정보가 없습니다. 로그인 후 수집을 시작할 수 없습니다.")
            logger.info("프로그램이 종료되었습니다.")

    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 수집이 중단되었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        capture_exception(e, event="collection_error")
        if notifier and "login" not in str(type(e).__name__).lower():
            notifier._post(f"❌ *[{profile.upper()}] 수집 오류*\n```{str(e)[:300]}```")
        raise
    finally:
        logger.info("수집 종료. 브라우저 정리 중...")
        if scraper and scraper.browser_manager:
            try:
                scraper.browser_manager.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()

