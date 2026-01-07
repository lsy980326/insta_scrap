"""
크리에이터 Repository
크리에이터 데이터 접근 로직
"""

from typing import Optional

from sqlalchemy.orm import Session

from ..models import Creator

from ...utils.logger import get_logger

logger = get_logger(__name__)


class CreatorRepository:
    """크리에이터 데이터 접근 Repository"""

    def __init__(self, session: Session) -> None:
        """
        초기화

        Args:
            session: 데이터베이스 세션
        """
        self.session = session

    def find_by_username(self, username: str) -> Optional[Creator]:
        """
        사용자명으로 크리에이터 조회

        Args:
            username: 인스타그램 사용자명

        Returns:
            Creator 객체, 없으면 None
        """
        return self.session.query(Creator).filter(Creator.username == username).first()

    def create_or_update_creator(
        self, username: str, profile_image_url: Optional[str] = None
    ) -> tuple[Creator, bool]:
        """
        크리에이터 생성 또는 업데이트

        Args:
            username: 인스타그램 사용자명
            profile_image_url: 프로필 이미지 URL

        Returns:
            (Creator 객체, is_new: bool) 튜플
        """
        existing_creator = self.find_by_username(username)

        if existing_creator:
            # 기존 크리에이터 업데이트
            logger.debug(f"기존 크리에이터 업데이트: {username}")
            if profile_image_url:
                existing_creator.profile_image_url = profile_image_url
            # last_seen_at은 트리거로 자동 업데이트됨
            self.session.flush()
            return existing_creator, False
        else:
            # 새 크리에이터 생성
            logger.debug(f"새 크리에이터 생성: {username}")
            new_creator = Creator(
                username=username,
                profile_image_url=profile_image_url,
            )
            self.session.add(new_creator)
            self.session.flush()
            return new_creator, True

