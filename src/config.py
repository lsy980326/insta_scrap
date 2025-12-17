"""
설정 관리 모듈
Pydantic을 사용한 타입 안전한 설정 관리
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScrapingConfig(BaseSettings):
    """스크래핑 설정"""

    # 인스타그램 로그인 정보
    instagram_username: Optional[str] = Field(default=None, description="인스타그램 사용자명")
    instagram_password: Optional[str] = Field(default=None, description="인스타그램 비밀번호")

    # 숏트렌드 로그인 정보
    shortrend_email: Optional[str] = Field(default=None, description="숏트렌드 이메일")
    shortrend_password: Optional[str] = Field(default=None, description="숏트렌드 비밀번호")

    # 스크래핑 설정
    hashtag: Optional[str] = Field(default=None, description="해시태그 (예: #fitness)")
    target_url: Optional[str] = Field(default=None, description="특정 릴스 URL")

    # 출력 설정
    output_dir: Path = Field(default=Path("output"), description="출력 디렉토리")
    output_format: str = Field(default="json", description="출력 형식 (json, csv)")

    # Playwright 설정
    playwright_headless: bool = Field(default=True, description="헤드리스 모드")
    playwright_timeout: int = Field(default=30000, ge=1000, le=120000, description="타임아웃 (밀리초)")
    playwright_browser: str = Field(
        default="chromium", description="브라우저 (chromium, firefox, webkit)"
    )
    playwright_storage_state: Optional[Path] = Field(
        default=None, description="브라우저 상태 저장 경로 (쿠키/세션 유지)"
    )

    # 프록시 설정
    proxy_server: Optional[str] = Field(
        default=None, description="프록시 서버 (예: http://proxy.example.com:8080)"
    )
    proxy_username: Optional[str] = Field(default=None, description="프록시 사용자명")
    proxy_password: Optional[str] = Field(default=None, description="프록시 비밀번호")

    # 스크래핑 제한
    max_reels: Optional[int] = Field(default=None, ge=1, description="최대 수집 개수")
    request_delay: float = Field(default=2.0, ge=0.0, description="요청 간 딜레이 (초)")

    @field_validator("max_reels", mode="before")
    @classmethod
    def validate_max_reels(cls, v: any) -> Optional[int]:  # noqa: ANN001
        """max_reels 빈 문자열 처리"""
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v

    # 로깅 설정
    log_level: str = Field(default="INFO", description="로깅 레벨")
    log_file: Optional[Path] = Field(default=None, description="로그 파일 경로")

    @field_validator("log_file", mode="before")
    @classmethod
    def validate_log_file(cls, v: any) -> Optional[Path]:  # noqa: ANN001
        """log_file 빈 문자열 처리"""
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            return Path(v)
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """출력 형식 검증"""
        if v.lower() not in ["json", "csv"]:
            raise ValueError("output_format은 'json' 또는 'csv'여야 합니다.")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """로깅 레벨 검증"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level은 {valid_levels} 중 하나여야 합니다.")
        return v.upper()


def load_config() -> ScrapingConfig:
    """설정 로드"""
    return ScrapingConfig()
