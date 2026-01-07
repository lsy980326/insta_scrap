"""
조회수 추적 모듈의 데이터베이스 업데이트 기능 테스트

사용 방법:
    python database/test_tracker.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import load_config
from src.database import init_db, get_db_session
from src.database.repositories import ReelRepository
from src.utils.logger import setup_logger, get_logger


def main():
    """메인 함수"""
    # 설정 로드
    config = load_config()

    # 로거 설정
    setup_logger(
        log_level=config.log_level,
        log_file=config.log_file,
    )

    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("조회수 추적 모듈 DB 업데이트 테스트")
    logger.info("=" * 60)

    # DB 초기화
    if not config.db_enabled:
        logger.error("데이터베이스가 비활성화되어 있습니다.")
        logger.info("DB_ENABLED=true로 설정하고 다시 시도하세요.")
        return

    if not init_db(config):
        logger.error("데이터베이스 초기화 실패")
        return

    logger.info("데이터베이스 연결 성공")

    # 테스트: 조회수 업데이트
    try:
        session = next(get_db_session())
        reel_repo = ReelRepository(session)

        # 테스트용 reel_id (실제 데이터로 변경 필요)
        test_reel_id = "TEST_REEL_123"
        
        # 릴스 찾기
        reel = reel_repo.find_by_reel_id(test_reel_id)
        
        if reel:
            logger.info(f"릴스 찾음: {reel.reel_id}")
            logger.info(f"현재 조회수: {reel_repo.get_latest_metric(reel.id).views if reel_repo.get_latest_metric(reel.id) else '없음'}")
            
            # 조회수 업데이트 테스트
            test_views = 10000
            reel_repo.add_metric(reel.id, views=test_views, likes=1000, comments=50)
            logger.info(f"조회수 업데이트 완료: {test_views}")
        else:
            logger.warning(f"릴스를 찾을 수 없습니다: {test_reel_id}")
            logger.info("실제 reel_id로 변경하여 테스트하세요.")

        session.close()
        logger.info("테스트 완료")

    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()

