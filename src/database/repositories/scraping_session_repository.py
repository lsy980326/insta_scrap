"""
수집 세션 Repository
수집 세션 추적 데이터 접근 로직
"""


from sqlalchemy.orm import Session

from ...utils.logger import get_logger
from ..models import ScrapingSession

logger = get_logger(__name__)


class ScrapingSessionRepository:
    """수집 세션 데이터 접근 Repository"""

    def __init__(self, session: Session) -> None:
        """
        초기화

        Args:
            session: 데이터베이스 세션
        """
        self.session = session

    def create_session(
        self, session_type: str, status: str = "running"
    ) -> ScrapingSession:
        """
        새 수집 세션 생성

        Args:
            session_type: 세션 타입 ('collection' 또는 'tracking')
            status: 세션 상태 ('running', 'completed', 'failed')

        Returns:
            생성된 ScrapingSession 객체
        """
        session = ScrapingSession(
            session_type=session_type,
            status=status,
        )
        self.session.add(session)
        self.session.flush()
        return session

    def update_session(
        self,
        session: ScrapingSession,
        status: str | None = None,
        total_reels: int | None = None,
        error_message: str | None = None,
    ) -> ScrapingSession:
        """
        수집 세션 업데이트

        Args:
            session: 업데이트할 ScrapingSession 객체
            status: 세션 상태
            total_reels: 총 릴스 수
            error_message: 에러 메시지

        Returns:
            업데이트된 ScrapingSession 객체
        """
        if status:
            session.status = status
        if total_reels is not None:
            session.total_reels = total_reels
        if error_message:
            session.error_message = error_message

        if status in ["completed", "failed"]:
            from datetime import datetime

            session.ended_at = datetime.now()

        self.session.flush()
        return session

    def find_by_id(self, session_id: int) -> ScrapingSession | None:
        """
        ID로 세션 조회

        Args:
            session_id: 세션 ID

        Returns:
            ScrapingSession 객체, 없으면 None
        """
        return self.session.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()

