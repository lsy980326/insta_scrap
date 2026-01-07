"""
데이터베이스 연결 관리 모듈
SQLAlchemy를 사용한 PostgreSQL 연결 관리
"""

from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import ScrapingConfig
from ..utils.logger import get_logger
from .models import Base

logger = get_logger(__name__)

# 전역 변수
_engine: Optional[object] = None
_SessionLocal: Optional[sessionmaker] = None


def get_database_url(config: ScrapingConfig) -> Optional[str]:
    """
    데이터베이스 URL 생성

    Args:
        config: 스크래핑 설정 객체

    Returns:
        데이터베이스 URL, 설정이 없으면 None
    """
    if not config.db_enabled:
        return None

    if not all([config.db_host, config.db_name, config.db_user, config.db_password]):
        logger.warning("데이터베이스 설정이 불완전합니다. DB 기능이 비활성화됩니다.")
        return None

    return (
        f"postgresql://{config.db_user}:{config.db_password}"
        f"@{config.db_host}:{config.db_port}/{config.db_name}"
    )


def init_db(config: ScrapingConfig) -> bool:
    """
    데이터베이스 연결 초기화

    Args:
        config: 스크래핑 설정 객체

    Returns:
        초기화 성공 여부
    """
    global _engine, _SessionLocal

    database_url = get_database_url(config)
    if not database_url:
        logger.info("데이터베이스가 비활성화되어 있습니다.")
        return False

    try:
        # SQLAlchemy 엔진 생성
        _engine = create_engine(
            database_url,
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow,
            pool_pre_ping=True,  # 연결 유효성 검사
            echo=False,  # SQL 쿼리 로깅 (디버깅 시 True)
        )

        # 세션 팩토리 생성
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        # 연결 테스트
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # 모든 테이블 자동 생성 (없으면 생성, 있으면 스킵)
        Base.metadata.create_all(bind=_engine)
        logger.info("데이터베이스 테이블 확인/생성 완료")

        logger.info("데이터베이스 연결 초기화 완료")
        return True

    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {e}")
        _engine = None
        _SessionLocal = None
        return False


def get_db_session() -> Generator[Session, None, None]:
    """
    데이터베이스 세션 생성 (의존성 주입용)

    Yields:
        데이터베이스 세션

    Raises:
        RuntimeError: 데이터베이스가 초기화되지 않은 경우
    """
    if _SessionLocal is None:
        raise RuntimeError("데이터베이스가 초기화되지 않았습니다. init_db()를 먼저 호출하세요.")

    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session_direct() -> Session:
    """
    데이터베이스 세션 직접 생성 (컨텍스트 매니저 없이 사용)

    Returns:
        데이터베이스 세션

    Raises:
        RuntimeError: 데이터베이스가 초기화되지 않은 경우
    """
    if _SessionLocal is None:
        raise RuntimeError("데이터베이스가 초기화되지 않았습니다. init_db()를 먼저 호출하세요.")

    return _SessionLocal()

