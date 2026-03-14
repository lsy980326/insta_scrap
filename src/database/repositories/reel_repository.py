"""
릴스 Repository
릴스 데이터 접근 로직
"""

import re
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ...models import ReelData
from ...utils.logger import get_logger
from ..models import Reel, ReelMetric

logger = get_logger(__name__)


def extract_reel_id(link: str) -> str | None:
    """
    릴스 링크에서 reel_id 추출

    Args:
        link: 릴스 링크 (예: "https://www.instagram.com/reel/DS4U0UKgGt9/")

    Returns:
        reel_id (예: "DS4U0UKgGt9"), 실패 시 None
    """
    if not link:
        return None

    # /reels/ID/ 또는 /reel/ID/ 패턴 매칭
    match = re.search(r"/reels?/([^/?#]+)/?", str(link))
    if match:
        return match.group(1)
    return None


class ReelRepository:
    """릴스 데이터 접근 Repository"""

    def __init__(self, session: Session) -> None:
        """
        초기화

        Args:
            session: 데이터베이스 세션
        """
        self.session = session

    def find_by_reel_id(self, reel_id: str) -> Reel | None:
        """
        reel_id로 릴스 조회

        Args:
            reel_id: Instagram 릴스 ID

        Returns:
            Reel 객체, 없으면 None
        """
        return self.session.query(Reel).filter(Reel.reel_id == reel_id).first()

    def find_by_link(self, link: str) -> Reel | None:
        """
        링크로 릴스 조회

        Args:
            link: 릴스 링크

        Returns:
            Reel 객체, 없으면 None
        """
        reel_id = extract_reel_id(link)
        if not reel_id:
            return None
        return self.find_by_reel_id(reel_id)

    def create_or_update_reel(
        self, reel_data: ReelData, country_code: str | None = None
    ) -> tuple[Reel, bool]:
        """
        릴스 생성 또는 업데이트 (중복 체크 포함)

        Args:
            reel_data: Pydantic ReelData 객체
            country_code: 국가 코드 (예: kr, jp). 신규 생성 시에만 설정, 업데이트 시에는 기존 값 유지.

        Returns:
            (Reel 객체, is_new: bool) 튜플
        """
        if not reel_data.link:
            raise ValueError("reel_data.link가 필요합니다.")

        # reel_id 추출
        reel_id = extract_reel_id(str(reel_data.link))
        if not reel_id:
            raise ValueError(f"링크에서 reel_id를 추출할 수 없습니다: {reel_data.link}")

        # 기존 릴스 조회
        existing_reel = self.find_by_reel_id(reel_id)

        # 게시일 파싱 (posted_date가 있으면 created_at, updated_at으로 사용)
        posted_datetime = None
        if reel_data.posted_date:
            try:
                # ISO 형식 문자열을 datetime으로 변환
                if isinstance(reel_data.posted_date, str):
                    posted_datetime = datetime.fromisoformat(reel_data.posted_date.replace("Z", "+00:00"))
                elif isinstance(reel_data.posted_date, datetime):
                    posted_datetime = reel_data.posted_date
            except Exception as e:
                logger.debug(f"게시일 파싱 실패: {e}")

        if existing_reel:
            # 기존 릴스 업데이트
            logger.debug(f"기존 릴스 업데이트: {reel_id}")
            existing_reel.link = str(reel_data.link)
            if reel_data.thumbnail:
                existing_reel.thumbnail_url = reel_data.thumbnail
            if reel_data.author:
                existing_reel.author = reel_data.author
            if reel_data.creator_profile_image:
                existing_reel.creator_profile_image = reel_data.creator_profile_image
            if reel_data.title:
                existing_reel.title = reel_data.title
            if reel_data.music:
                existing_reel.music = reel_data.music
            # 게시일이 있으면 updated_at 업데이트 (created_at은 유지)
            if posted_datetime:
                existing_reel.updated_at = posted_datetime

            self.session.flush()
            return existing_reel, False
        else:
            # 새 릴스 생성
            logger.debug(f"새 릴스 생성: {reel_id}")
            # 게시일이 있으면 created_at, updated_at 모두 게시일로 설정
            new_reel = Reel(
                reel_id=reel_id,
                link=str(reel_data.link),
                thumbnail_url=reel_data.thumbnail,
                author=reel_data.author,
                creator_profile_image=reel_data.creator_profile_image,
                title=reel_data.title,
                music=reel_data.music,
                country_code=country_code,
                created_at=posted_datetime if posted_datetime else func.current_timestamp(),
                updated_at=posted_datetime if posted_datetime else func.current_timestamp(),
            )
            self.session.add(new_reel)
            self.session.flush()
            return new_reel, True

    def add_metric(
        self,
        reel: Reel,
        likes: int | None = None,
        comments: int | None = None,
        views: int | None = None,
    ) -> ReelMetric:
        """
        릴스 통계 정보 추가 (시계열 추적)

        Args:
            reel: Reel 객체
            likes: 좋아요 수
            comments: 댓글 수
            views: 조회수

        Returns:
            생성된 ReelMetric 객체
        """
        metric = ReelMetric(
            reel_id=reel.id,
            likes=likes,
            comments=comments,
            views=views,
        )
        self.session.add(metric)
        self.session.flush()
        return metric

    def find_recent_by_country(self, country_code: str, days: int = 7) -> list[Reel]:
        """
        최근 N일 이내 수집된 릴스를 국가 코드로 조회 (추적 대상 로드용)

        Args:
            country_code: 국가 코드 (예: kr, jp)
            days: 최근 며칠치 (기본 7일)

        Returns:
            Reel 리스트 (collected_at 내림차순)
        """
        from datetime import timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            self.session.query(Reel)
            .filter(Reel.country_code == country_code)
            .filter(Reel.collected_at >= cutoff)
            .order_by(Reel.collected_at.desc())
            .all()
        )

    def get_latest_metric(self, reel: Reel) -> ReelMetric | None:
        """
        릴스의 최신 통계 정보 조회

        Args:
            reel: Reel 객체

        Returns:
            최신 ReelMetric 객체, 없으면 None
        """
        return (
            self.session.query(ReelMetric)
            .filter(ReelMetric.reel_id == reel.id)
            .order_by(ReelMetric.recorded_at.desc())
            .first()
        )

