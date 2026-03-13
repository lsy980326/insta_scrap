"""
설정 관리 모듈
Pydantic을 사용한 타입 안전한 설정 관리
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScrapingConfig(BaseSettings):
    """스크래핑 설정"""

    # 인스타그램 로그인 정보
    instagram_username: str | None = Field(default=None, description="인스타그램 사용자명")
    instagram_password: str | None = Field(default=None, description="인스타그램 비밀번호")

    # 숏트렌드 로그인 정보
    shortrend_email: str | None = Field(default=None, description="숏트렌드 이메일")
    shortrend_password: str | None = Field(default=None, description="숏트렌드 비밀번호")

    # 국가/프로파일 (수집 계정 기준, DB reels.country_code 저장용)
    country_code: str | None = Field(default=None, description="국가 코드 (예: kr, jp) — 프로파일 이름과 동일")

    # 스크래핑 설정
    hashtag: str | None = Field(default=None, description="해시태그 (예: #fitness)")
    target_url: str | None = Field(default=None, description="특정 릴스 URL")

    # 출력 설정
    output_dir: Path = Field(default=Path("output"), description="출력 디렉토리")
    output_format: str = Field(default="json", description="출력 형식 (json, csv)")

    # Playwright 설정
    playwright_headless: bool = Field(default=True, description="헤드리스 모드")
    playwright_timeout: int = Field(default=30000, ge=1000, le=120000, description="타임아웃 (밀리초)")
    playwright_browser: str = Field(
        default="chromium", description="브라우저 (chromium, firefox, webkit)"
    )
    playwright_storage_state: Path | None = Field(
        default=None, description="브라우저 상태 저장 경로 (쿠키/세션 유지)"
    )
    browser_locale: str = Field(default="ko-KR", description="브라우저 로케일 (예: ja-JP, en-US)")
    browser_timezone: str = Field(default="Asia/Seoul", description="브라우저 타임존 (예: Asia/Tokyo)")

    # 프록시 설정
    proxy_server: str | None = Field(
        default=None, description="프록시 서버 (예: http://proxy.example.com:8080)"
    )
    proxy_username: str | None = Field(default=None, description="프록시 사용자명")
    proxy_password: str | None = Field(default=None, description="프록시 비밀번호")

    # 스크래핑 제한
    max_reels: int | None = Field(default=None, ge=1, description="최대 수집 개수")
    scrape_run_minutes: int | None = Field(
        default=None, ge=1, description="수집 최대 실행 시간 (분). systemd RestartSec와 조합해 burst credit 회복"
    )
    request_delay: float = Field(default=2.0, ge=0.0, description="요청 간 딜레이 (초)")

    @field_validator("max_reels", "scrape_run_minutes", mode="before")
    @classmethod
    def validate_nullable_int(cls, v: any) -> int | None:  # noqa: ANN001
        """int | None 필드 빈 문자열 처리"""
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
    log_file: Path | None = Field(default=None, description="로그 파일 경로")
    log_rotation: str = Field(default="50 MB", description="로그 rotation 기준 (예: '50 MB', '1 day')")
    log_retention: int | str = Field(default=10, description="보관 파일 수 또는 기간 (예: 10, '30 days')")

    # 데이터베이스 설정
    db_enabled: bool = Field(default=False, description="데이터베이스 사용 여부")
    db_host: str | None = Field(default=None, description="데이터베이스 호스트")
    db_port: int = Field(default=5432, description="데이터베이스 포트")
    db_name: str | None = Field(default=None, description="데이터베이스 이름")
    db_user: str | None = Field(default=None, description="데이터베이스 사용자명")
    db_password: str | None = Field(default=None, description="데이터베이스 비밀번호")
    db_pool_size: int = Field(default=5, ge=1, description="데이터베이스 연결 풀 크기")
    db_max_overflow: int = Field(default=10, ge=0, description="데이터베이스 최대 오버플로우")

    # 알림 설정
    slack_webhook_url: str | None = Field(default=None, description="Slack Incoming Webhook URL")
    sentry_dsn: str | None = Field(default=None, description="Sentry DSN (없으면 Sentry 비활성화)")

    # S3 썸네일 아카이빙 설정
    s3_enabled: bool = Field(default=False, description="S3 썸네일 저장 사용 여부")
    s3_bucket: str | None = Field(default=None, description="S3 버킷명")
    aws_region: str = Field(default="ap-northeast-2", description="AWS 리전")
    aws_access_key_id: str | None = Field(default=None, description="AWS Access Key ID")
    aws_secret_access_key: str | None = Field(default=None, description="AWS Secret Access Key")

    # 세션 관리 설정
    session_storage_type: str = Field(
        default="db", description="세션 저장 타입 ('db' 또는 'file')"
    )
    session_file_dir: Path = Field(
        default=Path("sessions"), description="세션 파일 저장 디렉토리 (file 타입일 때)"
    )

    @field_validator("log_retention", mode="before")
    @classmethod
    def validate_log_retention(cls, v: any) -> int | str:  # noqa: ANN001
        """log_retention: 숫자 문자열은 int로, 빈 값은 기본값으로"""
        if v == "" or v is None:
            return 10
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return 10
            try:
                return int(v)
            except ValueError:
                return v  # "30 days" 같은 기간 문자열
        return v

    @field_validator("log_file", mode="before")
    @classmethod
    def validate_log_file(cls, v: any) -> Path | None:  # noqa: ANN001
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

    @field_validator("session_storage_type")
    @classmethod
    def validate_session_storage_type(cls, v: str) -> str:
        """세션 저장 타입 검증"""
        if v.lower() not in ["db", "file"]:
            raise ValueError("session_storage_type은 'db' 또는 'file'이어야 합니다.")
        return v.lower()

    @field_validator("session_file_dir", mode="before")
    @classmethod
    def validate_session_file_dir(cls, v: any) -> Path:  # noqa: ANN001
        """session_file_dir 빈 문자열 처리"""
        if v == "" or v is None:
            return Path("sessions")
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return Path("sessions")
            return Path(v)
        return v


def load_config() -> ScrapingConfig:
    """설정 로드"""
    return ScrapingConfig()
