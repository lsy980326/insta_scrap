"""
계정 세션 Repository
인스타그램 계정 세션 데이터 접근 로직
"""

from datetime import datetime

from sqlalchemy.orm import Session

from ...utils.logger import get_logger
from ..models import AccountSession

logger = get_logger(__name__)


class AccountSessionRepository:
    """계정 세션 데이터 접근 Repository"""

    def __init__(self, session: Session) -> None:
        """
        초기화

        Args:
            session: 데이터베이스 세션
        """
        self.session = session

    def find_by_account_id(self, account_id: str) -> AccountSession | None:
        """
        계정 ID로 세션 조회

        Args:
            account_id: Instagram username

        Returns:
            AccountSession 객체, 없으면 None
        """
        return (
            self.session.query(AccountSession)
            .filter(AccountSession.account_id == account_id)
            .first()
        )

    def create_or_update(
        self, account_id: str, cookies: list, user_agent: str, is_valid: bool = True
    ) -> AccountSession:
        """
        세션 생성 또는 업데이트

        Args:
            account_id: Instagram username
            cookies: Playwright 쿠키 리스트
            user_agent: User-Agent 문자열
            is_valid: 세션 유효성 플래그

        Returns:
            생성 또는 업데이트된 AccountSession 객체
        """
        existing = self.find_by_account_id(account_id)

        if existing:
            # 업데이트
            existing.cookies = cookies
            existing.user_agent = user_agent
            existing.is_valid = is_valid
            existing.last_verified_at = datetime.now()
            self.session.flush()
            logger.info(f"계정 세션 업데이트: {account_id}")
            return existing
        else:
            # 생성
            new_session = AccountSession(
                account_id=account_id,
                cookies=cookies,
                user_agent=user_agent,
                is_valid=is_valid,
                last_verified_at=datetime.now() if is_valid else None,
            )
            self.session.add(new_session)
            self.session.flush()
            logger.info(f"계정 세션 생성: {account_id}")
            return new_session

    def mark_invalid(self, account_id: str) -> None:
        """
        세션을 무효로 표시

        Args:
            account_id: Instagram username
        """
        session = self.find_by_account_id(account_id)
        if session:
            session.is_valid = False
            self.session.flush()
            logger.info(f"계정 세션 무효화: {account_id}")

    def delete(self, account_id: str) -> None:
        """
        세션 삭제

        Args:
            account_id: Instagram username
        """
        session = self.find_by_account_id(account_id)
        if session:
            self.session.delete(session)
            self.session.flush()
            logger.info(f"계정 세션 삭제: {account_id}")

