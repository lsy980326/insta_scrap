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
