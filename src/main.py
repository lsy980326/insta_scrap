"""
메인 실행 파일
"""

from .config import load_config
from .scraper import InstagramReelsScraper
from .utils.logger import get_logger, setup_logger


def main() -> None:
    """
    메인 함수
    """
    # 설정 로드
    config = load_config()

    # 로거 설정
    setup_logger(
        log_level=config.log_level,
        log_file=config.log_file,
    )

    logger = get_logger(__name__)

    logger.info("=" * 50)
    logger.info("Instagram Reels Scraper")
    logger.info("=" * 50)

    try:
        # 스크래퍼 인스턴스 생성
        scraper = InstagramReelsScraper(config=config)

        # TODO: 로그인 정보 및 태그 정보는 나중에 전달 예정
        # scraper.login()
        # reels = scraper.scrape_reels(hashtag="#your_hashtag")
        # scraper.save_to_json(reels)

        logger.info("스크래퍼가 준비되었습니다.")
        logger.info("로그인 정보와 태그 정보를 전달받으면 구현을 진행하겠습니다.")

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()
