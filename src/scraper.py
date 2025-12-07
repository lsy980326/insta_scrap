"""
인스타그램 릴스 스크래퍼
엔터프라이즈급 안정성과 타입 안전성을 갖춘 스크래퍼
"""

import json
import time
from pathlib import Path
from typing import Optional

from .browser import BrowserManager
from .config import ScrapingConfig
from .exceptions import (
    DataExtractionError,
    InstagramScraperError,
    LoginError,
    RateLimitError,
    ScrapingError,
)
from .models import ReelData
from .utils.human_behavior import random_delay, simulate_page_interaction
from .utils.logger import get_logger
from .utils.wait_utils import safe_fill_input, wait_for_element, wait_for_page_load


class InstagramReelsScraper:
    """
    인스타그램 릴스를 스크래핑하는 클래스

    수집 정보:
    - 썸네일
    - 좋아요 수
    - 댓글 수
    - 작성자 이름
    - 배경음악 정보
    - 링크
    """

    def __init__(
        self,
        config: Optional[ScrapingConfig] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """
        초기화

        Args:
            config: 스크래핑 설정 객체
            username: 인스타그램 사용자명 (선택, config보다 우선)
            password: 인스타그램 비밀번호 (선택, config보다 우선)
        """
        self.config = config or ScrapingConfig()
        self.username = username or self.config.instagram_username
        self.password = password or self.config.instagram_password
        self.browser_manager: Optional[BrowserManager] = None
        self.logger = get_logger(self.__class__.__name__)

        # 출력 디렉토리 생성
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("InstagramReelsScraper 초기화 완료")

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        인스타그램에 로그인

        Args:
            username: 인스타그램 사용자명 (None이면 기존 값 사용)
            password: 인스타그램 비밀번호 (None이면 기존 값 사용)

        Returns:
            로그인 성공 여부

        Raises:
            LoginError: 로그인 실패 시
        """
        username = username or self.username
        password = password or self.password

        if not username or not password:
            raise LoginError("사용자명과 비밀번호가 필요합니다.")

        try:
            self.logger.info(f"로그인 시도: {username}")

            # 브라우저 시작 (아직 시작되지 않은 경우)
            if self.browser_manager is None:
                self.browser_manager = BrowserManager(self.config)
                self.browser_manager.start()

            page = self.browser_manager.get_page()

            # 인스타그램 메인 페이지로 이동
            self.logger.info("인스타그램 메인 페이지로 이동 중...")
            page.goto("https://www.instagram.com/", wait_until="networkidle")

            # 페이지가 완전히 로드될 때까지 대기 (유틸리티 함수 사용)
            wait_for_page_load(page, timeout=30000)
            random_delay(1.0, 2.0)  # 사용자처럼 랜덤 대기

            # 페이지 상호작용 시뮬레이션 (봇 감지 우회)
            simulate_page_interaction(page, min_actions=1, max_actions=2)

            # 로그인 링크 클릭 또는 로그인 폼 확인
            self.logger.info("로그인 폼 확인 중...")
            try:
                # 이미 로그인되어 있는지 확인
                if "accounts/login" not in page.url:
                    # 로그인 링크 찾기
                    login_link_selectors = [
                        'a[href*="/accounts/login"]',
                        'a:has-text("Log in")',
                        'a:has-text("로그인")',
                    ]

                    login_link = None
                    for selector in login_link_selectors:
                        try:
                            login_link = page.locator(selector).first
                            if login_link.is_visible(timeout=3000):
                                self.logger.info(f"로그인 링크 찾음: {selector}")
                                login_link.click()
                                page.wait_for_load_state("networkidle")
                                page.wait_for_timeout(2000)
                                break
                        except Exception:
                            continue

                # 로그인 폼이 나타날 때까지 대기
                page.wait_for_selector("#loginForm", timeout=10000, state="visible")
                self.logger.info("로그인 폼 로드 완료")
            except Exception as e:
                self.logger.warning(f"loginForm 셀렉터 대기 실패, 계속 진행: {e}")

            # 추가 안정화 대기
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1000)

            # 쿠키 수락 (있는 경우)
            try:
                accept_cookies = page.locator('button:has-text("Accept")').or_(
                    page.locator('button:has-text("수락")')
                )
                if accept_cookies.count() > 0:
                    accept_cookies.first.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass  # 쿠키 버튼이 없을 수 있음

            # 디버깅: 페이지 HTML 저장 및 스크린샷 저장
            self.logger.info("=" * 60)
            self.logger.info("로그인 페이지 로드 완료")
            self.logger.info("=" * 60)
            self.logger.info("현재 페이지 URL: " + page.url)

            # 페이지 HTML 저장 (디버깅용)
            html_content = page.content()
            debug_dir = self.config.output_dir / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)

            html_file = debug_dir / "login_page.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            self.logger.info(f"페이지 HTML 저장: {html_file}")

            # 스크린샷 저장
            screenshot_file = debug_dir / "login_page.png"
            page.screenshot(path=str(screenshot_file), full_page=True)
            self.logger.info(f"스크린샷 저장: {screenshot_file}")

            self.logger.info("입력 필드와 로그인 버튼을 찾는 중...")

            # 사용자명 입력 필드 찾기 및 입력
            # 제공된 셀렉터: #loginForm > div... > div:nth-child(1) > div > label > input
            username_selectors = [
                "#loginForm > div > div:nth-child(1) > div > label > input",  # 제공된 셀렉터 (간소화)
                '#loginForm input[type="text"]',  # 더 간단한 대안
                'input[name="username"]',
                'input[aria-label*="전화번호"]',
                'input[aria-label*="사용자 이름"]',
            ]

            # 유틸리티 함수로 요소 찾기
            username_input = wait_for_element(
                page, username_selectors, timeout=5000, description="사용자명 입력 필드"
            )

            if not username_input:
                raise LoginError("사용자명 입력 필드를 찾을 수 없습니다.")

            # 안전하게 입력 (유틸리티 함수 사용)
            if not safe_fill_input(username_input, username, description="사용자명"):
                raise LoginError("사용자명 입력에 실패했습니다.")

            # 비밀번호 입력 필드 찾기 및 입력
            # 제공된 셀렉터: #loginForm > div... > div:nth-child(2) > div > label > input
            password_selectors = [
                "#loginForm > div > div:nth-child(2) > div > label > input",  # 제공된 셀렉터 (간소화)
                '#loginForm input[type="password"]',  # 더 간단한 대안
                'input[name="password"]',
                'input[type="password"]',
            ]

            # 유틸리티 함수로 요소 찾기
            password_input = wait_for_element(
                page, password_selectors, timeout=5000, description="비밀번호 입력 필드"
            )

            if not password_input:
                raise LoginError("비밀번호 입력 필드를 찾을 수 없습니다.")

            # 안전하게 입력 (유틸리티 함수 사용)
            if not safe_fill_input(password_input, password, description="비밀번호"):
                raise LoginError("비밀번호 입력에 실패했습니다.")

            # 로그인 버튼 찾기 및 클릭
            # 제공된 셀렉터: #loginForm > div... > div:nth-child(3)
            login_button_selectors = [
                "#loginForm > div > div:nth-child(3)",  # 제공된 셀렉터 (간소화)
                "#loginForm > div > div:nth-child(3) button",  # 버튼이 내부에 있는 경우
                '#loginForm button[type="submit"]',
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("로그인")',
            ]

            # 유틸리티 함수로 요소 찾기
            login_button = wait_for_element(
                page, login_button_selectors, timeout=5000, description="로그인 버튼"
            )

            if not login_button:
                raise LoginError("로그인 버튼을 찾을 수 없습니다.")

            # 버튼이 활성화될 때까지 대기
            self.logger.info("로그인 버튼 활성화 대기 중...")
            try:
                login_button.wait_for(state="attached", timeout=3000)
                page.wait_for_timeout(500)  # 추가 안정화 대기
            except Exception:
                pass  # 대기 실패해도 계속 진행

            # 로그인 버튼 클릭
            self.logger.info("로그인 버튼 클릭 중...")
            # 클릭 가능한지 확인 후 클릭
            try:
                if login_button.is_enabled():
                    login_button.click()
                    self.logger.info("로그인 버튼 클릭 완료")
                else:
                    # 버튼이 비활성화되어 있으면 내부 버튼 찾기 시도
                    inner_button = login_button.locator("button").first
                    if inner_button.is_visible():
                        inner_button.click()
                        self.logger.info("내부 버튼 클릭 완료")
                    else:
                        # 강제 클릭 시도
                        login_button.click(force=True)
                        self.logger.info("강제 클릭 완료")
            except Exception as e:
                self.logger.warning(f"일반 클릭 실패, 강제 클릭 시도: {e}")
                login_button.click(force=True)
                self.logger.info("강제 클릭 완료")

            page.wait_for_timeout(1000)  # 클릭 후 잠시 대기

            # 로그인 완료 대기 (리다이렉트 또는 에러 메시지 확인)
            page.wait_for_timeout(3000)

            # 로그인 성공 확인 (홈페이지로 리다이렉트되었는지 확인)
            current_url = page.url
            if "accounts/login" in current_url:
                # 에러 메시지 확인
                error_selectors = [
                    'div[role="alert"]',
                    'p:has-text("Sorry")',
                    'p:has-text("죄송합니다")',
                    'div:has-text("incorrect")',
                    'div:has-text("잘못")',
                ]

                error_found = False
                for selector in error_selectors:
                    try:
                        error_element = page.locator(selector).first
                        if error_element.is_visible():
                            error_text = error_element.text_content()
                            self.logger.error(f"로그인 오류: {error_text}")
                            error_found = True
                            break
                    except Exception:
                        continue

                if error_found:
                    raise LoginError("로그인에 실패했습니다. 사용자명 또는 비밀번호를 확인하세요.")

                # 추가 대기 후 다시 확인
                page.wait_for_timeout(2000)
                if "accounts/login" in page.url:
                    raise LoginError("로그인에 실패했습니다. 페이지가 리다이렉트되지 않았습니다.")

            # 로그인 성공 확인 및 추가 처리
            self.logger.info("로그인 성공 확인 중...")

            # 리다이렉트 대기
            try:
                # URL이 변경될 때까지 대기 (최대 10초)
                page.wait_for_url("**/instagram.com/**", timeout=10000)
                page.wait_for_load_state("networkidle")
            except Exception:
                pass  # URL 변경이 없어도 계속 진행

            current_url = page.url
            self.logger.info(f"현재 URL: {current_url}")

            # 추가 인증 단계 확인 (2FA, 보안 확인 등)
            try:
                # "Not Now" 버튼 클릭 (정보 저장 안 함)
                not_now_selectors = [
                    'button:has-text("Not Now")',
                    'button:has-text("나중에 하기")',
                    'button:has-text("Not now")',
                ]

                for selector in not_now_selectors:
                    try:
                        not_now_button = page.locator(selector).first
                        if not_now_button.is_visible(timeout=3000):
                            self.logger.info("추가 확인 단계 건너뛰기")
                            not_now_button.click()
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue

                # 알림 설정 건너뛰기
                turn_on_notifications = page.locator('button:has-text("Turn on")').or_(
                    page.locator('button:has-text("켜기")')
                )
                if turn_on_notifications.count() > 0:
                    not_now_button = page.locator('button:has-text("Not Now")').or_(
                        page.locator('button:has-text("나중에 하기")')
                    )
                    if not_now_button.count() > 0:
                        not_now_button.first.click()
                        page.wait_for_timeout(2000)
            except Exception as e:
                self.logger.debug(f"추가 인증 단계 처리 중 오류 (무시): {e}")

            # 최종 페이지 로드 확인
            page.wait_for_load_state("networkidle")
            random_delay(1.0, 2.0)  # 사용자처럼 랜덤 대기

            # 로그인 후 페이지 상호작용 시뮬레이션
            simulate_page_interaction(page, min_actions=1, max_actions=2)

            # 홈페이지로 이동 확인
            if "accounts/login" not in current_url:
                self.logger.info("로그인 성공! 홈페이지로 이동 완료")
            else:
                self.logger.warning("로그인 페이지에 여전히 있습니다. 추가 확인이 필요할 수 있습니다.")

            self.username = username
            self.password = password
            self.logger.info("로그인 프로세스 완료")
            return True
        except Exception as e:
            self.logger.error(f"로그인 실패: {e}")
            raise LoginError(f"로그인에 실패했습니다: {e}") from e

    def scrape_reels(
        self,
        hashtag: Optional[str] = None,
        url: Optional[str] = None,
        max_reels: Optional[int] = None,
    ) -> list[ReelData]:
        """
        릴스 스크래핑

        Args:
            hashtag: 해시태그 (선택, config보다 우선)
            url: 특정 릴스 URL (선택, config보다 우선)
            max_reels: 최대 수집 개수 (선택, config보다 우선)

        Returns:
            릴스 정보 리스트

        Raises:
            ScrapingError: 스크래핑 실패 시
            RateLimitError: 요청 제한 초과 시
        """
        hashtag = hashtag or self.config.hashtag
        url = url or self.config.target_url
        max_reels = max_reels or self.config.max_reels

        if not hashtag and not url:
            raise ScrapingError("해시태그 또는 URL이 필요합니다.")

        try:
            self.logger.info(f"스크래핑 시작 - 해시태그: {hashtag}, URL: {url}")

            # 브라우저 시작 (아직 시작되지 않은 경우)
            if self.browser_manager is None:
                self.browser_manager = BrowserManager(self.config)
                self.browser_manager.start()

            page = self.browser_manager.get_page()
            reels: list[ReelData] = []

            if url:
                # 특정 URL로 스크래핑
                page.goto(url)
                page.wait_for_load_state("networkidle")
                # TODO: 단일 릴스 데이터 추출
            elif hashtag:
                # 해시태그로 검색
                search_url = f"https://www.instagram.com/explore/tags/{hashtag.replace('#', '')}/"
                page.goto(search_url)
                page.wait_for_load_state("networkidle")
                # TODO: 해시태그 검색 결과에서 릴스 추출

            # 요청 딜레이 적용
            if self.config.request_delay > 0:
                time.sleep(self.config.request_delay)

            self.logger.info(f"스크래핑 완료: {len(reels)}개 수집")
            return reels
        except RateLimitError as e:
            self.logger.error(f"요청 제한 초과: {e}")
            raise
        except Exception as e:
            self.logger.error(f"스크래핑 실패: {e}")
            raise ScrapingError(f"스크래핑에 실패했습니다: {e}") from e

    def extract_reel_data(self, reel_element: any) -> ReelData:  # noqa: ANN001
        """
        릴스 요소에서 데이터 추출

        Args:
            reel_element: 릴스 HTML 요소 또는 데이터 객체

        Returns:
            추출된 릴스 데이터

        Raises:
            DataExtractionError: 데이터 추출 실패 시
        """
        try:
            self.logger.debug("데이터 추출 시작")
            # TODO: 실제 데이터 추출 로직 구현
            # Playwright의 page.locator()를 사용하여 요소 선택
            # 예: page.locator('selector').text_content()
            data = ReelData(
                thumbnail=None,
                likes=None,
                comments=None,
                author=None,
                music=None,
                link=None,
            )
            self.logger.debug("데이터 추출 완료")
            return data
        except Exception as e:
            self.logger.error(f"데이터 추출 실패: {e}")
            raise DataExtractionError(f"데이터 추출에 실패했습니다: {e}") from e

    def save_to_json(self, data: list[ReelData], filename: Optional[str] = None) -> Path:
        """
        데이터를 JSON 파일로 저장

        Args:
            data: 저장할 데이터
            filename: 파일명 (None이면 자동 생성)

        Returns:
            저장된 파일 경로

        Raises:
            InstagramScraperError: 저장 실패 시
        """
        if filename is None:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reels_data_{timestamp}.json"

        filepath = self.config.output_dir / filename

        try:
            self.logger.info(f"데이터 저장 중: {filepath}")
            # Pydantic 모델을 dict로 변환
            data_dict = [item.model_dump(mode="json") for item in data]

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)

            self.logger.info(f"데이터 저장 완료: {len(data)}개 항목")
            return filepath
        except Exception as e:
            self.logger.error(f"데이터 저장 실패: {e}")
            raise InstagramScraperError(f"데이터 저장에 실패했습니다: {e}") from e

    def save_to_csv(self, data: list[ReelData], filename: Optional[str] = None) -> Path:
        """
        데이터를 CSV 파일로 저장

        Args:
            data: 저장할 데이터
            filename: 파일명 (None이면 자동 생성)

        Returns:
            저장된 파일 경로

        Raises:
            InstagramScraperError: 저장 실패 시
        """
        try:
            import pandas as pd

            if filename is None:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"reels_data_{timestamp}.csv"

            filepath = self.config.output_dir / filename

            self.logger.info(f"CSV 저장 중: {filepath}")
            # Pydantic 모델을 dict로 변환
            data_dict = [item.model_dump(mode="json") for item in data]
            df = pd.DataFrame(data_dict)
            df.to_csv(filepath, index=False, encoding="utf-8-sig")

            self.logger.info(f"CSV 저장 완료: {len(data)}개 항목")
            return filepath
        except ImportError:
            raise InstagramScraperError("CSV 저장을 위해 pandas가 필요합니다.")
        except Exception as e:
            self.logger.error(f"CSV 저장 실패: {e}")
            raise InstagramScraperError(f"CSV 저장에 실패했습니다: {e}") from e
