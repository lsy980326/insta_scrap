"""
커스텀 예외 클래스
"""


class InstagramScraperError(Exception):
    """기본 스크래퍼 예외"""

    pass


class LoginError(InstagramScraperError):
    """로그인 실패 예외"""

    pass


class ScrapingError(InstagramScraperError):
    """스크래핑 실패 예외"""

    pass


class DataExtractionError(InstagramScraperError):
    """데이터 추출 실패 예외"""

    pass


class ConfigurationError(InstagramScraperError):
    """설정 오류 예외"""

    pass


class RateLimitError(InstagramScraperError):
    """요청 제한 초과 예외"""

    pass
