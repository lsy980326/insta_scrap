"""
메인 실행 파일
"""

import argparse

from .config import load_config
from .profile_loader import list_profiles, load_profile
from .scraper import InstagramReelsScraper
from .utils.logger import get_logger, setup_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Instagram Reels Scraper")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="accounts.yaml에서 사용할 프로파일 이름 (예: kr, jp). "
             "없으면 .env 기본값 사용.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="사용 가능한 프로파일 목록 출력 후 종료",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 프로파일 목록 출력 후 종료
    if args.list_profiles:
        profiles = list_profiles()
        print("사용 가능한 프로파일:")
        for p in profiles:
            print(f"  - {p}")
        return

    # 설정 로드: --profile 지정 시 accounts.yaml 우선, 없으면 .env
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

    logger.info("=" * 50)
    logger.info("Instagram Reels Scraper")
    logger.info("=" * 50)

    if args.profile:
        logger.info(f"프로파일: {args.profile} "
                    f"(locale={config.browser_locale}, tz={config.browser_timezone})")
    logger.info(f"계정: {config.instagram_username}")

    try:
        scraper = InstagramReelsScraper(config=config)

        if config.instagram_username and config.instagram_password:
            logger.info("로그인 정보가 설정되어 있습니다. 로그인을 시도합니다...")
            scraper.login()
        else:
            logger.warning("로그인 정보가 없습니다. .env 또는 accounts.yaml을 확인하세요.")

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()
