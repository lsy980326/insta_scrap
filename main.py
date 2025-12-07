"""
프로젝트 루트에서 실행 가능한 메인 파일

실행 방법:
1. Poetry 사용 (권장): python -m poetry run python main.py
2. 가상 환경 활성화 후: python -m poetry shell -> python main.py
3. 직접 실행 (가상 환경 필요): python main.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Poetry 가상 환경 확인 및 안내
try:
    from src.config import load_config
except ImportError as e:
    print("=" * 60)
    print("오류: 필요한 모듈을 찾을 수 없습니다.")
    print("=" * 60)
    print("\n해결 방법:")
    print("1. Poetry를 사용하여 실행하세요:")
    print("   python -m poetry run python main.py")
    print("\n2. 또는 가상 환경을 활성화한 후 실행하세요:")
    print("   python -m poetry shell")
    print("   python main.py")
    print("\n3. 또는 Poetry 가상 환경에 직접 접근:")
    print("   python -m poetry env info --path")
    print("   (출력된 경로의 Scripts\\python.exe main.py)")
    print("\n원본 오류:", str(e))
    print("=" * 60)
    sys.exit(1)

from src.config import load_config
from src.scraper import InstagramReelsScraper
from src.utils.logger import setup_logger, get_logger


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

        # 로그인 정보가 있으면 자동 로그인
        if config.instagram_username and config.instagram_password:
            logger.info("로그인 정보가 설정되어 있습니다. 로그인을 시도합니다...")
            scraper.login()
            logger.info("로그인 성공!")

        # 해시태그나 URL이 설정되어 있으면 스크래핑 시작
        if config.hashtag:
            logger.info(f"해시태그로 스크래핑 시작: {config.hashtag}")
            reels = scraper.scrape_reels(hashtag=config.hashtag, max_reels=config.max_reels)
            if reels:
                scraper.save_to_json(reels)
                logger.info(f"{len(reels)}개의 릴스를 수집했습니다.")
        elif config.target_url:
            logger.info(f"URL로 스크래핑 시작: {config.target_url}")
            reels = scraper.scrape_reels(url=config.target_url)
            if reels:
                scraper.save_to_json(reels)
                logger.info(f"{len(reels)}개의 릴스를 수집했습니다.")
        else:
            logger.info("스크래퍼가 준비되었습니다.")
            logger.info(".env 파일에서 HASHTAG 또는 TARGET_URL을 설정하세요.")

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise
    finally:
        # 브라우저 종료
        if scraper.browser_manager:
            scraper.browser_manager.close()


if __name__ == "__main__":
    main()

