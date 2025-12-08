import json
import re
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page

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
from .utils.human_behavior import random_delay, random_mouse_movement, simulate_page_interaction
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
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)

            # 페이지가 완전히 로드될 때까지 대기 (DOM만 확인, networkidle은 타임아웃 위험)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                self.logger.debug("페이지 로드 대기 실패 (계속 진행)")
            
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
                                try:
                                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                                except Exception:
                                    pass
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

            # 로그인 버튼 클릭 후 20초 대기 (브라우저에 아무것도 하지 않고 대기만)
            self.logger.info("로그인 처리 대기 중... (20초, 브라우저 조작 없음)")
            time.sleep(20)  # Python의 time.sleep 사용 (브라우저 응답을 기다리지 않음)

            # 로그인 결과 확인 (간단히 URL만 확인, 브라우저 조작 최소화)
            try:
                current_url = page.url
                self.logger.info(f"현재 URL: {current_url}")

                # 로그인 페이지에 여전히 있으면 경고만 출력
                if "accounts/login" in current_url:
                    self.logger.warning(
                        "로그인 페이지에 여전히 있습니다. 로그인 실패 가능성이 있습니다."
                    )
                else:
                    self.logger.info("로그인 성공으로 보입니다 (로그인 페이지가 아님)")
            except Exception as e:
                self.logger.warning(f"URL 가져오기 실패: {e}")
                current_url = "https://www.instagram.com/"

            # 로그인 후 팝업 처리
            self._handle_post_login_popup(page)

            # 릴스 탭으로 이동
            try:
                self.logger.info("릴스 탭으로 이동 시도 중...")
                self.navigate_to_reels_tab()
                self.logger.info("릴스 탭 이동 완료")
                
                # 릴스 수집 시작
                self.logger.info("릴스 수집을 시작합니다...")
                self.start_collecting_reels()
            except KeyboardInterrupt:
                self.logger.info("사용자에 의해 중단되었습니다.")
            except Exception as e:
                self.logger.warning(f"릴스 탭 이동 또는 수집 실패: {e}")

            self.username = username
            self.password = password
            self.logger.info("로그인 프로세스 완료")
            return True
        except Exception as e:
            self.logger.error(f"로그인 실패: {e}")
            raise LoginError(f"로그인에 실패했습니다: {e}") from e

    def _handle_post_login_popup(self, page: Page) -> None:
        """
        로그인 후 팝업 처리

        팝업이 있으면 확인 버튼을 클릭하거나, 마우스 이동/키 입력으로 닫습니다.
        팝업이 없으면 그냥 진행합니다.
        일정 시간 동안 주기적으로 팝업을 모니터링하여 자동으로 감지하고 닫습니다.

        Args:
            page: Playwright Page 객체
        """
        try:
            self.logger.info("로그인 후 팝업 확인 중...")

            # 팝업 감지 및 처리 (최대 15초 동안 주기적으로 확인)
            max_check_time = 15000  # 15초
            check_interval = 500  # 0.5초마다 확인
            elapsed_time = 0
            popup_closed = False

            while elapsed_time < max_check_time:
                if self._check_and_close_popup(page):
                    popup_closed = True
                    # 팝업을 닫은 후 잠시 대기하고 한 번 더 확인
                    time.sleep(1)  # Python time.sleep 사용
                    if not self._check_and_close_popup(page):
                            break
                else:
                    # 팝업이 없으면 잠시 대기 후 종료
                    if elapsed_time > 2000:  # 최소 2초는 기다림
                        break

                time.sleep(check_interval / 1000)  # 밀리초를 초로 변환
                elapsed_time += check_interval

            if popup_closed:
                self.logger.info("팝업 자동 처리 완료")
            else:
                self.logger.info("팝업이 없거나 이미 처리되었습니다.")

            # 팝업 처리 후 추가 대기
            time.sleep(1)  # Python time.sleep 사용
            random_delay(0.5, 1.0)

        except Exception as e:
            self.logger.debug(f"팝업 처리 중 오류 (무시하고 계속 진행): {e}")

    def _check_and_close_popup(self, page: Page) -> bool:
        """
        팝업이 있는지 확인하고 있으면 닫기

        Args:
            page: Playwright Page 객체

        Returns:
            팝업을 닫았으면 True, 없으면 False
        """
        try:
            # 사용자 제공 팝업 셀렉터 및 일반적인 팝업 셀렉터들
            popup_container_selectors = [
                # 사용자 제공 셀렉터 (Instagram 팝업 컨테이너)
                'body > div.x1n2onr6.xzkaem6 > div.x9f619.x1n2onr6.x1ja2u2z > div > div.x1uvtmcs.x4k7w5x.x1h91t0o.x1beo9mf.xaigb6o.x12ejxvf.x3igimt.xarpa2k.xedcshv.x1lytzrv.x1t2pt76.x7ja8zs.x1n2onr6.x1qrby5j.x1jfb8zj > div > div > div > div > div > div > div.x1i10hfl.xjqpnuy.xc5r6h4.xqeqjp1.x1phubyo.x972fbf.x10w94by.x1qhh985.x14e42zd.xdl72j9.x2lah0s.x3ct3a4.xdj266r.x14z9mp.xat24cr.x1lziwak.x2lwn1j.xeuugli.xexx8yu.x18d9i69.x1hl2dhg.xggy1nq.x1ja2u2z.x1t137rt.x1q0g3np.x1lku1pv.x1a2a7pz.x6s0dn4.xjyslct.x1ejq31n.x18oe1m7.x1sy0etr.xstzfhl.x9f619.x9bdzbf.x1ypdohk.x1f6kntn.xwhw2v2.xl56j7k.x17ydfre.x1n2onr6.x2b8uid.xlyipyv.x87ps6o.x5c86q.x18br7mf.x1i0vuye.xh8yej3.x6nl9eh.x1a5l9x9.x7vuprf.x1mg3h75.xn3w4p2.x106a9eq.x1xnnf8n.x18cabeq.x158me93.xk4oym4.x1uugd1q.x3nfvp2',
                # Instagram 팝업의 일반적인 패턴 (클래스명의 일부 사용)
                'body > div.x1n2onr6.xzkaem6',
                'div[role="dialog"]',
                '[data-testid="modal"]',
                '.x1n2onr6[role="dialog"]',
                # 모달/다이얼로그 패턴
                'div[role="presentation"]',
                'div._a9-z',  # Instagram 알림 모달
                'div._a9--',
            ]

            # 1단계: 팝업 컨테이너 확인
            for selector in popup_container_selectors:
                try:
                    popup = page.locator(selector).first
                    if popup.is_visible(timeout=500):
                        self.logger.info(f"팝업 컨테이너 발견: {selector[:50]}...")

                        # 팝업 내부의 확인/닫기 버튼 찾기
                        popup_button_selectors = [
                            # 버튼 텍스트 기반
                            'button:has-text("확인")',
                            'button:has-text("OK")',
                            'button:has-text("Okay")',
                            'button:has-text("Got it")',
                            'button:has-text("알겠습니다")',
                            'button:has-text("다음")',
                            'button:has-text("Next")',
                            'button:has-text("Close")',
                            'button:has-text("닫기")',
                            # aria-label 기반
                            'button[aria-label*="확인"]',
                            'button[aria-label*="OK"]',
                            'button[aria-label*="Close"]',
                            'button[aria-label*="닫기"]',
                            # 일반적인 팝업 버튼
                            'div[role="dialog"] button',
                            '[data-testid="confirm"]',
                            '[data-testid="ok"]',
                            '[data-testid="close"]',
                            # X 버튼
                            'button[aria-label*="Close"]',
                            'svg[aria-label*="Close"]',
                            '[aria-label*="닫기"]',
                        ]

                        # 팝업 내부에서 버튼 찾기
                        button_found = False
                        for button_selector in popup_button_selectors:
                            try:
                                # 팝업 컨테이너 내부에서 버튼 찾기
                                button = popup.locator(button_selector).first
                                if button.is_visible(timeout=500):
                                    self.logger.info(f"팝업 확인 버튼 발견: {button_selector}")
                                    button.click()
                                    page.wait_for_timeout(500)
                                    button_found = True
                                    return True
                            except Exception:
                                pass

                        # 버튼을 찾지 못한 경우, 다른 방법으로 팝업 닫기 시도
                        if not button_found:
                            self.logger.info("팝업 버튼을 찾지 못함. 다른 방법으로 닫기 시도...")

                            # 방법 1: ESC 키
                            try:
                                page.keyboard.press("Escape")
                                page.wait_for_timeout(500)
                                # ESC 후 팝업이 사라졌는지 확인
                                if not popup.is_visible(timeout=500):
                                    self.logger.info("ESC 키로 팝업 닫기 성공")
                                    return True
                            except Exception:
                                pass

                            # 방법 2: 팝업 외부 영역 클릭 (배경 클릭)
                            try:
                                # 팝업의 위치를 확인하고 외부 영역 클릭
                                viewport = page.viewport_size
                                if viewport:
                                    # 화면 상단 좌측 모서리 클릭 (보통 팝업 외부)
                                    page.mouse.click(10, 10)
                                    page.wait_for_timeout(500)
                                    if not popup.is_visible(timeout=500):
                                        self.logger.info("외부 영역 클릭으로 팝업 닫기 성공")
                                        return True
                            except Exception:
                                pass

                            # 방법 3: 마우스 이동으로 팝업 닫기 (일부 팝업은 마우스 움직임에 반응)
                            try:
                                random_mouse_movement(page, duration=0.2)
                                page.wait_for_timeout(500)
                                if not popup.is_visible(timeout=500):
                                    self.logger.info("마우스 이동으로 팝업 닫기 성공")
                                    return True
                            except Exception:
                                pass

                            # 방법 4: Enter 키 (일부 팝업은 Enter로 닫힘)
                            try:
                                page.keyboard.press("Enter")
                                page.wait_for_timeout(500)
                                if not popup.is_visible(timeout=500):
                                    self.logger.info("Enter 키로 팝업 닫기 성공")
                                    return True
                            except Exception:
                                pass

                        break  # 팝업을 처리했거나 시도했으므로 루프 종료
                except Exception:
                        continue

            return False

        except Exception as e:
            self.logger.debug(f"팝업 확인 중 오류 (무시): {e}")
            return False

    def _wait_for_main_page_load(self, page: Page) -> None:
        """
        메인화면 로딩 완료 대기

        DOM 로딩이 완료될 때까지 대기합니다.
        networkidle은 인스타그램처럼 동적 로딩이 많은 사이트에서는 타임아웃 위험이 있어 사용하지 않습니다.

        Args:
            page: Playwright Page 객체
        """
        try:
            self.logger.info("메인화면 로딩 대기 중...")

            # DOM만 확인 (networkidle은 타임아웃 위험)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                self.logger.debug("domcontentloaded 대기 실패 (계속 진행)")

            # 추가 안정화 대기 (Python time.sleep 사용)
            time.sleep(2)
            random_delay(1.0, 2.0)

            self.logger.info("메인화면 로딩 완료")
        except Exception as e:
            self.logger.warning(f"메인화면 로딩 대기 중 오류 (계속 진행): {e}")

    def navigate_to_reels_tab(self) -> bool:
        """
        릴스 탭으로 이동

        Returns:
            이동 성공 여부

        Raises:
            ScrapingError: 이동 실패 시
        """
        try:
            if self.browser_manager is None:
                raise ScrapingError("브라우저가 시작되지 않았습니다. 먼저 로그인하세요.")

            page = self.browser_manager.get_page()
            self.logger.info("릴스 탭으로 이동 중...")

            # 릴스 탭 셀렉터 (사용자 제공 셀렉터 및 일반적인 대안)
            reels_tab_selectors = [
                # 사용자 제공 셀렉터
                '#mount_0_0_fz > div > div > div.x9f619.x1n2onr6.x1ja2u2z > div > div > div.x78zum5.xdt5ytf.x1t2pt76.x1n2onr6.x1ja2u2z.x10cihs4 > div.html-div.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x9f619.x16ye13r.xvbhtw8.x78zum5.x15mokao.x1ga7v0g.x16uus16.xbiv7yw.x1uhb9sk.x1plvlek.xryxfnj.x1c4vz4f.x2lah0s.x1q0g3np.xqjyukv.x1qjc9v5.x1oa3qoh.x1qughib > div.html-div.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x9f619.xjbqb8w.x78zum5.x15mokao.x1ga7v0g.x16uus16.xbiv7yw.xixxii4.x13vifvy.x1plvlek.xryxfnj.x1c4vz4f.x2lah0s.xdt5ytf.xqjyukv.x1qjc9v5.x1oa3qoh.x1nhvcw1.x1dr59a3.xeq5yr9.x1n327nk > div > div > div > div > div.x1iyjqo2.xh8yej3 > div:nth-child(4) > span > div > a > div',
                # 일반적인 릴스 탭 셀렉터들
                'a[href="/reels/"]',
                'a[href*="/reels"]',
                'div:has-text("릴스")',
                'div:has-text("Reels")',
                'span:has-text("릴스")',
                'span:has-text("Reels")',
                # Instagram 네비게이션 바에서 릴스 찾기
                'nav a[href*="/reels"]',
                'nav span:has-text("릴스")',
                'nav span:has-text("Reels")',
            ]

            # 유틸리티 함수로 요소 찾기
            reels_tab = wait_for_element(
                page, reels_tab_selectors, timeout=10000, description="릴스 탭"
            )

            if not reels_tab:
                raise ScrapingError("릴스 탭을 찾을 수 없습니다.")

            # 릴스 탭 클릭
            self.logger.info("릴스 탭 클릭 중...")
            reels_tab.click()
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                self.logger.debug("릴스 탭 로드 대기 실패 (계속 진행)")
            time.sleep(2)  # Python time.sleep 사용
            random_delay(1.0, 2.0)

            # 릴스 페이지 로딩 확인
            current_url = page.url
            if "/reels" in current_url:
                self.logger.info(f"릴스 탭으로 이동 완료: {current_url}")
                return True
            else:
                self.logger.warning(f"릴스 탭 이동 후 URL 확인 필요: {current_url}")
                # URL이 변경되지 않았더라도 요소를 찾았으므로 성공으로 간주
                return True

        except Exception as e:
            self.logger.error(f"릴스 탭 이동 실패: {e}")
            raise ScrapingError(f"릴스 탭으로 이동하는데 실패했습니다: {e}") from e

    def _wait_for_reels_page_load(self, page: Page) -> None:
        """
        릴스 페이지 로딩 완료 대기

        Args:
            page: Playwright Page 객체
        """
        try:
            self.logger.info("릴스 페이지 로딩 대기 중...")
            time.sleep(3)  # 초기 로딩 대기
            
            # 릴스 컨테이너가 나타날 때까지 대기
            reels_container_selectors = [
                'section > main > div',
                'div.xvc5jky',
                'main > div',
            ]
            
            for selector in reels_container_selectors:
                try:
                    container = page.locator(selector).first
                    if container.is_visible(timeout=5000):
                        self.logger.info(f"릴스 컨테이너 발견: {selector}")
                        break
                except Exception:
                    continue

            # 추가 안정화 대기
            time.sleep(2)
            self.logger.info("릴스 페이지 로딩 완료")
        except Exception as e:
            self.logger.warning(f"릴스 페이지 로딩 대기 중 오류 (계속 진행): {e}")

    def _get_current_reel_instancekey(self, page: Page) -> Optional[str]:
        """
        (중복 체크용 백업) 현재 보이는 릴스의 data-instancekey 값 추출

        최근 레이아웃에서는 data-instancekey가 **플레이어 단위**로만 유지되거나
        아예 존재하지 않는 경우가 많아서,
        - "현재 어떤 릴스가 보이는지"를 구분하는 용도로는 사용하지 않는다.
        - 단, 일부 예전 레이아웃에서만 중복 체크용 보조 수단으로 쓴다.
        """
        try:
            instancekey_div = page.locator("div[data-instancekey]").first
            if instancekey_div.is_visible(timeout=1000):
                instancekey = instancekey_div.get_attribute("data-instancekey")
                if instancekey:
                    # INFO 로 남기면 로그가 너무 길어지므로 debug 로만 남김
                    self.logger.debug(
                        f"instancekey 추출 (중복 체크 보조용): {instancekey[:40]}..."
                    )
                    return instancekey
        except Exception as e:
            self.logger.debug(f"instancekey 추출 실패(무시 가능): {e}")

        # instancekey 가 없다고 해서 오류는 아님
        return None

    def _get_current_reel_video(self, page: Page):
        """
        현재 화면(뷰포트)에서 중앙에 가장 가까운 video 요소를 찾는다.

        인스타 릴스 피드는 슬롯(div)이 여러 개 미리 생성되어 있고,
        슬롯 안의 내용만 교체되는 구조라서,
        카드 div 클래스(x1qjc9v5 등)만으로는 "현재 보이는 릴스"를
        안정적으로 식별하기 어렵다.

        따라서 **실제 재생되는 video 요소**를 기준으로 현재 릴스를 판단한다.
        """
        try:
            videos = page.locator("video")
            count = videos.count()
            if not count:
                self.logger.warning("video 태그를 찾을 수 없습니다.")
                return None

            viewport = page.viewport_size
            if not viewport:
                self.logger.debug("viewport 정보를 가져올 수 없음. 첫 번째 video 사용.")
                return videos.first

            center_y = viewport["height"] / 2
            closest_idx: Optional[int] = None
            closest_dist = float("inf")

            for i in range(min(20, count)):  # 너무 많이 보면 느려지니 최대 20개까지만
                v = videos.nth(i)
                try:
                    rect = v.evaluate(
                        "el => { const r = el.getBoundingClientRect(); "
                        "return { top: r.top, bottom: r.bottom, height: r.height }; }"
                    )

                    # 화면에 일부라도 보이는 video 만 대상
                    if rect["bottom"] <= 0 or rect["top"] >= viewport["height"]:
                        continue

                    mid_y = rect["top"] + rect["height"] / 2
                    dist = abs(mid_y - center_y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_idx = i
                except Exception:
                    continue

            if closest_idx is not None:
                v = videos.nth(closest_idx)
                self.logger.info(
                    f"현재 릴스 video 선택 (index={closest_idx}, dist={closest_dist:.1f})"
                )
                return v

        except Exception as e:
            self.logger.debug(f"현재 릴스 video 찾기 실패: {e}")

        return None

    def _get_current_reel_container(self, page: Page):
        """
        현재 화면에서 "재생 중인" 릴스 카드 컨테이너를 찾는다.

        x1qjc9v5 카드들 중 **뷰포트 중앙에 가장 가까운 카드**를 선택한다.

        (중요)
        - 이전에는 data-instancekey 로 "현재 릴스"를 찾으려 했지만,
          로그에서 보듯이 instancekey 값이 계속 동일하게 유지돼
          항상 같은 카드만 바라보는 문제가 있었다.
        - 그래서 이제는 **instancekey 를 전혀 사용하지 않고**,
          화면 중앙 위치만 기준으로 현재 카드를 선택한다.
        """
        try:
            # 카드 컨테이너(div.x1qjc9v5 ...)들 중 화면 중앙에 가장 가까운 것 선택
            card_candidates = page.locator('div.x1qjc9v5')
            count = card_candidates.count()
            if not count:
                # 클래스명이 조금 달라질 것을 대비한 백업 셀렉터
                card_candidates = page.locator(
                    'div[class*="x1qjc9v5"][class*="xg7h5cd"]'
                )
                count = card_candidates.count()

            if not count:
                self.logger.warning("현재 릴스 카드 컨테이너(div.x1qjc9v5)를 찾을 수 없습니다.")
                return None

            viewport = page.viewport_size
            if not viewport:
                self.logger.debug("viewport 정보를 가져올 수 없음. 첫 번째 카드 사용.")
                return card_candidates.first

            # 브라우저의 뷰포트 기준 좌표를 사용하기 위해 getBoundingClientRect() 사용
            # Playwright의 bounding_box()는 페이지 전체 기준 좌표(scrollTop 포함)를 반환하므로,
            # 스크롤된 상태에서는 viewport_height/2 와 비교하면 안 된다.
            # 대신 JS evaluate를 통해 뷰포트 기준 좌표(top)를 직접 가져온다.
            
            closest_idx = None
            closest_distance = float("inf")
            
            # 뷰포트 중앙 Y 좌표
            viewport_center_y = viewport["height"] / 2

            for i in range(min(12, count)):  # 너무 많이 보면 느려지니 12개까지만
                div = card_candidates.nth(i)
                try:
                    # 뷰포트 기준 좌표(top, height) 가져오기
                    rect = div.evaluate("el => { const r = el.getBoundingClientRect(); return { top: r.top, height: r.height, bottom: r.bottom }; }")
                    
                    # 요소의 수직 중앙점 (뷰포트 기준)
                    element_center_y = rect["top"] + rect["height"] / 2
                    
                    # 뷰포트 중앙과의 거리
                    distance = abs(element_center_y - viewport_center_y)
                    
                    # 화면에 보이는 요소만 대상 (적어도 일부라도 보여야 함)
                    if rect["bottom"] > 0 and rect["top"] < viewport["height"]:
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_idx = i
                except Exception:
                    continue

            if closest_idx is not None:
                container = card_candidates.nth(closest_idx)
                self.logger.info(f"현재 릴스 컨테이너 선택 완료 (index: {closest_idx}, 거리: {closest_distance:.1f}px)")
                return container

        except Exception as e:
            self.logger.debug(f"현재 릴스 컨테이너 찾기 실패: {e}")

        return None

    def _extract_current_reel_data(self, page: Page) -> Optional[ReelData]:
        """
        현재 보이는 릴스의 정보를 수집

        Args:
            page: Playwright Page 객체

        Returns:
            추출된 릴스 데이터, 실패 시 None
        """
        try:
            self.logger.info("현재 릴스 정보 수집 중...")
            
            # 현재 URL 확인 (디버깅용)
            current_url = page.url
            self.logger.debug(f"현재 URL: {current_url}")
            
            reel_data = ReelData(
                thumbnail=None,
                likes=None,
                comments=None,
                author=None,
                creator_profile_image=None,
                title=None,
                music=None,
                link=None,
            )

            # 현재 릴스를 대표하는 컨테이너 결정
            # 1순위: 화면 중앙에 가장 가까운 video 기준
            root = page  # 기본값 (최악의 경우 페이지 전체 검색)
            current_video = None  # 이후 썸네일/좋아요/댓글 추출에도 재사용
            try:
                current_video = self._get_current_reel_video(page)
                if current_video:
                    try:
                        # 좋아요 버튼이 함께 들어있는 카드 컨테이너를 우선 시도
                        container = current_video.locator(
                            'xpath=ancestor::div[.//svg[@aria-label="좋아요"]][1]'
                        )
                        if container.count() > 0:
                            root = container.first
                            self.logger.info("현재 릴스 컨테이너를 video+좋아요 버튼 기준으로 선택")
                        else:
                            # fallback: video의 가장 가까운 상위 div 하나라도 사용
                            fallback = current_video.locator("xpath=ancestor::div[1]")
                            if fallback.count() > 0:
                                root = fallback.first
                                self.logger.info("현재 릴스 컨테이너를 video 상위 div 기준으로 선택")
                    except Exception as e:
                        self.logger.debug(f"video 기반 컨테이너 결정 실패: {e}")
                else:
                    # 2순위: 기존 카드 컨테이너 로직 (x1qjc9v5) 사용
                    try:
                        current_container = self._get_current_reel_container(page)
                        if current_container:
                            root = current_container
                        else:
                            self.logger.info(
                                "현재 릴스 컨테이너를 찾지 못해 페이지 전체에서 검색합니다."
                            )
                    except Exception as e:
                        self.logger.debug(
                            f"현재 릴스 컨테이너 결정 실패 (페이지 전체 사용): {e}"
                        )
            except Exception as e:
                self.logger.debug(f"현재 릴스 컨테이너 결정 중 예외 (페이지 전체 사용): {e}")

            # 좋아요 수 추출 - reels.txt에서 확인한 규칙 기반
            try:
                # 방법 1: 좋아요 버튼 찾고 같은 컨테이너 내의 span.html-span.x1vvkbs 찾기
                like_button_selectors = [
                    'svg[aria-label="좋아요"]',
                    'button[aria-label*="좋아요"]',
                    'svg[aria-label*="Like"]',
                ]
                
                for selector in like_button_selectors:
                    try:
                        like_button = root.locator(selector).first
                        if like_button.is_visible(timeout=500):
                            # 좋아요 버튼의 조상 요소에서 span.html-span.x1vvkbs 찾기
                            # 좋아요 버튼과 같은 html-div 컨테이너 내의 형제 요소 찾기
                            parent_div = like_button.locator('xpath=ancestor::div[contains(@class, "html-div")][position()<=3]')
                            for i in range(min(3, parent_div.count())):
                                try:
                                    container = parent_div.nth(i)
                                    # span.html-span.x1vvkbs 클래스를 가진 요소 찾기
                                    number_spans = container.locator('span.html-span.x1vvkbs').all()
                                    for span in number_spans[:3]:
                                        try:
                                            text = span.text_content() or ""
                                            text = text.strip()
                                            # 숫자 형식 처리 (예: "17.4만", "4346", "1,234")
                                            if re.match(r'^[\d.,만천억]+$', text.replace(' ', '')):
                                                likes_value = None

                                                # "만" 단위 처리
                                                if "만" in text:
                                                    num_match = re.search(r'([\d.]+)', text)
                                                    if num_match:
                                                        num_val = float(num_match.group(1))
                                                        likes_value = int(num_val * 10000)

                                                # "천" 단위 처리
                                                elif "천" in text:
                                                    num_match = re.search(r'([\d.]+)', text)
                                                    if num_match:
                                                        num_val = float(num_match.group(1))
                                                        likes_value = int(num_val * 1000)

                                                # 단순 숫자 (콤마/점 포함)
                                                else:
                                                    likes_str = text.replace(",", "").replace(".", "")
                                                    if likes_str.isdigit():
                                                        likes_value = int(likes_str)

                                                if likes_value and likes_value > 0:
                                                    reel_data.likes = likes_value
                                                    self.logger.info(f"좋아요 수: {reel_data.likes}")
                                                    break
                                        except Exception:
                                            continue
                                    if reel_data.likes:
                                        break
                                except Exception:
                                    continue
                            if reel_data.likes:
                                break
                    except Exception:
                        continue

                # 방법 2 (백업): 화면 전체에서 현재 비디오와 세로 위치가 가장 가까운 "좋아요" 아이콘 기준으로 수집
                if not reel_data.likes and current_video:
                    try:
                        like_icons = page.locator(
                            'svg[aria-label="좋아요"], svg[aria-label*="Like"]'
                        )
                        icon_count = like_icons.count()
                        if icon_count:
                            # 현재 비디오의 세로 중앙 위치
                            video_rect = current_video.evaluate(
                                "el => { const r = el.getBoundingClientRect(); "
                                "return { top: r.top, height: r.height }; }"
                            )
                            video_center_y = video_rect["top"] + video_rect["height"] / 2

                            closest_idx = None
                            closest_dist = float("inf")

                            for i in range(min(10, icon_count)):
                                try:
                                    icon = like_icons.nth(i)
                                    rect = icon.evaluate(
                                        "el => { const r = el.getBoundingClientRect(); "
                                        "return { top: r.top, height: r.height }; }"
                                    )
                                    center_y = rect["top"] + rect["height"] / 2
                                    dist = abs(center_y - video_center_y)
                                    if dist < closest_dist:
                                        closest_dist = dist
                                        closest_idx = i
                                except Exception:
                                    continue

                            if closest_idx is not None:
                                like_button = like_icons.nth(closest_idx)
                                parent_div = like_button.locator(
                                    'xpath=ancestor::div[contains(@class, "html-div")][1]'
                                )
                                if parent_div.count() > 0:
                                    container = parent_div.first
                                    number_spans = container.locator(
                                        'span.html-span.x1vvkbs'
                                    ).all()
                                    for span in number_spans[:3]:
                                        try:
                                            text = (span.text_content() or "").strip()
                                            if re.match(
                                                r'^[\d.,만천억]+$', text.replace(" ", "")
                                            ):
                                                likes_value = None
                                                if "만" in text:
                                                    m = re.search(r"([\d.]+)", text)
                                                    if m:
                                                        likes_value = int(
                                                            float(m.group(1)) * 10000
                                                        )
                                                elif "천" in text:
                                                    m = re.search(r"([\d.]+)", text)
                                                    if m:
                                                        likes_value = int(
                                                            float(m.group(1)) * 1000
                                                        )
                                                else:
                                                    likes_str = (
                                                        text.replace(",", "")
                                                        .replace(".", "")
                                                        .strip()
                                                    )
                                                    if likes_str.isdigit():
                                                        likes_value = int(likes_str)

                                                if likes_value is not None:
                                                    reel_data.likes = likes_value
                                                    self.logger.info(
                                                        f"좋아요 수(백업): {reel_data.likes}"
                                                    )
                                                    break
                                        except Exception:
                                            continue
                    except Exception:
                        pass

            except Exception as e:
                self.logger.debug(f"좋아요 수 추출 실패: {e}")

            # 댓글 수 추출 - reels.txt에서 확인한 규칙 기반
            try:
                # 방법 1: 댓글 버튼 찾고 같은 컨테이너 내의 span.html-span.x1vvkbs 찾기
                comment_button_selectors = [
                    'svg[aria-label="댓글"]',
                    'button[aria-label*="댓글"]',
                    'svg[aria-label*="Comment"]',
                ]
                
                for selector in comment_button_selectors:
                    try:
                        comment_button = root.locator(selector).first
                        if comment_button.is_visible(timeout=500):
                            # 댓글 버튼의 조상 요소에서 span.html-span.x1vvkbs 찾기
                            parent_div = comment_button.locator('xpath=ancestor::div[contains(@class, "html-div")][position()<=3]')
                            for i in range(min(3, parent_div.count())):
                                try:
                                    container = parent_div.nth(i)
                                    # span.html-span.x1vvkbs 클래스를 가진 요소 찾기
                                    number_spans = container.locator('span.html-span.x1vvkbs').all()
                                    for span in number_spans[:3]:
                                        try:
                                            text = span.text_content() or ""
                                            text = text.strip()
                                            # 숫자 형식 처리 (댓글은 보통 숫자만)
                                            if re.match(r'^[\d,]+$', text.replace(' ', '')):
                                                comments_str = text.replace(',', '').replace('.', '')
                                                if comments_str.isdigit():
                                                    comments_value = int(comments_str)
                                                    if comments_value >= 0:
                                                        reel_data.comments = comments_value
                                                        self.logger.info(f"댓글 수: {reel_data.comments}")
                                                        break
                                        except Exception:
                                            continue
                                    if reel_data.comments is not None:
                                        break
                                except Exception:
                                    continue
                            if reel_data.comments is not None:
                                break
                    except Exception:
                        continue

                # 방법 2 (백업): 현재 비디오 기준으로 세로 위치가 가장 가까운 "댓글" 아이콘 사용
                if reel_data.comments is None and current_video:
                    try:
                        comment_icons = page.locator(
                            'svg[aria-label="댓글"], svg[aria-label*="Comment"]'
                        )
                        icon_count = comment_icons.count()
                        if icon_count:
                            video_rect = current_video.evaluate(
                                "el => { const r = el.getBoundingClientRect(); "
                                "return { top: r.top, height: r.height }; }"
                            )
                            video_center_y = video_rect["top"] + video_rect["height"] / 2

                            closest_idx = None
                            closest_dist = float("inf")

                            for i in range(min(10, icon_count)):
                                try:
                                    icon = comment_icons.nth(i)
                                    rect = icon.evaluate(
                                        "el => { const r = el.getBoundingClientRect(); "
                                        "return { top: r.top, height: r.height }; }"
                                    )
                                    center_y = rect["top"] + rect["height"] / 2
                                    dist = abs(center_y - video_center_y)
                                    if dist < closest_dist:
                                        closest_dist = dist
                                        closest_idx = i
                                except Exception:
                                    continue

                            if closest_idx is not None:
                                comment_button = comment_icons.nth(closest_idx)
                                parent_div = comment_button.locator(
                                    'xpath=ancestor::div[contains(@class, "html-div")][1]'
                                )
                                if parent_div.count() > 0:
                                    container = parent_div.first
                                    number_spans = container.locator(
                                        'span.html-span.x1vvkbs'
                                    ).all()
                                    for span in number_spans[:3]:
                                        try:
                                            text = (span.text_content() or "").strip()
                                            if re.match(
                                                r'^[\d,]+$', text.replace(" ", "")
                                            ):
                                                comments_str = (
                                                    text.replace(",", "")
                                                    .replace(".", "")
                                                    .strip()
                                                )
                                                if comments_str.isdigit():
                                                    comments_value = int(comments_str)
                                                    reel_data.comments = comments_value
                                                    self.logger.info(
                                                        f"댓글 수(백업): {reel_data.comments}"
                                                    )
                                                    break
                                        except Exception:
                                            continue
                    except Exception:
                        pass

            except Exception as e:
                self.logger.debug(f"댓글 수 추출 실패: {e}")

            # 크리에이터 이름 추출 - reels.txt에서 확인한 규칙 기반
            try:
                # 방법 1: aria-label에 "님의 릴스"가 포함된 링크에서 추출
                try:
                    creator_link = root.locator('a[aria-label*="님의 릴스"]').first
                    if creator_link.is_visible(timeout=500):
                        # href에서 사용자명 추출 (예: /jeonnamdragons_fc/reels/)
                        href = creator_link.get_attribute("href") or ""
                        if href.startswith("/") and "/reels/" in href:
                            username_match = re.search(r'^/([^/]+)/reels', href)
                            if username_match:
                                reel_data.author = username_match.group(1)
                                self.logger.info(f"크리에이터 (href): {reel_data.author}")
                            else:
                                # 링크 내부의 span[dir="auto"]에서 텍스트 추출
                                author_span = creator_link.locator('span[dir="auto"]').first
                                if author_span.is_visible(timeout=500):
                                    author_text = author_span.text_content() or ""
                                    if author_text.strip() and len(author_text.strip()) < 50:
                                        reel_data.author = author_text.strip()
                                        self.logger.info(f"크리에이터 (텍스트): {reel_data.author}")
                except Exception:
                    pass
                
                # 방법 2: 프로필 이미지 근처의 span[dir="auto"]에서 추출
                if not reel_data.author:
                    try:
                        profile_imgs = root.locator(
                            'img[alt*="프로필 사진"], img[alt*="님의 프로필 사진"]'
                        ).all()
                        for img in profile_imgs[:5]:
                            try:
                                # 이미지의 부모 링크에서 span 찾기
                                parent_link = img.locator('xpath=ancestor::a[1]')
                                if parent_link.count() > 0:
                                    author_span = parent_link.locator('span[dir="auto"]').first
                                    if author_span.is_visible(timeout=500):
                                        author_text = author_span.text_content() or ""
                                        if author_text.strip() and len(author_text.strip()) < 50:
                                            reel_data.author = author_text.strip()
                                            self.logger.info(f"크리에이터 (프로필 이미지): {reel_data.author}")
                                            break
                            except Exception:
                                continue
                    except Exception:
                        pass
                        
            except Exception as e:
                self.logger.debug(f"크리에이터 이름 추출 실패: {e}")

            # 크리에이터 프로필 사진 추출 - reels.txt에서 확인한 규칙 기반
            try:
                # 방법 1: alt에 "님의 프로필 사진"이 포함된 이미지 찾기
                try:
                    profile_img = root.locator('img[alt*="님의 프로필 사진"]').first
                    if profile_img.is_visible(timeout=500):
                        img_src = profile_img.get_attribute("src")
                        if img_src and "cdninstagram" in img_src:
                            reel_data.creator_profile_image = img_src
                            self.logger.info(f"프로필 사진: {reel_data.creator_profile_image[:50]}...")
                except Exception:
                    pass
                
                # 방법 2: 백업 - 프로필 링크 내부의 이미지
                if not reel_data.creator_profile_image:
                    try:
                        creator_link = root.locator('a[aria-label*="님의 릴스"]').first
                        if creator_link.is_visible(timeout=500):
                            profile_img = creator_link.locator('img[src*="cdninstagram"]').first
                            if profile_img.is_visible(timeout=500):
                                img_src = profile_img.get_attribute("src")
                                if img_src:
                                    reel_data.creator_profile_image = img_src
                                    self.logger.info(f"프로필 사진 (백업): {reel_data.creator_profile_image[:50]}...")
                    except Exception:
                        pass
                        
            except Exception as e:
                self.logger.debug(f"프로필 사진 추출 실패: {e}")

            # 제목 추출 - 제공된 HTML 구조 기반
            try:
                # 방법 1: span.x6ikm8r.x10wlt62.xuxw1ft 클래스를 가진 요소 (제목 스타일)
                try:
                    title_spans = root.locator('span.x6ikm8r.x10wlt62.xuxw1ft').all()
                    for span in title_spans[:10]:
                        try:
                            title_text = span.text_content() or ""
                            title_text = title_text.strip()
                            # 제목 조건: 충분히 긴 텍스트, 사용자명/음악과 다름
                            if (len(title_text) > 5 and len(title_text) < 500 and 
                                title_text != reel_data.author and 
                                (not reel_data.music or title_text != reel_data.music) and
                                not title_text.startswith('@') and
                                not re.match(r'^[\d,]+$', title_text) and
                                not title_text.startswith('오리지널')):
                                reel_data.title = title_text
                                self.logger.info(f"제목: {reel_data.title[:50]}...")
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
                
                # 방법 2: span[dir="auto"] 중에서 긴 텍스트 찾기 (백업)
                if not reel_data.title:
                    try:
                        title_spans = root.locator('span[dir="auto"]').all()
                        for span in title_spans[:20]:
                            try:
                                title_text = span.text_content() or ""
                                title_text = title_text.strip()
                                if (len(title_text) > 10 and len(title_text) < 500 and 
                                    title_text != reel_data.author and 
                                    (not reel_data.music or title_text != reel_data.music) and
                                    not title_text.startswith('@') and
                                    not re.match(r'^[\d,]+$', title_text)):
                                    reel_data.title = title_text
                                    self.logger.info(f"제목 (백업): {reel_data.title[:50]}...")
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass
                        
            except Exception as e:
                self.logger.debug(f"제목 추출 실패: {e}")

            # 영상 썸네일 추출 - reels.txt에서 확인한 규칙 기반
            try:
                # 방법 0: 현재 비디오의 poster 속성 사용 (가장 정확한 경우)
                try:
                    video_for_thumb = current_video or self._get_current_reel_video(page)
                except Exception:
                    video_for_thumb = None

                if video_for_thumb:
                    try:
                        poster = video_for_thumb.get_attribute("poster")
                        if poster and "cdninstagram" in poster:
                            reel_data.thumbnail = poster
                            self.logger.info(
                                f"썸네일(poster): {reel_data.thumbnail[:50]}..."
                            )
                    except Exception:
                        pass

                # 방법 1: img.xz74otr 클래스를 가진 이미지 (릴스 썸네일)
                if not reel_data.thumbnail:
                    try:
                        thumbnail_img = (
                            (current_video or root)
                            .locator(
                                'xpath=ancestor::div[.//img[contains(@class, "xz74otr")]][1]'
                            )
                            .locator(
                                'img.xz74otr[src*="cdninstagram"]:not([alt*="님의 프로필 사진"])'
                            )
                            .first
                        )
                        if thumbnail_img.is_visible(timeout=500):
                            img_src = thumbnail_img.get_attribute("src")
                            if img_src and ("t51" in img_src or "t52" in img_src):
                                reel_data.thumbnail = img_src
                                self.logger.info(
                                    f"썸네일: {reel_data.thumbnail[:50]}..."
                                )
                    except Exception:
                        pass

                # 방법 2: 비디오 근처의 이미지 (프로필 사진 제외)
                if not reel_data.thumbnail and video_for_thumb:
                    try:
                        parent = video_for_thumb.locator("xpath=ancestor::div[2]")
                        if parent.count() > 0:
                            thumbnail_img = parent.locator(
                                'img[src*="cdninstagram"][src*="/v/t"]:not([alt*="님의 프로필 사진"])'
                            ).first
                            if thumbnail_img.is_visible(timeout=500):
                                img_src = thumbnail_img.get_attribute("src")
                                if img_src:
                                    reel_data.thumbnail = img_src
                                    self.logger.info(
                                        f"썸네일 (비디오 근처): {reel_data.thumbnail[:50]}..."
                                    )
                    except Exception:
                        pass

            except Exception as e:
                self.logger.debug(f"썸네일 추출 실패: {e}")

            # 배경음악 추출 - reels.txt에서 확인한 규칙 기반
            try:
                # 방법 1: /audio/ 링크 내부의 span.xuxw1ft 또는 span.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft 찾기
                try:
                    audio_link = root.locator('a[href*="/reels/audio/"]').first
                    if audio_link.is_visible(timeout=500):
                        # 링크 내부의 span.xuxw1ft 또는 span.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft 클래스 요소 찾기
                        music_spans = audio_link.locator('span.xuxw1ft, span.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft').all()
                        for span in music_spans[:3]:
                            try:
                                music_text = span.text_content() or ""
                                music_text = music_text.strip()
                                # "오리지널 오디오"가 포함된 텍스트 찾기 (예: "jeonnamdragons_fc · 오리지널 오디오")
                                if music_text and len(music_text) > 3:
                                    reel_data.music = music_text
                                    self.logger.info(f"배경음악: {reel_data.music}")
                                    break
                            except Exception:
                                continue
                        
                        # 백업: 링크 내부의 모든 텍스트
                        if not reel_data.music:
                            music_text = audio_link.text_content() or ""
                            music_text = music_text.strip()
                            if music_text and len(music_text) > 3:
                                reel_data.music = music_text
                                self.logger.info(f"배경음악 (백업): {reel_data.music}")
                except Exception:
                    pass
                
                # 방법 2: 텍스트에 "오리지널 오디오" 또는 "· 오리지널"이 포함된 요소 찾기
                if not reel_data.music:
                    try:
                        all_spans = root.locator(
                            'span.xuxw1ft, span.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft'
                        ).all()
                        for span in all_spans[:20]:
                            try:
                                text = span.text_content() or ""
                                text = text.strip()
                                if ("오리지널 오디오" in text or "· 오리지널" in text) and len(text) > 5:
                                    reel_data.music = text
                                    self.logger.info(f"배경음악 (패턴): {reel_data.music}")
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass
                        
            except Exception as e:
                self.logger.debug(f"배경음악 추출 실패: {e}")

            # 게시물 링크 추출 - URL에서 직접 추출
            try:
                # 현재 페이지 URL 그대로를 사용 (릴스 전환 시 URL이 함께 바뀌므로 충분히 구분 가능)
                current_url = page.evaluate("window.location.href")
                if isinstance(current_url, str) and "instagram.com" in current_url:
                    reel_data.link = current_url
                    self.logger.info(f"링크 (URL): {reel_data.link}")

            except Exception as e:
                self.logger.debug(f"링크 추출 실패: {e}")

            self.logger.info("릴스 정보 수집 완료")
            return reel_data

        except Exception as e:
            self.logger.error(f"릴스 정보 수집 중 오류: {e}")
            return None

    def _move_to_next_reel(self, page: Page) -> bool:
        """
        다음 릴스로 이동

        Args:
            page: Playwright Page 객체

        Returns:
            이동 성공 여부
        """
        try:
            self.logger.info("다음 릴스로 이동 중...")

            # 이동 전 URL 저장 (JS로 직접 가져오기)
            initial_url = page.evaluate("window.location.href")
            self.logger.debug(f"이동 전 URL: {initial_url}")
            
            # 방법 1: 마우스 휠로 화면 전체 높이만큼 스크롤 (1번만 시도)
            try:
                viewport = page.viewport_size
                if viewport:
                    viewport_height = viewport["height"]
                    # 화면 중앙에서 아래로 화면 높이만큼 스크롤 (1번만)
                    page.mouse.move(viewport["width"] // 2, viewport["height"] // 2)
                    page.mouse.wheel(0, viewport_height)

                    # 충분한 대기 시간 (릴스 전환 대기)
                    time.sleep(4)  # 대기 시간 증가

                    # URL 변화 확인 (JS로 직접 가져오기)
                    new_url = page.evaluate("window.location.href")
                    if new_url != initial_url:
                        # /reels/<id>/ 형태면 ID 기준으로도 한 번 더 로그 남김
                        new_match = re.search(r"/reels?/([^/?#]+)/?", new_url)
                        old_match = re.search(r"/reels?/([^/?#]+)/?", initial_url)
                        if new_match and old_match and new_match.group(1) != old_match.group(1):
                            self.logger.info(
                                f"스크롤로 다음 릴스 이동 완료 (reels ID 변경: {new_match.group(1)})"
                            )
                        else:
                            self.logger.info(
                                f"스크롤로 다음 릴스 이동 완료 (URL 변경): {new_url}"
                            )
                        return True

                    # 변화가 없으면 실패로 판단
                    self.logger.debug("스크롤 후 변화 없음")
            except Exception as e:
                self.logger.debug(f"마우스 휠 스크롤 실패: {e}")
            
            # 방법 1이 실패했을 때만 다른 방법 시도
            # 방법 2: 화살표 아래 키 1번만 누르기
            try:
                self.logger.debug("마우스 휠 실패 또는 변화 없음, 화살표 키 시도...")
                page.keyboard.press("ArrowDown")
                time.sleep(4)  # 충분한 대기

                # URL의 reel ID 또는 전체 URL 변경으로 확인
                new_url = page.evaluate("window.location.href")
                if new_url != initial_url:
                    new_match = re.search(r"/reels?/([^/?#]+)/?", new_url)
                    old_match = re.search(r"/reels?/([^/?#]+)/?", initial_url)
                    if new_match and old_match and new_match.group(1) != old_match.group(1):
                        self.logger.info(
                            f"화살표 키로 다음 릴스 이동 완료 (reels ID 변경: {new_match.group(1)})"
                        )
                    else:
                        self.logger.info(f"화살표 키로 다음 릴스 이동 완료 (URL 변경): {new_url}")
                    return True
            except Exception as e:
                self.logger.debug(f"화살표 키 이동 실패: {e}")
            
            self.logger.warning("다음 릴스로 이동하지 못했습니다")
            return False

        except Exception as e:
            self.logger.warning(f"다음 릴스 이동 실패: {e}")
            return False

    def start_collecting_reels(self) -> None:
        """
        릴스 수집 시작 (무한 반복)

        릴스 탭에서 현재 릴스 정보를 수집하고, 다음 릴스로 이동하여 반복합니다.
        수집한 데이터는 주기적으로 저장합니다.
        """
        try:
            if self.browser_manager is None:
                raise ScrapingError("브라우저가 시작되지 않았습니다. 먼저 로그인하세요.")

            page = self.browser_manager.get_page()
            self.logger.info("릴스 수집 시작...")

            # 릴스 페이지 로딩 대기
            self._wait_for_reels_page_load(page)

            collected_reels: list[ReelData] = []
            collected_reel_ids: set[str] = set()  # 중복 체크용 (URL 기반 ID)
            collected_thumbnails: set[str] = set()  # 썸네일 중복 체크용
            save_interval = 10  # 10개마다 저장
            consecutive_failures = 0  # 연속 실패 횟수
            max_failures = 5  # 최대 연속 실패 허용 횟수
            
            while True:
                try:
                    # 현재 릴스 정보 수집
                    reel_data = self._extract_current_reel_data(page)
                    
                    if reel_data:
                        # 중복 체크 (여러 방법 사용)
                        is_duplicate = False
                        duplicate_reason = None
                        
                        # 방법 1: ReelData.link 또는 현재 페이지 URL에서 /reels/<id>/ 기준 중복 체크
                        reel_id: Optional[str] = None
                        url_candidates: list[tuple[str, str]] = []

                        # 우선순위 1: reel_data.link (가능하면 이 값을 신뢰)
                        if reel_data.link and isinstance(reel_data.link, str):
                            url_candidates.append(("link", reel_data.link))

                        # 백업용: page.url
                        current_url = page.url
                        if isinstance(current_url, str):
                            url_candidates.append(("URL", current_url))

                        for source_name, url_value in url_candidates:
                            match = re.search(r"/reels?/([^/?#]+)/?", url_value)
                            if not match:
                                continue

                            candidate_id = match.group(1)

                            # 이미 같은 ID로 판정된 경우는 다시 확인할 필요 없음
                            if reel_id is not None and candidate_id == reel_id:
                                continue

                            reel_id = candidate_id

                            if reel_id in collected_reel_ids:
                                is_duplicate = True
                                duplicate_reason = f"reels ID ({source_name}): {reel_id}"
                            else:
                                collected_reel_ids.add(reel_id)

                            # 한 번 유효 ID를 처리했으면 더 이상 다른 소스는 볼 필요 없음
                            break
                        
                        # 방법 3: 백업 - 썸네일 URL로 체크
                        if not is_duplicate and reel_data.thumbnail:
                            thumbnail_key = reel_data.thumbnail
                            if thumbnail_key in collected_thumbnails:
                                is_duplicate = True
                                duplicate_reason = f"썸네일: {reel_data.thumbnail[:50]}..."
                            else:
                                collected_thumbnails.add(thumbnail_key)
                        
                        if is_duplicate:
                            self.logger.warning(f"중복 릴스 감지 ({duplicate_reason})")
                        
                        # 중복이 아닌 경우에만 추가
                        if not is_duplicate:
                            collected_reels.append(reel_data)
                            consecutive_failures = 0  # 성공 시 실패 카운터 리셋
                            self.logger.info(f"수집된 릴스 수: {len(collected_reels)} (작성자: {reel_data.author})")
                        else:
                            self.logger.info("중복 릴스 건너뜀")
                        
                        # 주기적으로 저장
                        if len(collected_reels) >= save_interval:
                            self.logger.info(f"{save_interval}개 수집 완료. 임시 저장 중...")
                            self.save_to_json(collected_reels)
                            save_interval += 10
                    
                    # 다음 릴스로 이동
                    if not self._move_to_next_reel(page):
                        consecutive_failures += 1
                        self.logger.warning(f"다음 릴스로 이동하지 못했습니다 ({consecutive_failures}/{max_failures}). 잠시 대기 후 재시도...")
                        
                        if consecutive_failures >= max_failures:
                            self.logger.error(f"연속 {max_failures}회 이동 실패. 수집 중단.")
                            break
                        
                        time.sleep(3)
                    else:
                        consecutive_failures = 0  # 이동 성공 시 실패 카운터 리셋
                        # 이동 성공 후 추가 안정화 대기
                        time.sleep(1)
                        random_delay(0.5, 1.0)

                except KeyboardInterrupt:
                    self.logger.info("사용자에 의해 중단되었습니다.")
                    # 중단 전 마지막 저장
                    if collected_reels:
                        self.logger.info("중단 전 데이터 저장 중...")
                        self.save_to_json(collected_reels)
                    break
                except Exception as e:
                    self.logger.error(f"릴스 수집 중 오류 (계속 진행): {e}")
                    time.sleep(2)

        except Exception as e:
            self.logger.error(f"릴스 수집 실패: {e}")
            raise ScrapingError(f"릴스 수집에 실패했습니다: {e}") from e

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
                creator_profile_image=None,
                title=None,
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