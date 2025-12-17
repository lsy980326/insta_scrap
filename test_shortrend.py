"""
숏트렌드 스크래퍼 테스트 스크립트
"""

import os
import sys

from src.config import ScrapingConfig
from src.shortrend_scraper import ShortrendScraper
from src.utils.logger import setup_logger, get_logger


def main() -> None:
    """숏트렌드 로그인 테스트"""
    # 설정 로드
    config = ScrapingConfig()

    # 로거 설정
    setup_logger(
        log_level=config.log_level,
        log_file=config.log_file,
    )

    logger = get_logger(__name__)

    logger.info("=" * 50)
    logger.info("숏트렌드 스크래퍼 테스트")
    logger.info("=" * 50)

    # 이메일과 비밀번호 가져오기 (.env에서 자동 로드, 없으면 직접 입력)
    email = config.shortrend_email
    password = config.shortrend_password

    # .env에 없으면 직접 입력받기
    if not email:
        try:
            email = input("이메일을 입력하세요: ").strip()
        except (EOFError, KeyboardInterrupt):
            logger.error("이메일 입력이 필요합니다. .env 파일에 SHORTREND_EMAIL을 설정하거나 직접 입력해주세요.")
            sys.exit(1)

    if not password:
        try:
            password = input("비밀번호를 입력하세요: ").strip()
        except (EOFError, KeyboardInterrupt):
            logger.error("비밀번호 입력이 필요합니다. .env 파일에 SHORTREND_PASSWORD를 설정하거나 직접 입력해주세요.")
            sys.exit(1)

    if not email or not password:
        logger.error("이메일과 비밀번호를 입력해주세요.")
        return

    try:
        # 스크래퍼 인스턴스 생성
        scraper = ShortrendScraper(
            config=config,
            email=email,
            password=password,
        )

        # 로그인 실행
        logger.info("로그인 시도 중...")
        success = scraper.login()

        if success:
            logger.info("✅ 로그인 성공!")
            logger.info("필터 설정 완료 (날짜: 오늘, 새 영상만 보기: 활성화)")
            logger.info("=" * 50)
            
            # 릴스 수집 시작
            try:
                logger.info("릴스 수집을 시작합니다...")
                reels = scraper.collect_reels(max_count=100)
                
                if reels:
                    logger.info(f"✅ {len(reels)}개의 릴스 수집 완료!")
                    
                    # 데이터 저장
                    filepath = scraper.save_to_json(reels)
                    logger.info(f"데이터가 저장되었습니다: {filepath}")
                else:
                    logger.warning("수집된 릴스가 없습니다.")
                    
            except KeyboardInterrupt:
                logger.info("사용자에 의해 수집이 중단되었습니다.")
            except Exception as e:
                logger.error(f"릴스 수집 중 오류: {e}")
            
            logger.info("=" * 50)
            logger.info("브라우저가 열려있습니다.")
            logger.info("브라우저를 확인한 후, 이 스크립트를 종료하면 브라우저가 닫힙니다.")
            logger.info("=" * 50)
            
            # 브라우저를 열어둔 상태로 유지
            try:
                scraper.keep_browser_open()
            except KeyboardInterrupt:
                logger.info("사용자에 의해 중단되었습니다.")
        else:
            logger.warning("⚠️ 로그인 실패 또는 확인 필요")

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise
    finally:
        # 브라우저 종료 (사용자가 Ctrl+C로 종료한 경우)
        try:
            logger.info("브라우저를 종료합니다...")
            scraper.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

