"""
계정 프로파일 로더
accounts.yaml에서 프로파일을 읽어 ScrapingConfig를 오버라이드한다.
"""

from pathlib import Path

import yaml

from .config import ScrapingConfig
from .utils.logger import get_logger

logger = get_logger(__name__)

ACCOUNTS_FILE = Path("accounts.yaml")


def load_profile(profile_name: str) -> ScrapingConfig:
    """
    accounts.yaml에서 지정한 프로파일을 읽어 ScrapingConfig를 반환한다.
    .env가 기본값이고, 프로파일 값이 덮어쓴다.

    Args:
        profile_name: 프로파일 이름 (예: "kr", "jp")

    Returns:
        프로파일이 적용된 ScrapingConfig
    """
    if not ACCOUNTS_FILE.exists():
        raise FileNotFoundError(
            f"accounts.yaml 파일을 찾을 수 없습니다: {ACCOUNTS_FILE.resolve()}"
        )

    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    profiles = data.get("profiles", {})
    if profile_name not in profiles:
        available = list(profiles.keys())
        raise ValueError(
            f"프로파일 '{profile_name}'이 없습니다. "
            f"사용 가능한 프로파일: {available}"
        )

    profile = profiles[profile_name]
    logger.info(f"프로파일 로드: {profile_name}")

    # .env 기본값 로드 후 프로파일로 오버라이드
    base_config = ScrapingConfig()
    overrides = _build_overrides(profile)

    return base_config.model_copy(update=overrides)


def _build_overrides(profile: dict) -> dict:
    """yaml 프로파일 딕셔너리를 ScrapingConfig 필드명으로 변환"""
    mapping = {
        "instagram_username": "instagram_username",
        "instagram_password": "instagram_password",
        "hashtag":            "hashtag",
        "output_dir":         "output_dir",
        "request_delay":      "request_delay",
        "locale":             "browser_locale",
        "timezone":           "browser_timezone",
        "proxy":              "proxy_server",
    }

    # model_copy는 타입 변환을 하지 않으므로 Path 필드는 직접 변환
    path_fields = {"output_dir"}

    overrides: dict = {}
    for yaml_key, config_key in mapping.items():
        value = profile.get(yaml_key)
        # 빈 문자열은 스킵 (proxy 등 선택 항목)
        if value == "" or value is None:
            continue
        if config_key in path_fields:
            value = Path(value)
        overrides[config_key] = value

    return overrides


def list_profiles() -> list[str]:
    """accounts.yaml에 있는 프로파일 이름 목록 반환"""
    if not ACCOUNTS_FILE.exists():
        return []
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return list(data.get("profiles", {}).keys())
