"""
데이터 모델 정의
Pydantic을 사용한 타입 안전한 데이터 모델
"""

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ReelData(BaseModel):
    """릴스 데이터 모델"""

    thumbnail: Optional[str] = Field(default=None, description="영상 썸네일 URL")
    likes: Optional[int] = Field(default=None, ge=0, description="좋아요 수")
    comments: Optional[int] = Field(default=None, ge=0, description="댓글 수")
    author: Optional[str] = Field(default=None, description="크리에이터 이름")
    creator_profile_image: Optional[str] = Field(default=None, description="크리에이터 프로필 사진 URL")
    title: Optional[str] = Field(default=None, description="제목")
    music: Optional[str] = Field(default=None, description="배경음악 정보")
    link: Optional[HttpUrl] = Field(default=None, description="게시물 링크")

    @field_validator("author")
    @classmethod
    def validate_author(cls, v: Optional[str]) -> Optional[str]:
        """작성자 이름 검증"""
        if v is not None and len(v.strip()) == 0:
            return None
        return v

    class Config:
        """Pydantic 설정"""

        json_schema_extra = {
            "example": {
                "thumbnail": "https://example.com/thumbnail.jpg",
                "likes": 1234,
                "comments": 56,
                "author": "username",
                "music": "Song Name - Artist",
                "link": "https://www.instagram.com/reel/abc123/",
            }
        }


class ShortrendReelData(BaseModel):
    """숏트렌드 릴스 데이터 모델"""

    # 기본 정보
    thumbnail_url: Optional[str] = Field(default=None, description="썸네일 이미지 URL")
    video_url: Optional[str] = Field(default=None, description="비디오 URL")
    instagram_link: Optional[str] = Field(default=None, description="Instagram 게시물 링크")

    # 랭킹 정보
    rank: Optional[str] = Field(default=None, description="랭킹 (예: TOP 1)")
    rank_number: Optional[int] = Field(default=None, description="랭킹 번호")
    date: Optional[str] = Field(default=None, description="날짜 (예: 12월 14일)")
    growth_rate: Optional[str] = Field(default=None, description="증가율 (예: +999%)")

    # 통계 정보
    views: Optional[int] = Field(default=None, description="조회수")
    views_daily_change: Optional[str] = Field(default=None, description="조회수 일일 변화율")
    views_weekly_change: Optional[str] = Field(default=None, description="조회수 주간 변화율")
    likes: Optional[int] = Field(default=None, description="좋아요 수")
    likes_daily_change: Optional[str] = Field(default=None, description="좋아요 일일 변화율")
    likes_weekly_change: Optional[str] = Field(default=None, description="좋아요 주간 변화율")
    comments: Optional[int] = Field(default=None, description="댓글 수")
    comments_daily_change: Optional[str] = Field(default=None, description="댓글 일일 변화율")
    comments_weekly_change: Optional[str] = Field(default=None, description="댓글 주간 변화율")

    # 작성자 정보
    author_username: Optional[str] = Field(default=None, description="작성자 사용자명 (예: @moon_tae_hwan)")
    author_display_name: Optional[str] = Field(default=None, description="작성자 표시 이름 (예: 문태환)")
    author_followers: Optional[int] = Field(default=None, description="작성자 팔로워 수")

    # 콘텐츠 정보
    title: Optional[str] = Field(default=None, description="제목/캡션")
    duration: Optional[str] = Field(default=None, description="영상 길이 (예: 0:11)")

    # 원본 데이터 (디버깅용)
    raw_data: Optional[dict] = Field(default=None, description="원본 추출 데이터")
