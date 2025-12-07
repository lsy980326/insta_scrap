"""
스크래퍼 테스트
"""

import pytest

from src.config import ScrapingConfig
from src.exceptions import LoginError, ScrapingError
from src.scraper import InstagramReelsScraper


@pytest.fixture
def config():
    """테스트용 설정"""
    return ScrapingConfig(
        instagram_username="test_user",
        instagram_password="test_pass",
        output_dir="test_output",
    )


@pytest.fixture
def scraper(config):
    """테스트용 스크래퍼 인스턴스"""
    return InstagramReelsScraper(config=config)


class TestInstagramReelsScraper:
    """InstagramReelsScraper 테스트 클래스"""

    def test_init(self, scraper):
        """초기화 테스트"""
        assert scraper.config is not None
        assert scraper.username == "test_user"
        assert scraper.password == "test_pass"

    def test_login_without_credentials(self, scraper):
        """자격증명 없이 로그인 시도"""
        scraper.username = None
        scraper.password = None
        with pytest.raises(LoginError):
            scraper.login()

    def test_scrape_reels_without_params(self, scraper):
        """파라미터 없이 스크래핑 시도"""
        with pytest.raises(ScrapingError):
            scraper.scrape_reels()

    @pytest.mark.slow
    def test_scrape_reels_with_hashtag(self, scraper):
        """해시태그로 스크래핑 테스트"""
        # 실제 구현 후 활성화
        pass
