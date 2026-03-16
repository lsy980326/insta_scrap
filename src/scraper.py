import json
import re
import time
from pathlib import Path

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
from .utils.session_manager import SessionManager
from .utils.wait_utils import safe_fill_input, wait_for_element

# 데이터베이스 관련 import (선택적)
try:
    from .database import get_db_session, init_db
    from .database.repositories import CreatorRepository, ReelRepository
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# S3 썸네일 아카이빙 import (선택적)
try:
    from .thumbnail_archiver import build_archiver_from_config
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False


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

    # 클래스 레벨 글로벌 캐시: 모든 릴스 데이터를 저장 (Key: shortcode)
    _reels_cache: dict[str, dict] = {}

    def __init__(
        self,
        config: ScrapingConfig | None = None,
        username: str | None = None,
        password: str | None = None,
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
        self.browser_manager: BrowserManager | None = None
        self.logger = get_logger(self.__class__.__name__)
        self.session_manager = SessionManager(self.config)
        self._network_listener_registered = False  # 네트워크 리스너 등록 여부

        # 출력 디렉토리 생성
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # 데이터베이스 초기화
        self._db_enabled = False
        self.logger.info(f"DB 설정 확인: db_enabled={self.config.db_enabled}, DB_AVAILABLE={DB_AVAILABLE}")
        if self.config.db_enabled and DB_AVAILABLE:
            self.logger.info("DB 초기화 시도 중...")
            if init_db(self.config):
                self._db_enabled = True
                self.logger.info("✅ 데이터베이스 연결 초기화 완료")
            else:
                self.logger.warning("❌ 데이터베이스 연결 실패. 파일 저장만 사용합니다.")
        elif self.config.db_enabled and not DB_AVAILABLE:
            self.logger.warning("❌ 데이터베이스 모듈을 사용할 수 없습니다. 파일 저장만 사용합니다.")
        else:
            self.logger.info(f"DB 비활성화됨 (db_enabled={self.config.db_enabled})")

        self.logger.info("InstagramReelsScraper 초기화 완료")

    def login(self, username: str | None = None, password: str | None = None) -> bool:
        """
        인스타그램에 로그인 (세션 관리 포함)

        세션 관리 플로우:
        1. 저장된 세션(쿠키 + User-Agent) 로드 시도
        2. 세션이 있으면 브라우저에 설정하고 검증
        3. 세션이 유효하면 로그인 완료
        4. 세션이 없거나 무효하면 전체 로그인 진행
        5. 로그인 성공 후 세션 저장

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

        account_id = username

        try:
            self.logger.info(f"로그인 시도: {account_id}")

            # 1단계: 저장된 세션 로드 시도
            session_data = self.session_manager.load_session(account_id)

            if session_data:
                cookies = session_data.get("cookies")
                user_agent = session_data.get("user_agent")

                if cookies and user_agent:
                    self.logger.info("✅ 저장된 세션 발견, 세션 검증 시도 중...")

                    # 2단계: User-Agent와 함께 브라우저 시작
                    if self.browser_manager is None:
                        self.browser_manager = BrowserManager(self.config, user_agent=user_agent)
                        self.browser_manager.start()

                    # 3단계: 쿠키 설정
                    try:
                        self.browser_manager.set_cookies(cookies)
                    except Exception as e:
                        self.logger.warning(f"쿠키 설정 실패, 전체 로그인 진행: {e}")
                        session_data = None  # 세션 사용 불가, 전체 로그인 진행

                    # 4단계: 세션 검증
                    if session_data:
                        page = self.browser_manager.get_page()
                        if self.session_manager.verify_session(page, account_id=account_id):
                            self.logger.info("✅ 저장된 세션으로 로그인 성공")
                            self.username = username
                            self.password = password

                            # 세션으로 로그인 성공 시 릴스 탭으로 이동
                            try:
                                self.logger.info("릴스 탭으로 이동 시도 중...")
                                self.navigate_to_reels_tab()
                                self.logger.info("릴스 탭 이동 완료")
                                return True
                            except Exception as e:
                                self.logger.warning(f"릴스 탭 이동 실패 (세션 만료 의심, 전체 로그인 진행): {e}")
                                session_data = None  # 세션 무효화 → 전체 로그인으로 fallthrough
                        else:
                            self.logger.warning("⚠️ 저장된 세션이 만료됨, 전체 로그인 진행")

            # 5단계: 전체 로그인 (세션 없음 또는 검증 실패)
            if not session_data or not session_data.get("cookies") or not session_data.get("user_agent"):
                self.logger.info("전체 로그인 프로세스 시작...")

            # 브라우저 시작 (아직 시작되지 않은 경우)
            if self.browser_manager is None:
                self.browser_manager = BrowserManager(self.config)
                self.browser_manager.start()

            page = self.browser_manager.get_page()

            # ── 로그인 페이지 직접 접근 ──────────────────────────────────────
            # 메인 페이지(/)에서 로그인 링크를 찾는 방식은 UI 변경에 취약.
            # /accounts/login/ 은 항상 로그인 폼을 보여주므로 직접 이동.
            self.logger.info("로그인 페이지 직접 접근 중...")
            page.goto(
                "https://www.instagram.com/accounts/login/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            random_delay(1.5, 2.5)
            simulate_page_interaction(page, min_actions=1, max_actions=2)

            # 쿠키 수락 팝업 (있는 경우만)
            try:
                cookie_btn = page.locator(
                    'button:has-text("Accept"), button:has-text("수락"), button:has-text("許可")'
                ).first
                if cookie_btn.is_visible(timeout=2000):
                    cookie_btn.click()
                    page.wait_for_timeout(800)
            except Exception:
                pass

            # 로그인 폼 대기 — autocomplete 속성은 UI 버전과 무관하게 안정적
            debug_dir = self.config.output_dir / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                page.wait_for_selector(
                    'input[autocomplete*="username"], input[type="text"]',
                    timeout=15000,
                    state="visible",
                )
            except Exception:
                try:
                    page.wait_for_selector("input", timeout=10000, state="visible")
                except Exception:
                    # 실패 시 현재 화면 스크린샷 저장 후 예외 전파
                    page.screenshot(path=str(debug_dir / "login_failed.png"))
                    self.logger.error(f"로그인 페이지 로드 실패 — URL: {page.url} / 스크린샷: {debug_dir}/login_failed.png")
                    raise

            self.logger.info(f"로그인 페이지 로드 완료: {page.url}")

            # 디버그 스크린샷
            page.screenshot(path=str(debug_dir / "login_page.png"))

            # ── 사용자명 입력 ──────────────────────────────────────────────
            # autocomplete 기반 → 타입 기반 순서로 시도 (name 속성은 자주 변경됨)
            username_selectors = [
                'input[autocomplete="username webauthn"]',  # 최신 UI
                'input[autocomplete="username"]',           # 이전 UI
                'input[type="text"]:visible',               # 타입 기반 fallback
                'input:not([type="password"]):visible',     # password 아닌 첫 input
            ]
            username_input = wait_for_element(
                page, username_selectors, timeout=10000, description="사용자명 입력 필드"
            )
            if not username_input:
                raise LoginError("사용자명 입력 필드를 찾을 수 없습니다.")
            if not safe_fill_input(username_input, username, description="사용자명"):
                raise LoginError("사용자명 입력에 실패했습니다.")
            page.wait_for_timeout(500)

            # ── 비밀번호 입력 ──────────────────────────────────────────────
            # type="password" 는 UI 버전에 관계없이 불변
            password_input = wait_for_element(
                page,
                ['input[type="password"]:visible', 'input[type="password"]'],
                timeout=5000,
                description="비밀번호 입력 필드",
            )
            if not password_input:
                raise LoginError("비밀번호 입력 필드를 찾을 수 없습니다.")
            if not safe_fill_input(password_input, password, description="비밀번호"):
                raise LoginError("비밀번호 입력에 실패했습니다.")
            page.wait_for_timeout(500)

            # ── Enter 키로 제출 ────────────────────────────────────────────
            # 버튼 셀렉터는 UI 버전/언어마다 달라 불안정 → Enter 키로 대체
            self.logger.info("Enter 키로 로그인 제출 중...")
            page.keyboard.press("Enter")

            # ── URL 변화 기반 로그인 성공 감지 (최대 30초) ─────────────────
            # 고정 sleep(20) 대신 실제 URL 변화를 기다림 → 빠르면 빠를수록 좋음
            self.logger.info("로그인 처리 대기 중... (URL 변화 감지, 최대 30초)")
            try:
                page.wait_for_url(
                    lambda url: "accounts/login" not in url and "/login" not in url,
                    timeout=30000,
                )
                self.logger.info("로그인 성공 감지 (URL 변화 확인)")
            except Exception:
                # URL 변화 없으면 현재 URL로 최종 판단
                pass

            # 로그인 결과 확인 및 리다이렉트 감지
            try:
                # 페이지가 완전히 로드될 때까지 대기
                page.wait_for_load_state("domcontentloaded", timeout=5000)
                random_delay(1.0, 2.0)

                current_url = page.url
                self.logger.info(f"로그인 후 현재 URL: {current_url}")

                # 로그인 페이지로 리다이렉트되었는지 확인
                if "accounts/login" in current_url or "/login" in current_url:
                    self.logger.error("로그인 페이지로 리다이렉트되었습니다.")
                    self.logger.error("로그인에 실패했거나 인증이 필요합니다.")
                    raise LoginError("로그인에 실패했습니다. 로그인 페이지로 리다이렉트되었습니다.")
                else:
                    self.logger.info("로그인 성공 확인 (로그인 페이지가 아님)")
            except LoginError:
                raise
            except Exception as e:
                self.logger.warning(f"URL 확인 중 오류 (계속 진행): {e}")
                # 오류가 발생해도 URL을 다시 확인
                try:
                    final_url = page.url
                    if "accounts/login" in final_url or "/login" in final_url:
                        self.logger.error("로그인 페이지로 리다이렉트되었습니다.")
                        raise LoginError("로그인에 실패했습니다. 로그인 페이지로 리다이렉트되었습니다.")
                except LoginError:
                    raise
                except Exception:
                    pass  # 최종 확인도 실패하면 계속 진행

            # 로그인 상태 최종 확인 (views_tracker.py와 동일한 로직)
            try:
                final_url = page.url
                if "accounts/login" in final_url or "/login" in final_url:
                    self.logger.error("로그인 후에도 로그인 페이지에 있습니다. 로그인에 실패했습니다.")
                    raise LoginError("로그인에 실패했습니다. 로그인 페이지에 여전히 있습니다.")
                else:
                    self.logger.info("로그인 성공 확인 완료")
            except LoginError:
                raise
            except Exception as e:
                self.logger.warning(f"로그인 상태 확인 실패: {e}")

            # 홈 탭으로 이동 (20초 대기 후)
            try:
                self.logger.info("홈 탭으로 이동 시도 중...")
                self._navigate_to_home_tab(page)
                self.logger.info("홈 탭 이동 완료")
            except Exception as e:
                self.logger.warning(f"홈 탭 이동 실패 (계속 진행): {e}")

            # 홈 탭 이동 후 팝업 처리
            self._handle_post_login_popup(page)

            # 릴스 탭으로 이동 (수집은 main.py에서 별도로 호출)
            try:
                self.logger.info("릴스 탭으로 이동 시도 중...")
                self.navigate_to_reels_tab()
                self.logger.info("릴스 탭 이동 완료")
            except Exception as e:
                self.logger.warning(f"릴스 탭 이동 실패: {e}")

            self.username = username
            self.password = password

            # 6단계: 로그인 성공 후 세션 저장
            try:
                if self.browser_manager and self.browser_manager.context:
                    session_data = self.session_manager.extract_session_data(
                        self.browser_manager.context
                    )
                    self.session_manager.save_session(
                        account_id=account_id,
                        cookies=session_data["cookies"],
                        user_agent=session_data["user_agent"],
                    )
                    self.logger.info("✅ 세션 저장 완료")
            except Exception as e:
                self.logger.warning(f"세션 저장 실패 (작업은 계속 진행): {e}")

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

    def _navigate_to_home_tab(self, page: Page) -> None:
        """
        홈 탭으로 이동

        Args:
            page: Playwright Page 객체
        """
        try:
            self.logger.info("홈 탭 찾는 중...")

            # 홈 탭 셀렉터
            home_tab_selectors = [
                'a[href="/"]',
                'a[href*="/"]:has-text("Home")',
                'a[href*="/"]:has-text("홈")',
                'nav a[href="/"]',
                'nav a[href*="/"]',
            ]

            home_tab = wait_for_element(
                page, home_tab_selectors, timeout=10000, description="홈 탭"
            )

            if not home_tab:
                # 홈으로 직접 이동
                self.logger.info("홈 탭을 찾을 수 없어 URL로 직접 이동합니다...")
                page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=10000)
                page.wait_for_load_state("domcontentloaded")
                random_delay(1.0, 2.0)
                return

            # 홈 탭 클릭
            self.logger.info("홈 탭 클릭 중...")
            home_tab.click()

            # 페이지 로드 대기
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                self.logger.debug("홈 탭 로드 대기 실패 (계속 진행)")

            random_delay(1.0, 2.0)

            # URL 확인
            try:
                current_url = page.url
                if "/" in current_url and "accounts" not in current_url:
                    self.logger.info(f"홈 탭으로 이동 완료: {current_url}")
                else:
                    self.logger.warning(f"홈 탭 이동 후 URL 확인 필요: {current_url}")
            except Exception:
                pass

        except Exception as e:
            self.logger.warning(f"홈 탭 이동 실패 (계속 진행): {e}")
            # 실패해도 계속 진행

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

            # 직접 URL 이동 (탭 요소 탐색/클릭 불필요 → ~13초 절감)
            self.logger.info("릴스 페이지 직접 이동 중...")
            try:
                page.goto(
                    "https://www.instagram.com/reels/",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
            except Exception:
                self.logger.debug("domcontentloaded 대기 실패 (계속 진행)")

            current_url = page.url
            if "accounts/login" in current_url or "/login" in current_url:
                raise ScrapingError(f"릴스 탭 이동 중 로그인 페이지로 리다이렉트됨 (세션 만료): {current_url}")
            if "/reels" in current_url:
                self.logger.info(f"릴스 탭으로 이동 완료: {current_url}")
                return True
            else:
                self.logger.warning(f"릴스 탭 이동 후 URL 확인 필요: {current_url}")
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
            time.sleep(1)  # 초기 로딩 대기 (비디오 차단으로 단축)

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
            time.sleep(1)
            # 일부 환경에서 페이지가 확대된 것처럼 보이면서(줌/레이아웃) 액션바가 화면 밖으로 밀리는 경우가 있음.
            # - 브라우저 줌을 리셋(Meta+0) 시도
            # - DOM zoom을 낮춰(80%) 액션바가 화면 안으로 들어오게 유도
            try:
                page.keyboard.press("Meta+0")
            except Exception:
                pass
            try:
                page.evaluate('document.documentElement.style.zoom = "80%";')
                self.logger.info('페이지 줌 보정 적용: document zoom=80%')
            except Exception:
                pass
            self.logger.info("릴스 페이지 로딩 완료")
        except Exception as e:
            self.logger.warning(f"릴스 페이지 로딩 대기 중 오류 (계속 진행): {e}")

    def _get_current_reel_instancekey(self, page: Page) -> str | None:
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
            closest_idx: int | None = None
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

    def _extract_current_reel_data(self, page: Page) -> ReelData | None:
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
                views=None,
                author=None,
                creator_profile_image=None,
                title=None,
                music=None,
                link=None,
                posted_date=None,
            )

            # 현재 릴스를 대표하는 컨테이너 결정
            # 1순위: 화면 중앙에 가장 가까운 video 기준
            root = page  # 기본값 (최악의 경우 페이지 전체 검색)
            current_video = None  # 이후 썸네일/좋아요/댓글 추출에도 재사용
            try:
                current_video = self._get_current_reel_video(page)
                if current_video:
                    try:
                        # reels.txt 구조처럼 video와 액션바(좋아요/댓글)는 같은 카드 상위 div에 공존하므로
                        # video+좋아요+댓글을 동시에 포함하는 가장 가까운 ancestor div를 우선 선택한다.
                        container = current_video.locator(
                            'xpath=ancestor::div['
                            './/video'
                            ' and '
                            './/svg[contains(@aria-label,"좋아요") or contains(@aria-label,"Like") or contains(@aria-label,"Unlike")]'
                            ' and '
                            './/svg[contains(@aria-label,"댓글") or contains(@aria-label,"Comment")]'
                            '][1]'
                        )
                        if container.count() > 0:
                            root = container.first
                            self.logger.info("현재 릴스 컨테이너를 video+좋아요+댓글 기준으로 선택")
                        else:
                            # 2순위: 카드 컨테이너 클래스(x1qjc9v5) 기반
                            card = current_video.locator(
                                'xpath=ancestor::div[contains(@class,"x1qjc9v5")][1]'
                            )
                            if card.count() > 0:
                                root = card.first
                                self.logger.info("현재 릴스 컨테이너를 카드(x1qjc9v5) 기준으로 선택")
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

            # 좋아요/댓글 수 추출 (reels.txt 구조 기준)
            # - 같은 카드 내부의 role=button 블록에서 카운트(span.x1vvkbs)를 읽는다.
            # - 지금 로그처럼 "버튼을 찾지 못함"이 계속 뜨는 이유는 stats_root에 액션바가 포함되지 않아서임.
            #   그래서 stats_root를 더 큰 컨테이너로 잡고, 필요하면 상위로 확장하며 찾는다.
            stats_root = root
            try:
                if current_video:
                    card = current_video.locator(
                        'xpath=ancestor::div[contains(@class,"x1qjc9v5")][1]'
                    )
                    if card.count() > 0:
                        stats_root = card.first
            except Exception:
                stats_root = root

            def _find_button_scope_with_fallback(scope, xpath_expr: str, label: str):
                """scope에서 버튼을 못 찾으면 상위 div로 확장하며 최대 5번 재시도."""
                current_scope = scope
                for attempt in range(5):
                    btn = current_scope.locator(xpath_expr).first
                    try:
                        if btn.is_visible(timeout=50):
                            return btn, attempt
                    except Exception:
                        pass
                    # 상위로 확장
                    parent = current_scope.locator("xpath=ancestor::div[1]")
                    if parent.count() == 0:
                        break
                    current_scope = parent.first
                self.logger.info(f"{label}: 버튼을 찾지 못함 (scope_expand_attempts=5)")
                return None, 5

            def _parse_like_count(text: str) -> int | None:
                t = (text or "").strip().replace(" ", "")
                if not t:
                    return None
                if not re.match(r"^[\d.,만천억]+$", t):
                    return None
                try:
                    if "만" in t:
                        m = re.search(r"([\d.]+)", t)
                        return int(float(m.group(1)) * 10000) if m else None
                    if "천" in t:
                        m = re.search(r"([\d.]+)", t)
                        return int(float(m.group(1)) * 1000) if m else None
                    digits = t.replace(",", "").replace(".", "")
                    return int(digits) if digits.isdigit() else None
                except Exception:
                    return None

            def _extract_count_from_button(button, kind: str) -> tuple[int | None, int, int]:
                try:
                    texts = button.locator("span.html-span.x1vvkbs, span.x1vvkbs").evaluate_all(
                        "els => els.slice(0, 80).map(el => el.textContent || '')"
                    )
                except Exception:
                    texts = []
                if not texts:
                    try:
                        texts = button.locator("span").evaluate_all(
                            "els => els.slice(0, 80).map(el => el.textContent || '')"
                        )
                    except Exception:
                        texts = []

                total = len(texts)
                scanned = 0
                for txt in texts:
                    scanned += 1
                    txt = (txt or "").strip()
                    if not txt:
                        continue
                    if kind == "likes":
                        v = _parse_like_count(txt)
                        if v is not None and v >= 0:
                            return v, scanned, total
                    else:
                        t2 = txt.replace(" ", "")
                        if re.match(r"^[\d,]+$", t2):
                            digits = t2.replace(",", "").replace(".", "").strip()
                            if digits.isdigit():
                                return int(digits), scanned, total
                return None, scanned, total

            def _find_action_button_by_proximity(
                button_xpath: str, label: str, svg_xpath: str | None = None
            ):
                """
                reels 페이지에서 액션바(좋아요/댓글)가 video 카드 밖(오른쪽 컬럼)에 렌더링되는 레이아웃이 있음.
                그 경우 카드 내부 탐색은 실패하므로, 현재 video의 위치를 기준으로 '오른쪽에 가장 가까운' 아이콘을 찾는다.
                """
                if not current_video:
                    return None
                try:
                    vrect = current_video.evaluate(
                        "el => { const r = el.getBoundingClientRect(); "
                        "return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height }; }"
                    )
                    vcy = vrect["top"] + vrect["height"] / 2

                    # 1) role=button/button 자체의 aria-label 기준
                    candidates = page.locator(button_xpath)
                    cnt = candidates.count()
                    # 디버그: svg 총 개수도 같이 남김 (화면/레イ아웃 확인용)
                    try:
                        total_svgs = page.locator("svg").count()
                    except Exception:
                        total_svgs = -1
                    self.logger.info(f"{label}: candidate_buttons={cnt}, total_svgs={total_svgs}")

                    # 2) 버튼 aria-label이 없으면 svg(title/aria-label)로 찾고, ancestor button으로 변환
                    svg_candidates = None
                    svg_cnt = 0
                    if cnt == 0 and svg_xpath:
                        svg_candidates = page.locator(svg_xpath)
                        svg_cnt = svg_candidates.count()
                        self.logger.info(f"{label}: candidate_svgs={svg_cnt} (svg_xpath fallback)")

                    best_idx = None
                    best_score = float("inf")

                    # offscreen(화면 밖)일 수 있으니 is_visible로 거르지 않는다.
                    source = candidates
                    source_cnt = cnt
                    source_kind = "button"
                    if cnt == 0 and svg_candidates is not None and svg_cnt > 0:
                        source = svg_candidates
                        source_cnt = svg_cnt
                        source_kind = "svg"

                    if source_cnt == 0:
                        self.logger.info(f"{label}: proximity 후보 없음")
                        return None

                    # 단일 evaluate_all로 모든 rect 한 번에 수집 (개별 evaluate 80회 → 1회)
                    try:
                        all_rects = source.evaluate_all(
                            "els => els.slice(0, 80).map((el, i) => {"
                            "  const r = el.getBoundingClientRect();"
                            "  return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height, idx: i };"
                            "})"
                        )
                    except Exception:
                        all_rects = []

                    for rect in all_rects:
                        if rect["bottom"] < vrect["top"] - 250 or rect["top"] > vrect["bottom"] + 250:
                            continue
                        icy = rect["top"] + rect["height"] / 2
                        dy = abs(icy - vcy)
                        dx = abs(rect["left"] - vrect["right"])
                        score = dy + dx * 0.2
                        if score < best_score:
                            best_score = score
                            best_idx = rect["idx"]

                    if best_idx is None:
                        self.logger.info(f"{label}: proximity 후보 없음 (video_right={vrect['right']:.1f})")
                        return None

                    self.logger.info(f"{label}: proximity 선택 index={best_idx}, score={best_score:.1f}")
                    chosen = source.nth(best_idx)
                    if source_kind == "svg":
                        btn = chosen.locator(
                            'xpath=ancestor::*[@role="button" or self::button][1]'
                        )
                        if btn.count() > 0:
                            return btn.first
                        return None
                    return chosen
                except Exception as e:
                    self.logger.warning(f"{label}: proximity 탐색 실패: {e}")
                    return None

            # 좋아요
            try:
                like_xpath = (
                    'xpath=.//*[@role="button" or self::button]'
                    '[.//svg[contains(@aria-label,"좋아요") or contains(@aria-label,"Like") or contains(@aria-label,"Unlike")]][1]'
                )
                like_btn, expand_attempts = _find_button_scope_with_fallback(
                    stats_root, like_xpath, "좋아요"
                )
                if like_btn:
                    self.logger.info(f"좋아요: 버튼 발견 (scope_expand_attempts={expand_attempts})")
                    v, scanned, total = _extract_count_from_button(like_btn, "likes")
                    reel_data.likes = v
                    self.logger.info(
                        f"좋아요 수 수집: value={reel_data.likes}, scanned_spans={scanned}, candidate_spans={total}"
                    )
                else:
                    # 공간기반 fallback (카드 밖 레이아웃 대응)
                    like_btn2 = _find_action_button_by_proximity(
                        'xpath=//*[@role="button" or self::button][contains(@aria-label,"좋아요") or contains(@aria-label,"Like") or contains(@aria-label,"Unlike")]',
                        "좋아요(fallback)",
                        'xpath=//svg[contains(@aria-label,"좋아요") or contains(@aria-label,"Like") or contains(@aria-label,"Unlike") or .//title[contains(., "좋아요") or contains(., "Like") or contains(., "Unlike")]]',
                    )
                    if like_btn2:
                        try:
                            like_btn2.scroll_into_view_if_needed(timeout=1000)
                        except Exception:
                            pass
                        v, scanned, total = _extract_count_from_button(like_btn2, "likes")
                        reel_data.likes = v
                        self.logger.info(
                            f"좋아요 수 수집(fallback): value={reel_data.likes}, scanned_spans={scanned}, candidate_spans={total}"
                        )
            except Exception as e:
                self.logger.warning(f"좋아요 수 수집 실패: {e}")

            # 댓글
            try:
                comment_xpath = (
                    'xpath=.//*[@role="button" or self::button]'
                    '[.//svg[contains(@aria-label,"댓글") or contains(@aria-label,"Comment")]][1]'
                )
                comment_btn, expand_attempts = _find_button_scope_with_fallback(
                    stats_root, comment_xpath, "댓글"
                )
                if comment_btn:
                    self.logger.info(f"댓글: 버튼 발견 (scope_expand_attempts={expand_attempts})")
                    v, scanned, total = _extract_count_from_button(comment_btn, "comments")
                    reel_data.comments = v
                    self.logger.info(
                        f"댓글 수 수집: value={reel_data.comments}, scanned_spans={scanned}, candidate_spans={total}"
                    )
                else:
                    comment_btn2 = _find_action_button_by_proximity(
                        'xpath=//*[@role="button" or self::button][contains(@aria-label,"댓글") or contains(@aria-label,"Comment")]',
                        "댓글(fallback)",
                        'xpath=//svg[contains(@aria-label,"댓글") or contains(@aria-label,"Comment") or .//title[contains(., "댓글") or contains(., "Comment")]]',
                    )
                    if comment_btn2:
                        try:
                            comment_btn2.scroll_into_view_if_needed(timeout=1000)
                        except Exception:
                            pass
                        v, scanned, total = _extract_count_from_button(comment_btn2, "comments")
                        reel_data.comments = v
                        self.logger.info(
                            f"댓글 수 수집(fallback): value={reel_data.comments}, scanned_spans={scanned}, candidate_spans={total}"
                        )
            except Exception as e:
                self.logger.warning(f"댓글 수 수집 실패: {e}")

            # 최종 fallback: 라벨(aria-label/title)이 전혀 안 잡히는 레이아웃 대응
            # - video 오른쪽에 있는 버튼 "세로열"을 좌표로 클러스터링
            # - 그 중 숫자(count)가 붙은 버튼 2개를 (좋아요, 댓글)로 확정
            try:
                if current_video and (reel_data.likes is None or reel_data.comments is None):
                    vrect = current_video.evaluate(
                        "el => { const r = el.getBoundingClientRect(); "
                        "return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height }; }"
                    )
                    vcy = vrect["top"] + vrect["height"] / 2

                    btns = page.locator('xpath=//*[@role="button" or self::button][.//svg]')
                    btn_cnt = btns.count()
                    scan_n = min(120, btn_cnt)

                    # 단일 evaluate_all로 모든 rect 한 번에 수집 (개별 evaluate 120회 → 1회)
                    try:
                        all_btn_rects = btns.evaluate_all(
                            f"els => els.slice(0, {scan_n}).map((el, i) => {{"
                            "  const r = el.getBoundingClientRect();"
                            "  return { top: r.top, bottom: r.bottom, left: r.left, height: r.height, width: r.width, idx: i };"
                            "})"
                        )
                    except Exception:
                        all_btn_rects = []

                    clusters: dict[int, list[tuple[float, int]]] = {}
                    for rect in all_btn_rects:
                        try:
                            if rect["bottom"] < vrect["top"] - 350 or rect["top"] > vrect["bottom"] + 350:
                                continue
                            if rect["left"] < vrect["right"] - 50:
                                continue
                            x_bucket = int(round(rect["left"] / 10.0) * 10)
                            clusters.setdefault(x_bucket, []).append((rect["top"], rect["idx"]))
                        except Exception:
                            continue

                    if not clusters:
                        self.logger.info("counts(geometry_fallback): 후보 버튼 클러스터 없음")
                    else:
                        best_bucket = max(clusters.keys(), key=lambda k: len(clusters[k]))
                        ordered = sorted(clusters[best_bucket], key=lambda t: t[0])

                        # ordered[:8]의 rect는 all_btn_rects에서 이미 가져왔으므로 재사용
                        rect_by_idx = {r["idx"]: r for r in all_btn_rects}
                        values: list[int] = []
                        for _, idx in ordered[:8]:
                            try:
                                rect = rect_by_idx.get(idx)
                                if rect is None:
                                    continue
                                bcy = rect["top"] + rect["height"] / 2
                                if abs(bcy - vcy) > 700:
                                    continue

                                b = btns.nth(idx)
                                like_v, _, _ = _extract_count_from_button(b, "likes")
                                com_v, _, _ = _extract_count_from_button(b, "comments")
                                if like_v is not None:
                                    values.append(like_v)
                                elif com_v is not None:
                                    values.append(com_v)
                            except Exception:
                                continue

                        # 일반적으로 위에서부터 [좋아요, 댓글] 순서로 숫자가 존재
                        if len(values) >= 2:
                            if reel_data.likes is None:
                                reel_data.likes = values[0]
                            if reel_data.comments is None:
                                reel_data.comments = values[1]

                        self.logger.info(
                            f"counts(geometry_fallback): x_bucket={best_bucket}, "
                            f"cluster_size={len(ordered)}, extracted_nums={values[:4]}, "
                            f"likes={reel_data.likes}, comments={reel_data.comments}"
                        )
            except Exception as e:
                self.logger.warning(f"counts(geometry_fallback) 실패: {e}")

            # 크리에이터 이름 추출
            # 시스템 경로로 혼동될 수 있는 pathname 목록
            _SYSTEM_PATHS = frozenset({
                'explore', 'reels', 'reel', 'stories', 'accounts',
                'p', 'tv', 'direct', 'login', 'signup',
            })
            try:
                # 방법 0: /username/reels/ href 기반 (로케일 독립적 — 가장 안정적)
                try:
                    creator_links = root.locator('a[href*="/reels/"]').all()
                    for link in creator_links[:10]:
                        try:
                            href = link.get_attribute("href") or ""
                            if href.startswith("/") and "/reels" in href:
                                m = re.search(r'^/([^/]+)/reels', href)
                                if m:
                                    candidate = m.group(1)
                                    if candidate not in _SYSTEM_PATHS and len(candidate) > 0:
                                        reel_data.author = candidate
                                        self.logger.info(f"크리에이터 (href): {reel_data.author}")
                                        break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 방법 1: aria-label 기반 (한국어/일본어/영어 로케일 지원)
                if not reel_data.author:
                    try:
                        _aria_selectors = [
                            'a[aria-label*="님의 릴스"]',   # 한국어
                            'a[aria-label*="のリール"]',     # 일본어
                            "a[aria-label*=\"'s reels\"]",  # 영어
                            'a[aria-label*=" reels"]',      # 영어 (다른 패턴)
                        ]
                        for sel in _aria_selectors:
                            try:
                                creator_link = root.locator(sel).first
                                if creator_link.is_visible(timeout=300):
                                    href = creator_link.get_attribute("href") or ""
                                    if href.startswith("/") and "/reels" in href:
                                        m = re.search(r'^/([^/]+)/reels', href)
                                        if m and m.group(1) not in _SYSTEM_PATHS:
                                            reel_data.author = m.group(1)
                                            self.logger.info(f"크리에이터 (aria-label href): {reel_data.author}")
                                            break
                                    else:
                                        span = creator_link.locator('span[dir="auto"]').first
                                        if span.is_visible(timeout=300):
                                            txt = (span.text_content() or "").strip()
                                            if txt and len(txt) < 50:
                                                reel_data.author = txt
                                                self.logger.info(f"크리에이터 (aria-label 텍스트): {reel_data.author}")
                                                break
                            except Exception:
                                continue
                        if reel_data.author:
                            pass  # break 역할 (for-else 없이)
                    except Exception:
                        pass

                # 방법 2: 프로필 이미지 근처 span[dir="auto"] (한국어/일본어/영어 alt text)
                if not reel_data.author:
                    try:
                        profile_imgs = root.locator(
                            'img[alt*="프로필 사진"], img[alt*="님의 프로필 사진"],'
                            ' img[alt*="プロフィール写真"], img[alt*="profile picture"]'
                        ).all()
                        for img in profile_imgs[:5]:
                            try:
                                parent_link = img.locator('xpath=ancestor::a[1]')
                                if parent_link.count() > 0:
                                    author_span = parent_link.locator('span[dir="auto"]').first
                                    if author_span.is_visible(timeout=300):
                                        author_text = (author_span.text_content() or "").strip()
                                        if author_text and len(author_text) < 50:
                                            reel_data.author = author_text
                                            self.logger.info(f"크리에이터 (프로필 이미지): {reel_data.author}")
                                            break
                            except Exception:
                                continue
                    except Exception:
                        pass

            except Exception as e:
                self.logger.debug(f"크리에이터 이름 추출 실패: {e}")

            # 크리에이터 프로필 사진 추출
            try:
                # 방법 0: /username/reels/ href 내부의 프로필 CDN 이미지 (로케일 독립적)
                try:
                    creator_links = root.locator('a[href*="/reels/"]').all()
                    for link in creator_links[:10]:
                        try:
                            href = link.get_attribute("href") or ""
                            if href.startswith("/") and "/reels" in href:
                                m = re.search(r'^/([^/]+)/reels', href)
                                if m and m.group(1) not in _SYSTEM_PATHS:
                                    img = link.locator('img[src*="cdninstagram"]').first
                                    if img.is_visible(timeout=300):
                                        src = img.get_attribute("src")
                                        # 프로필 이미지는 CDN 경로에 2885-19 또는 t51.2885 포함
                                        if src and "cdninstagram" in src:
                                            reel_data.creator_profile_image = src
                                            self.logger.info(
                                                f"프로필 사진 (href): {reel_data.creator_profile_image[:50]}..."
                                            )
                                            break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 방법 1: alt text 기반 (한국어/일본어/영어 로케일 지원)
                if not reel_data.creator_profile_image:
                    try:
                        profile_img = root.locator(
                            'img[alt*="님의 프로필 사진"], img[alt*="프로필 사진"],'
                            ' img[alt*="プロフィール写真"], img[alt*="のプロフィール写真"],'
                            ' img[alt*="profile picture"]'
                        ).first
                        if profile_img.is_visible(timeout=500):
                            img_src = profile_img.get_attribute("src")
                            if img_src and "cdninstagram" in img_src:
                                reel_data.creator_profile_image = img_src
                                self.logger.info(f"프로필 사진 (alt): {reel_data.creator_profile_image[:50]}...")
                    except Exception:
                        pass

                # 방법 2: aria-label 기반 링크 내부 이미지
                if not reel_data.creator_profile_image:
                    try:
                        _aria_selectors = [
                            'a[aria-label*="님의 릴스"]',
                            'a[aria-label*="のリール"]',
                            "a[aria-label*=\"'s reels\"]",
                        ]
                        for sel in _aria_selectors:
                            try:
                                creator_link = root.locator(sel).first
                                if creator_link.is_visible(timeout=300):
                                    img = creator_link.locator('img[src*="cdninstagram"]').first
                                    if img.is_visible(timeout=300):
                                        src = img.get_attribute("src")
                                        if src:
                                            reel_data.creator_profile_image = src
                                            self.logger.info(
                                                f"프로필 사진 (aria-label): {reel_data.creator_profile_image[:50]}..."
                                            )
                                            break
                            except Exception:
                                continue
                    except Exception:
                        pass

            except Exception as e:
                self.logger.debug(f"프로필 사진 추출 실패: {e}")

            # 제목 추출
            # 캡션 span: x6ikm8r x10wlt62 xuxw1ft (xlyipyv 없음)
            # 음악 span: x6ikm8r x10wlt62 xlyipyv xuxw1ft (xlyipyv 있음) → :not(.xlyipyv)로 제외
            try:
                # 방법 1: root 범위에서 캡션 span 직접 선택 (음악 span 제외)
                try:
                    caption_spans = root.locator('span.x6ikm8r.x10wlt62.xuxw1ft:not(.xlyipyv)').all()
                    for span in caption_spans[:10]:
                        try:
                            title_text = (span.text_content() or "").strip()
                            if title_text and len(title_text) > 1:
                                reel_data.title = title_text
                                self.logger.info(f"제목(캡션): {title_text[:60]!r}")
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 방법 2: div[dir="auto"] > span 구조로 탐색 (방법 1 실패 시)
                if not reel_data.title:
                    try:
                        divs = root.locator('div[dir="auto"]').all()
                        for div in divs[:20]:
                            try:
                                # 오디오 링크 내부 div는 건너뜀
                                in_audio = div.evaluate("el => !!el.closest('a[href*=\"/reels/audio/\"]')")
                                if in_audio:
                                    continue
                                text = (div.text_content() or "").strip()
                                if text and len(text) > 1:
                                    reel_data.title = text
                                    self.logger.info(f"제목(div[dir=auto]): {text[:60]!r}")
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

            # 네트워크 응답 가로채기 방식: Global Cache 전략
            # - 모든 패킷의 릴스 데이터를 캐시에 저장
            # - URL에서 shortcode 추출 후 캐시에서 조회
            # - 타이밍 문제 해결 (패킷이 언제 와도 캐시에 저장됨)
            try:
                # 1. 글로벌 네트워크 리스너 등록 (한 번만)
                if not self._network_listener_registered and self.browser_manager:
                    page = self.browser_manager.get_page()
                    if page:
                        self._register_global_network_listener(page)
                        self._network_listener_registered = True

                # 2. 현재 URL에서 shortcode 추출
                target_code: str | None = None
                if reel_data.link:
                    match = re.search(r"/reels?/([^/?]+)", str(reel_data.link))
                    if match:
                        target_code = match.group(1)

                # 3. 캐시에서 데이터 조회 (Retry 로직 포함)
                needs_reel_id = reel_data.link and "/reels/" in reel_data.link and reel_data.link.rstrip("/").endswith("/reels")
                needs_counts = reel_data.likes is None or reel_data.comments is None

                if needs_counts or needs_reel_id:
                    cached_data = None
                    # 최대 10번 시도 (5초)
                    for attempt in range(10):
                        if target_code and target_code in self._reels_cache:
                            cached_data = self._reels_cache[target_code]
                            self.logger.debug(f"💾 캐시에서 데이터 조회 성공: {target_code} (시도 {attempt + 1})")
                            break
                        if attempt < 9:
                            time.sleep(0.5)  # 0.5초 대기

                    if cached_data:
                        if reel_data.likes is None and cached_data.get("likes") is not None:
                            reel_data.likes = cached_data["likes"]
                        if reel_data.comments is None and cached_data.get("comments") is not None:
                            reel_data.comments = cached_data["comments"]
                        if reel_data.views is None and cached_data.get("views") is not None:
                            reel_data.views = cached_data["views"]
                        if reel_data.posted_date is None and cached_data.get("posted_date") is not None:
                            reel_data.posted_date = cached_data["posted_date"]
                        if needs_reel_id and cached_data.get("code"):
                            reel_data.link = f"https://www.instagram.com/reels/{cached_data['code']}/"
                            self.logger.info(f"링크 업데이트 (캐시에서 reel_id 추출): {reel_data.link}")
                        # 네트워크 캐시 썸네일은 shortcode와 1:1 대응이라 DOM poster보다 정확
                        # DOM video.poster는 슬롯 재사용으로 이전 릴스 값이 남을 수 있으므로
                        # 캐시에 값이 있으면 항상 덮어씀
                        if cached_data.get("thumbnail"):
                            reel_data.thumbnail = cached_data["thumbnail"]
                            self.logger.info(f"썸네일 (캐시 우선): {reel_data.thumbnail[:50]}...")
                        if reel_data.author is None and cached_data.get("author"):
                            reel_data.author = cached_data["author"]
                            self.logger.info(f"크리에이터 (캐시 fallback): {reel_data.author}")
                        if reel_data.creator_profile_image is None and cached_data.get("profile_image"):
                            reel_data.creator_profile_image = cached_data["profile_image"]
                            self.logger.info(f"프로필 사진 (캐시 fallback): {reel_data.creator_profile_image[:50]}...")

                        self.logger.info(
                            f"counts(cache): "
                            f"likes={reel_data.likes}, comments={reel_data.comments}, "
                            f"views={reel_data.views}, posted_date={reel_data.posted_date}, "
                            f"link={reel_data.link}"
                        )
                    else:
                        self.logger.warning(f"⚠️ 캐시에서 데이터를 찾지 못함 (code={target_code}, 캐시 크기={len(self._reels_cache)})")

            except Exception as e:
                self.logger.warning(f"counts(cache) 실패: {e}")

            self.logger.info("릴스 정보 수집 완료")
            return reel_data

        except Exception as e:
            self.logger.error(f"릴스 정보 수집 중 오류: {e}")
            return None

    def _register_global_network_listener(self, page: Page) -> None:
        """
        글로벌 네트워크 리스너 등록
        모든 패킷의 릴스 데이터를 캐시에 저장
        """
        def handle_response(response) -> None:
            url = response.url
            # 인스타그램 API 요청 URL 패턴
            if not ("graphql" in url or "/api/v1/feed/" in url or "/api/v1/media/" in url or "/info/" in url or "web_info" in url):
                return

            try:
                json_body = response.json()

                # 원본 네트워크 데이터 저장 (디버깅용)
                try:
                    import json as json_module
                    debug_dir = Path("output/debug/network_responses")
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    import time as time_module
                    timestamp = time_module.strftime("%Y%m%d_%H%M%S_%f", time_module.localtime())
                    url_safe = url.replace("https://", "").replace("http://", "").replace("/", "_").replace("?", "_").replace("&", "_")[:100]
                    filename = f"{timestamp}_{url_safe}.json"
                    filepath = debug_dir / filename
                    with open(filepath, "w", encoding="utf-8") as f:
                        json_module.dump({
                            "url": url,
                            "timestamp": timestamp,
                            "data": json_body
                        }, f, indent=2, ensure_ascii=False)
                    self.logger.debug(f"💾 네트워크 응답 저장: {filepath}")
                except Exception:
                    pass

                # 캐시에 저장
                self._parse_and_cache_reels(json_body)
            except Exception:
                pass

        page.on("response", handle_response)
        self.logger.info("✅ 글로벌 네트워크 리스너 등록 완료")

    def _parse_and_cache_reels(self, json_data: dict) -> None:
        """
        네트워크 패킷에서 릴스 정보를 추출하여 캐시에 저장 (구조 변화 대응 강화판)

        Args:
            json_data: 네트워크 응답 JSON 데이터
        """
        try:
            data_inner = json_data.get("data", {})
            if not data_inner:
                return

            # 인스타그램이 데이터를 담는 다양한 키 패턴들
            possible_roots = [
                "xdt_api__v1__feed__timeline__connection",      # 메인 피드
                "xdt_api__v1__clips__home__connection",         # 릴스 탭
                "xdt_api__v1__clips__home__connection_v2",      # 릴스 탭 (신규 버전 - 현재 로그에서 발견됨)
                "xdt_api__v1__media__shortcode__media",         # 단일 게시물 조회
            ]

            edges = []

            # 1. 알려진 루트 키 탐색
            for root in possible_roots:
                if root in data_inner:
                    container = data_inner[root]
                    # 리스트 형태(edges)로 들어오는 경우
                    if "edges" in container:
                        edges.extend(container["edges"])
                    # 단일 객체로 들어오는 경우 (shortcode_media 등)
                    elif "shortcode" in container or "code" in container:
                        edges.append({"node": {"media": container}})

            # 2. 만약 알려진 키가 없으면, 'edges'를 가진 모든 하위 딕셔너리를 검색 (비상 대책)
            if not edges:
                for _key, value in data_inner.items():
                    if isinstance(value, dict) and "edges" in value:
                        edges.extend(value["edges"])

            # 3. 데이터 추출 및 캐싱
            for edge in edges:
                # node 밑에 media가 있을 수도, node가 바로 media일 수도 있음
                node = edge.get("node", {})
                media = node.get("media") or node  # media 키가 없으면 node 자체를 사용

                # 광고나 잘못된 데이터 제외
                if not media or ("code" not in media and "shortcode" not in media):
                    continue

                shortcode = media.get("code") or media.get("shortcode")

                if shortcode:
                    # 좋아요/댓글 수 추출 (없는 경우 None 처리)
                    like_count = media.get("like_count")
                    if like_count is None:  # 구조가 다를 수 있으므로 한번 더 체크
                        like_count = media.get("edge_media_preview_like", {}).get("count")
                    if like_count is None:
                        like_count = media.get("edge_media_to_like", {}).get("count")

                    comment_count = media.get("comment_count")
                    if comment_count is None:
                        comment_count = media.get("edge_media_to_comment", {}).get("count")

                    # 조회수 추출
                    views = media.get("video_view_count") or media.get("view_count") or media.get("play_count")
                    if views is None:
                        views = media.get("edge_media_preview", {}).get("video_view_count")

                    # 게시일자 추출
                    posted_date = None
                    if "taken_at_timestamp" in media and isinstance(
                        media["taken_at_timestamp"], int | float
                    ):
                        import datetime
                        posted_date = datetime.datetime.fromtimestamp(
                            media["taken_at_timestamp"]
                        ).isoformat()
                    elif "taken_at" in media and isinstance(media["taken_at"], int | float):
                        import datetime
                        posted_date = datetime.datetime.fromtimestamp(
                            media["taken_at"]
                        ).isoformat()

                    # 썸네일 추출 — 여러 경로 시도 (API 버전·구조에 따라 위치가 다름)
                    thumbnail_url = None
                    try:
                        # image_versions2 (가장 일반적인 GraphQL 형식)
                        candidates = media.get("image_versions2", {}).get("candidates", [])
                        if candidates:
                            # 가장 큰 해상도(첫 번째)를 사용
                            thumbnail_url = candidates[0].get("url")

                        # carousel_media[0].image_versions2 (캐러셀 첫 장)
                        if not thumbnail_url:
                            carousel = media.get("carousel_media", [])
                            if carousel:
                                sub = carousel[0].get("image_versions2", {}).get("candidates", [])
                                if sub:
                                    thumbnail_url = sub[0].get("url")

                        # thumbnail_resources (구형 API)
                        if not thumbnail_url:
                            resources = media.get("thumbnail_resources", [])
                            if resources:
                                thumbnail_url = resources[-1].get("src")

                        # 단순 필드 fallback
                        if not thumbnail_url:
                            thumbnail_url = (
                                media.get("thumbnail_src")
                                or media.get("display_url")
                                or media.get("cover_frame_url")
                            )
                    except Exception:
                        pass

                    # author 추출 (user.username)
                    cached_author = None
                    try:
                        user = media.get("user") or media.get("owner") or {}
                        cached_author = user.get("username") or user.get("screen_name")
                    except Exception:
                        pass

                    # profile image 추출 (user.profile_pic_url)
                    cached_profile_image = None
                    try:
                        user = media.get("user") or media.get("owner") or {}
                        cached_profile_image = (
                            user.get("profile_pic_url")
                            or user.get("profile_picture_url")
                        )
                    except Exception:
                        pass

                    # 캐시에 저장 (이미 있으면 덮어쓰기)
                    cached_item = {
                        "code": shortcode,
                        "likes": like_count,
                        "comments": comment_count,
                        "views": views,
                        "posted_date": posted_date,
                        "thumbnail": thumbnail_url,
                        "author": cached_author,
                        "profile_image": cached_profile_image,
                        "cached_at": time.time()
                    }
                    self._reels_cache[shortcode] = cached_item
                    self.logger.debug(
                        f"💾 캐시 저장: {shortcode} -> "
                        f"L:{like_count}, C:{comment_count}, V:{views}, "
                        f"thumb={'O' if thumbnail_url else 'X'}, "
                        f"author={cached_author or '-'}"
                    )
        except Exception as e:
            self.logger.debug(f"캐시 파싱 실패: {e}")

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
                    time.sleep(2)  # 대기 시간 최적화

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
                time.sleep(2)  # 대기 시간 최적화

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

    def _print_reel_summary(self, reel_data: ReelData, index: int) -> None:
        """
        수집된 릴스 데이터를 보기 좋게 출력

        Args:
            reel_data: 수집된 릴스 데이터
            index: 수집 순서 (1부터 시작)
        """
        try:
            print("\n" + "=" * 80)
            print(f"📹 릴스 #{index} 수집 완료")
            print("=" * 80)
            print(f"👤 작성자: {reel_data.author or 'N/A'}")
            if reel_data.title:
                title_preview = reel_data.title[:60] + "..." if len(reel_data.title) > 60 else reel_data.title
                print(f"📝 제목: {title_preview}")
            print(f"❤️  좋아요: {reel_data.likes:,}" if reel_data.likes else "❤️  좋아요: N/A")
            print(f"💬 댓글: {reel_data.comments:,}" if reel_data.comments else "💬 댓글: N/A")
            print(f"👁️  조회수: {reel_data.views:,}" if reel_data.views else "👁️  조회수: N/A")
            if reel_data.posted_date:
                print(f"📅 게시일: {reel_data.posted_date}")
            if reel_data.music:
                music_preview = reel_data.music[:50] + "..." if len(reel_data.music) > 50 else reel_data.music
                print(f"🎵 음악: {music_preview}")
            if reel_data.link:
                print(f"🔗 링크: {reel_data.link}")
            print("=" * 80 + "\n")
        except Exception as e:
            self.logger.debug(f"릴스 요약 출력 실패: {e}")

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

            # 글로벌 네트워크 리스너 등록 (한 번만)
            if not self._network_listener_registered:
                self._register_global_network_listener(page)
                self._network_listener_registered = True

            # 릴스 페이지 로딩 대기
            self._wait_for_reels_page_load(page)

            collected_reels: list[ReelData] = []
            collected_reel_ids: set[str] = set()  # 중복 체크용 (URL 기반 ID)
            collected_thumbnails: set[str] = set()  # 썸네일 중복 체크용
            save_interval = 10  # 10개마다 저장
            last_db_saved_count = 0  # DB에 저장한 구간 끝 인덱스 (reel_metrics 중복 방지)
            consecutive_failures = 0  # 연속 이동 실패 횟수
            max_failures = 5  # 최대 연속 이동 실패 허용 횟수
            consecutive_duplicates = 0  # 연속 중복 감지 횟수
            max_consecutive_duplicates = 10  # 연속 중복 N개 이상이면 피드 루프로 판단, 종료
            last_poster: str | None = None  # 릴스 전환 감지용 (DOM/카운트 갱신 안정화)

            # 실행 시간 제한 (burst credit 회복용)
            run_deadline: float | None = None
            if self.config.scrape_run_minutes:
                run_deadline = time.time() + self.config.scrape_run_minutes * 60
                self.logger.info(f"⏱️ 수집 시간 제한: {self.config.scrape_run_minutes}분 후 종료 (burst credit 회복)")

            while True:
                # 실행 시간 초과 시 정상 종료 (systemd가 RestartSec 대기 후 재시작)
                if run_deadline and time.time() > run_deadline:
                    self.logger.info(f"⏱️ 수집 시간 {self.config.scrape_run_minutes}분 경과 — 정상 종료 (크레딧 회복 대기 중)")
                    break
                try:
                    # 릴스 전환 직후 DOM이 재사용/지연 갱신되는 경우가 있어,
                    # video poster가 바뀔 때까지 짧게 기다린 뒤 수집한다.
                    try:
                        v = self._get_current_reel_video(page)
                        poster = v.get_attribute("poster") if v else None
                        if last_poster and poster and poster == last_poster:
                            for _ in range(4):  # 최대 약 2초 대기 (최적화)
                                time.sleep(0.5)
                                v = self._get_current_reel_video(page)
                                poster = v.get_attribute("poster") if v else None
                                if poster and poster != last_poster:
                                    break
                    except Exception:
                        poster = None

                    # 현재 릴스 정보 수집
                    reel_data = self._extract_current_reel_data(page)

                    if reel_data:
                        # 다음 루프를 위해 마지막 poster 갱신
                        try:
                            if reel_data.thumbnail:
                                last_poster = reel_data.thumbnail
                            elif poster:
                                last_poster = poster
                        except Exception:
                            pass

                        # 중복 체크 (여러 방법 사용)
                        is_duplicate = False
                        duplicate_reason = None

                        # 방법 1: ReelData.link 또는 현재 페이지 URL에서 /reels/<id>/ 기준 중복 체크
                        reel_id: str | None = None
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
                        # reel_id가 정상 추출된 경우에는 썸네일 체크 생략
                        # (t51.827 등 공통 UI 이미지가 잘못 추출되어 false positive 발생 방지)
                        if not is_duplicate and not reel_id and reel_data.thumbnail:
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
                            consecutive_failures = 0
                            consecutive_duplicates = 0  # 신규 릴스 수집 시 중복 카운터 리셋
                            self.logger.info(f"수집된 릴스 수: {len(collected_reels)} (작성자: {reel_data.author})")
                            self._print_reel_summary(reel_data, len(collected_reels))
                        else:
                            consecutive_duplicates += 1
                            self.logger.info(f"중복 릴스 건너뜀 ({consecutive_duplicates}/{max_consecutive_duplicates})")
                            if consecutive_duplicates >= max_consecutive_duplicates:
                                self.logger.warning(
                                    f"연속 {max_consecutive_duplicates}개 중복 감지 — "
                                    "인스타그램 피드가 루프됨, 수집 종료."
                                )
                                break

                        # 주기적으로 저장 (JSON은 전체, DB는 새로 수집된 구간만 전달해 reel_metrics 중복 방지)
                        if len(collected_reels) >= save_interval:
                            self.logger.info(f"{save_interval}개 수집 완료. 임시 저장 중...")
                            self.save_to_json(
                                collected_reels,
                                db_only_new_count=last_db_saved_count,
                            )
                            last_db_saved_count = len(collected_reels)
                            save_interval += 10

                    # 다음 릴스로 이동
                    if not self._move_to_next_reel(page):
                        consecutive_failures += 1
                        self.logger.warning(f"다음 릴스로 이동하지 못했습니다 ({consecutive_failures}/{max_failures}). 잠시 대기 후 재시도...")

                        if consecutive_failures >= max_failures:
                            self.logger.error(f"연속 {max_failures}회 이동 실패. 수집 중단.")
                            break

                        time.sleep(1)  # 대기 시간 최적화
                    else:
                        consecutive_failures = 0  # 이동 성공 시 실패 카운터 리셋
                        # 이동 성공 후 추가 안정화 대기
                        time.sleep(0.5)  # 대기 시간 최적화
                        random_delay(0.3, 0.5)  # 대기 시간 최적화

                except KeyboardInterrupt:
                    self.logger.info("사용자에 의해 중단되었습니다.")
                    # 중단 전 마지막 저장 (DB에는 아직 저장 안 한 구간만)
                    if collected_reels:
                        self.logger.info("중단 전 데이터 저장 중...")
                        self.save_to_json(
                            collected_reels,
                            db_only_new_count=last_db_saved_count,
                        )
                        last_db_saved_count = len(collected_reels)
                    break
                except Exception as e:
                    self.logger.error(f"릴스 수집 중 오류 (계속 진행): {e}")
                    time.sleep(2)

            # 루프 종료 후 아직 DB에 안 넣은 구간이 있으면 한 번 더 저장
            if collected_reels and last_db_saved_count < len(collected_reels):
                self.logger.info("수집 종료. 남은 데이터 저장 중...")
                self.save_to_json(
                    collected_reels,
                    db_only_new_count=last_db_saved_count,
                )

        except Exception as e:
            self.logger.error(f"릴스 수집 실패: {e}")
            raise ScrapingError(f"릴스 수집에 실패했습니다: {e}") from e

    def scrape_reels(
        self,
        hashtag: str | None = None,
        url: str | None = None,
        max_reels: int | None = None,
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

    def save_to_json(
        self,
        data: list[ReelData],
        filename: str | None = None,
        db_only_new_count: int | None = None,
    ) -> Path:
        """
        데이터를 JSON 파일로 저장

        Args:
            data: 저장할 데이터
            filename: 파일명 (None이면 자동 생성)
            db_only_new_count: 지정 시 DB에는 data[db_only_new_count:]만 저장 (reel_metrics 중복 방지).
                               None이면 전체 data를 DB에 저장.

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
            # S3 썸네일 아카이빙 (JSON/DB 저장 전 — S3 URL로 교체된 상태로 저장)
            if S3_AVAILABLE:
                archiver = build_archiver_from_config(self.config)
                if archiver is not None:
                    country = getattr(self.config, "country_code", None) or "unknown"
                    data, _ = archiver.batch_archive(data, country_code=country)

            self.logger.info(f"데이터 저장 중: {filepath}")
            # Pydantic 모델을 dict로 변환
            data_dict = [item.model_dump(mode="json") for item in data]

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)

            self.logger.info(f"데이터 저장 완료: {len(data)}개 항목")

            # DB가 활성화되어 있으면 DB에도 저장 (새로 수집된 구간만 전달해 reel_metrics 중복 방지)
            if self._db_enabled:
                to_save = (
                    data[db_only_new_count:]
                    if db_only_new_count is not None and db_only_new_count < len(data)
                    else data
                )
                if to_save:
                    self.logger.info(f"DB 저장 시작... (신규 {len(to_save)}건)")
                    self._save_to_db(to_save)
            else:
                self.logger.debug(f"DB 저장 건너뜀 (DB 활성화 여부: {self._db_enabled}, config.db_enabled: {self.config.db_enabled})")

            return filepath
        except Exception as e:
            self.logger.error(f"데이터 저장 실패: {e}")
            raise InstagramScraperError(f"데이터 저장에 실패했습니다: {e}") from e

    def save_to_csv(self, data: list[ReelData], filename: str | None = None) -> Path:
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
        except ImportError as e:
            raise InstagramScraperError("CSV 저장을 위해 pandas가 필요합니다.") from e
        except Exception as e:
            self.logger.error(f"CSV 저장 실패: {e}")
            raise InstagramScraperError(f"CSV 저장에 실패했습니다: {e}") from e

    def _save_to_db(self, data: list[ReelData]) -> None:
        """
        데이터베이스에 릴스 데이터 저장

        Args:
            data: 저장할 ReelData 리스트
        """
        if not self._db_enabled:
            self.logger.warning("DB 저장 시도했지만 DB가 비활성화되어 있습니다.")
            return

        self.logger.info(f"DB에 {len(data)}개 릴스 저장 시작...")
        try:
            session_gen = get_db_session()
            session = next(session_gen)

            try:
                creator_repo = CreatorRepository(session)
                reel_repo = ReelRepository(session)

                saved_count = 0
                updated_count = 0

                for reel_data in data:
                    try:
                        # 크리에이터 저장/업데이트
                        if reel_data.author:
                            creator_repo.create_or_update_creator(
                                username=reel_data.author,
                                profile_image_url=reel_data.creator_profile_image,
                            )

                        # 릴스 저장/업데이트 (계정 기준 country_code는 신규 생성 시에만 설정)
                        reel, is_new = reel_repo.create_or_update_reel(
                            reel_data, country_code=getattr(self.config, "country_code", None)
                        )
                        if is_new:
                            saved_count += 1
                        else:
                            updated_count += 1

                        # 통계 정보 추가 (시계열 추적)
                        reel_repo.add_metric(
                            reel=reel,
                            likes=reel_data.likes,
                            comments=reel_data.comments,
                            views=reel_data.views,
                        )

                    except Exception as e:
                        self.logger.warning(f"릴스 DB 저장 실패 (링크: {reel_data.link}): {e}")
                        continue

                session.commit()
                self.logger.info(
                    f"DB 저장 완료: 새로 저장 {saved_count}개, 업데이트 {updated_count}개"
                )

            finally:
                session.close()

        except Exception as e:
            self.logger.warning(f"DB 저장 실패: {e}")
            # DB 저장 실패해도 파일 저장은 성공했으므로 예외를 발생시키지 않음
