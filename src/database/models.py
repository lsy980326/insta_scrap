"""
데이터베이스 ORM 모델
SQLAlchemy를 사용한 테이블 모델 정의
"""


from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Creator(Base):
    """크리에이터 정보 테이블"""

    __tablename__ = "creators"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    profile_image_url = Column(Text, nullable=True)
    first_seen_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False)
    last_seen_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False)
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False)
    updated_at = Column(TIMESTAMP, default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    # 관계
    reels = relationship(
        "Reel",
        back_populates="creator_obj",
        primaryjoin="foreign(Reel.author) == Creator.username",
        viewonly=True,  # 읽기 전용 (실제 FK 제약이 없으므로)
    )

    def __repr__(self) -> str:
        return f"<Creator(username='{self.username}')>"


class Reel(Base):
    """릴스 기본 정보 테이블"""

    __tablename__ = "reels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reel_id = Column(String(255), unique=True, nullable=False, index=True)  # Instagram 릴스 ID
    link = Column(Text, nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    author = Column(String(255), nullable=True, index=True)  # 크리에이터 사용자명
    creator_profile_image = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    music = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False)
    updated_at = Column(TIMESTAMP, default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    # 외래키 관계 (선택적)
    # author는 creators.username과 연결되지만, 외래키 제약은 선택적
    creator_obj = relationship(
        "Creator",
        primaryjoin="Reel.author == foreign(Creator.username)",
        viewonly=True,  # 읽기 전용 (실제 FK 제약이 없으므로)
    )

    # 관계
    metrics = relationship("ReelMetric", back_populates="reel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Reel(reel_id='{self.reel_id}', author='{self.author}')>"


class ReelMetric(Base):
    """릴스 통계 정보 테이블 (시계열 추적)"""

    __tablename__ = "reel_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reel_id = Column(BigInteger, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False, index=True)
    likes = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
    views = Column(Integer, nullable=True)
    recorded_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False, index=True)

    # 관계
    reel = relationship("Reel", back_populates="metrics")

    def __repr__(self) -> str:
        return f"<ReelMetric(reel_id={self.reel_id}, views={self.views}, recorded_at='{self.recorded_at}')>"


class ScrapingSession(Base):
    """수집 세션 추적 테이블"""

    __tablename__ = "scraping_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_type = Column(String(50), nullable=False, index=True)  # 'collection' 또는 'tracking'
    started_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False)
    ended_at = Column(TIMESTAMP, nullable=True)
    total_reels = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="running", nullable=False, index=True)  # 'running', 'completed', 'failed'
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False)

    def __repr__(self) -> str:
        return f"<ScrapingSession(type='{self.session_type}', status='{self.status}')>"


class AccountSession(Base):
    """인스타그램 계정 세션 정보 테이블 (쿠키 및 User-Agent 저장)"""

    __tablename__ = "account_sessions"

    account_id = Column(String(255), primary_key=True, nullable=False, index=True)  # Instagram username
    cookies = Column(JSON, nullable=False)  # Playwright 쿠키 형식
    user_agent = Column(Text, nullable=False)  # User-Agent 문자열
    is_valid = Column(Boolean, default=True, nullable=False, index=True)
    last_verified_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), nullable=False)
    updated_at = Column(TIMESTAMP, default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    def __repr__(self) -> str:
        return f"<AccountSession(account_id='{self.account_id}', is_valid={self.is_valid})>"

