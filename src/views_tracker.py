"""
조회수 추적 모듈
수집된 릴스 데이터에 조회수를 추가하는 모듈
"""

import json
import re
import time
from collections import defaultdict
from pathlib import Path

from playwright.sync_api import Page

from .browser import BrowserManager
from .config import ScrapingConfig
from .database import get_db_session, init_db
from .database.repositories import ReelRepository
from .exceptions import LoginError, ScrapingError
from .models import ReelData
from .utils.human_behavior import random_delay, simulate_page_interaction
from .utils.logger import get_logger
from .utils.session_manager import SessionManager
from .utils.wait_utils import safe_fill_input, wait_for_element


class ReelViewsTracker:
    """
    릴스 조회수 추적 클래스

    수집된 릴스 데이터를 기반으로 크리에이터의 reels 페이지에서 조회수를 추출합니다.
    """

    def __init__(self, config: ScrapingConfig | None = None) -> None:
        """
        초기화

        Args:
            config: 스크래핑 설정 객체
        """
        self.config = config or ScrapingConfig()
        self.browser_manager: BrowserManager | None = None
        self.logger = get_logger(self.__class__.__name__)
        self.session_manager = SessionManager(self.config)
        self._is_logged_in = False

        # 출력 디렉토리 생성
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # 데이터베이스 초기화
        self._db_enabled = False
        if self.config.db_enabled:
            self._db_enabled = init_db(self.config)
            if self._db_enabled:
                self.logger.info("데이터베이스 연결 활성화")
            else:
                self.logger.warning("데이터베이스 연결 실패, 파일 저장만 사용합니다")

        self.logger.info("ReelViewsTracker 초기화 완료")

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
            username: 인스타그램 사용자명 (None이면 config에서 가져옴)
            password: 인스타그램 비밀번호 (None이면 config에서 가져옴)

        Returns:
            로그인 성공 여부

        Raises:
            LoginError: 로그인 실패 시
        """
        username = username or self.config.instagram_username
        password = password or self.config.instagram_password

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
                            self._is_logged_in = True
                            return True
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

            # 로그인 폼 대기
            try:
                page.wait_for_selector(
                    'input[autocomplete*="username"], input[type="text"]',
                    timeout=15000,
                    state="visible",
                )
            except Exception:
                page.wait_for_selector("input", timeout=10000, state="visible")

            self.logger.info(f"로그인 페이지 로드 완료: {page.url}")

            # ── 사용자명 입력 ──────────────────────────────────────────────
            username_selectors = [
                'input[autocomplete="username webauthn"]',
                'input[autocomplete="username"]',
                'input[type="text"]:visible',
                'input:not([type="password"]):visible',
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

            # ── Enter 키로 제출 + URL 변화 감지 ───────────────────────────
            self.logger.info("Enter 키로 로그인 제출 중...")
            page.keyboard.press("Enter")

            self.logger.info("로그인 처리 대기 중... (URL 변화 감지, 최대 30초)")
            try:
                page.wait_for_url(
                    lambda url: "accounts/login" not in url and "/login" not in url,
                    timeout=30000,
                )
                self.logger.info("로그인 성공 감지 (URL 변화 확인)")
            except Exception:
                pass

            # 로그인 후 팝업 처리
            self._handle_post_login_popup(page)

            # 로그인 상태 최종 확인
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

            self._is_logged_in = True

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

        Args:
            page: Playwright Page 객체
        """
        try:
            self.logger.info("로그인 후 팝업 확인 중...")

            max_check_time = 15000  # 15초
            check_interval = 500  # 0.5초마다 확인
            elapsed_time = 0
            popup_closed = False

            while elapsed_time < max_check_time:
                if self._check_and_close_popup(page):
                    popup_closed = True
                    time.sleep(1)
                    if not self._check_and_close_popup(page):
                        break
                else:
                    if elapsed_time > 2000:  # 최소 2초는 기다림
                        break

                time.sleep(check_interval / 1000)
                elapsed_time += check_interval

            if popup_closed:
                self.logger.info("팝업 자동 처리 완료")
            else:
                self.logger.info("팝업이 없거나 이미 처리되었습니다.")

            time.sleep(1)
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
            popup_container_selectors = [
                'body > div.x1n2onr6.xzkaem6',
                'div[role="dialog"]',
                '[data-testid="modal"]',
                '.x1n2onr6[role="dialog"]',
                'div[role="presentation"]',
                'div._a9-z',
                'div._a9--',
            ]

            for selector in popup_container_selectors:
                try:
                    popup = page.locator(selector).first
                    if popup.is_visible(timeout=500):
                        self.logger.info(f"팝업 컨테이너 발견: {selector[:50]}...")

                        popup_button_selectors = [
                            'button:has-text("확인")',
                            'button:has-text("OK")',
                            'button:has-text("Okay")',
                            'button:has-text("Got it")',
                            'button:has-text("알겠습니다")',
                            'button:has-text("다음")',
                            'button:has-text("Next")',
                            'button:has-text("Close")',
                            'button:has-text("닫기")',
                            'button[aria-label*="확인"]',
                            'button[aria-label*="OK"]',
                            'button[aria-label*="Close"]',
                            'button[aria-label*="닫기"]',
                            'div[role="dialog"] button',
                            '[data-testid="confirm"]',
                            '[data-testid="ok"]',
                            '[data-testid="close"]',
                        ]

                        button_found = False
                        for button_selector in popup_button_selectors:
                            try:
                                button = popup.locator(button_selector).first
                                if button.is_visible(timeout=500):
                                    self.logger.info(f"팝업 확인 버튼 발견: {button_selector}")
                                    button.click()
                                    page.wait_for_timeout(500)
                                    button_found = True
                                    return True
                            except Exception:
                                pass

                        if not button_found:
                            # ESC 키 등으로 닫기 시도
                            try:
                                page.keyboard.press("Escape")
                                page.wait_for_timeout(500)
                                if not popup.is_visible(timeout=500):
                                    self.logger.info("ESC 키로 팝업 닫기 성공")
                                    return True
                            except Exception:
                                pass

                        break
                except Exception:
                    continue

            return False

        except Exception as e:
            self.logger.debug(f"팝업 확인 중 오류 (무시): {e}")
            return False

    def _parse_number(self, text: str) -> int | None:
        """
        텍스트에서 숫자 추출 (예: "502.9만" -> 5029000, "5647" -> 5647)

        Args:
            text: 숫자가 포함된 텍스트

        Returns:
            파싱된 숫자, 실패 시 None
        """
        if not text:
            return None

        text = text.strip().replace(",", "").replace(" ", "")

        # 만 단위 처리 (한국어: 만, 일본어: 万)
        if "만" in text or "万" in text:
            match = re.search(r"([\d.]+)", text)
            if match:
                try:
                    num = float(match.group(1))
                    return int(num * 10000)
                except ValueError:
                    pass

        # 억 단위 처리 (일본어: 億)
        elif "억" in text or "億" in text:
            match = re.search(r"([\d.]+)", text)
            if match:
                try:
                    num = float(match.group(1))
                    return int(num * 100000000)
                except ValueError:
                    pass

        # 천 단위 처리 (한국어: 천, 일본어: 千, 영어: K/k)
        elif "천" in text or "千" in text or text.upper().endswith("K"):
            match = re.search(r"([\d.]+)", text)
            if match:
                try:
                    num = float(match.group(1))
                    return int(num * 1000)
                except ValueError:
                    pass

        # 백만 단위 처리 (영어: M)
        elif text.upper().endswith("M"):
            match = re.search(r"([\d.]+)", text)
            if match:
                try:
                    num = float(match.group(1))
                    return int(num * 1000000)
                except ValueError:
                    pass

        # 일반 숫자
        else:
            match = re.search(r"([\d.]+)", text)
            if match:
                try:
                    return int(float(match.group(1)))
                except ValueError:
                    pass

        return None

    def _extract_reel_id_from_link(self, link: str) -> str | None:
        """
        릴스 링크에서 릴스 ID 추출

        Args:
            link: 릴스 링크 (예: "https://www.instagram.com/reels/DS4U0UKgGt9/")

        Returns:
            릴스 ID (예: "DS4U0UKgGt9"), 실패 시 None
        """
        if not link:
            return None

        # /reels/ID/ 또는 /reel/ID/ 패턴 매칭
        match = re.search(r"/reels?/([^/?#]+)/?", str(link))
        if match:
            return match.group(1)
        return None

    def _extract_views_from_creator_reels_page(
        self, page: Page, creator_name: str, target_reel_ids: set[str]
    ) -> dict[str, dict[str, int | None]]:
        """
        크리에이터의 reels 페이지에서 조회수, 좋아요 수, 댓글 수 추출

        Args:
            page: Playwright Page 객체
            creator_name: 크리에이터 이름
            target_reel_ids: 찾아야 할 릴스 ID 집합

        Returns:
            {릴스ID: {views: 조회수, likes: 좋아요수, comments: 댓글수}} 딕셔너리
        """
        metrics_dict: dict[str, dict[str, int | None]] = {}

        try:
            self.logger.info(f"크리에이터 '{creator_name}'의 reels 페이지 접근 중...")

            # 크리에이터의 reels 페이지로 이동
            reels_url = f"https://www.instagram.com/{creator_name}/reels/"

            # 현재 URL이 메인 페이지가 아니면 먼저 메인 페이지로 이동하여 세션 유지
            try:
                current_url = page.url
                if "instagram.com" not in current_url or current_url == "about:blank":
                    self.logger.info("현재 페이지가 인스타그램이 아닙니다. 메인 페이지로 이동 후 reels 페이지로 이동합니다.")
                    page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
                    time.sleep(0.5)
                    random_delay(0.3, 0.7)
            except Exception:
                pass

            page.goto(
                reels_url,
                wait_until="domcontentloaded",
                timeout=30000,
                referer="https://www.instagram.com/",
            )

            # 페이지 로드 대기 (최적화: 대기 시간 단축)
            time.sleep(1)
            random_delay(0.5, 1.0)

            try:
                page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass

            # 로그인 상태 확인 — URL 리다이렉트 또는 인페이지 로그인 오버레이 감지
            current_url = page.url
            login_overlay = False
            try:
                # Instagram은 URL 유지하면서 로그인 오버레이를 띄우기도 함
                login_overlay = page.locator(
                    'input[name="username"], input[name="email"], a[href="/accounts/login/"]'
                ).first.is_visible(timeout=1500)
            except Exception:
                pass
            if "accounts/login" in current_url or "/login" in current_url or login_overlay:
                self.logger.warning(
                    f"크리에이터 '{creator_name}'의 reels 페이지 접근 시 로그인 리다이렉트 감지. 재로그인 시도..."
                )
                try:
                    self._is_logged_in = False
                    self.login()
                    page.goto(
                        reels_url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                        referer="https://www.instagram.com/",
                    )
                    time.sleep(1)
                    current_url = page.url
                    if "accounts/login" in current_url or "/login" in current_url:
                        self.logger.error(f"재로그인 후에도 로그인 페이지입니다. '{creator_name}' 건너뜁니다.")
                        return metrics_dict
                    self.logger.info("재로그인 성공, 계속 진행합니다.")
                except Exception as e:
                    self.logger.error(f"재로그인 실패: {e}. '{creator_name}' 건너뜁니다.")
                    return metrics_dict

            self.logger.info(f"크리에이터 '{creator_name}'의 reels 페이지에서 조회수 추출 중...")

            max_scrolls = 10  # 최대 스크롤 횟수

            # 스크롤하면서 조회수 추출 시도
            for scroll_attempt in range(max_scrolls + 1):
                # 모든 릴스 링크 찾기
                reel_links = page.locator(f'a[href^="/{creator_name}/reel/"]').all()

                if scroll_attempt == 0:
                    self.logger.info(f"크리에이터 '{creator_name}'의 릴스 링크 {len(reel_links)}개 발견 (초기)")
                else:
                    self.logger.info(f"스크롤 후 릴스 링크 {len(reel_links)}개 발견 (스크롤 {scroll_attempt}회)")

                # 각 릴스 링크에서 조회수 추출
                for link_elem in reel_links[:100]:
                    try:
                        # href에서 릴스 ID 추출
                        href = link_elem.get_attribute("href") or ""
                        reel_id_match = re.search(rf"/{re.escape(creator_name)}/reel/([^/]+)/?", href)
                        if not reel_id_match:
                            continue

                        reel_id = reel_id_match.group(1)

                        # 찾고 있는 릴스 ID가 아니면 스킵
                        if reel_id not in target_reel_ids:
                            continue

                        # 이미 찾았으면 스킵
                        if reel_id in metrics_dict:
                            continue

                        # 조회수, 좋아요 수, 댓글 수 추출
                        try:
                            element_handle = link_elem.element_handle()
                            if element_handle:
                                extracted_data = element_handle.evaluate("""
                                    (link) => {
                                        const result = { views: null, likes: null, comments: null };

                                        // 링크의 부모 요소에서 통계 정보 찾기
                                        let parent = link.parentElement;
                                        let depth = 0;

                                        // 통계 컨테이너 찾기 (일반적으로 통계들이 함께 있는 컨테이너)
                                        while (parent && depth < 5) {
                                            // 구조 파악: _aajz > _aaj- (좋아요/댓글) > _aaj_ (조회수)

                                            // 1. 조회수 찾기: _aaj_ 안에 조회수 아이콘과 숫자
                                            const viewsContainer = parent.querySelector('div._aaj_');
                                            if (viewsContainer && !result.views) {
                                                // aria-label 다국어 지원 (한국어/영어/일본어) + fallback
                                                const viewsIcon = viewsContainer.querySelector(
                                                    'svg[aria-label*="조회수"], svg[aria-label*="view"], svg[aria-label*="View"], ' +
                                                    'svg[aria-label*="再生"], svg[aria-label*="視聴"], svg[aria-label*="回再生"]'
                                                );
                                                const searchIn = viewsIcon
                                                    ? viewsIcon.parentElement
                                                    : viewsContainer;  // fallback: 컨테이너 전체에서 숫자 탐색
                                                if (searchIn) {
                                                    const spans = searchIn.querySelectorAll ? searchIn.querySelectorAll('span') : searchIn.parentElement.querySelectorAll('span');
                                                    for (const span of spans) {
                                                        const text = (span.textContent || '').trim();
                                                        if (/^[\\d.,만천万千億億억kKmM]+$/.test(text.replace(/\\s/g, '')) && text.length > 0) {
                                                            result.views = text;
                                                            break;
                                                        }
                                                    }
                                                }
                                            }

                                            // 2. 좋아요와 댓글 찾기: _aaj- 안에 ul > li 순서대로
                                            const statsContainer = parent.querySelector('div._aaj-');
                                            if (statsContainer) {
                                                const ul = statsContainer.querySelector('ul');
                                                if (ul) {
                                                    const lis = Array.from(ul.querySelectorAll('li'));

                                                    // 첫 번째 li: 좋아요 (위)
                                                    if (lis.length > 0 && !result.likes) {
                                                        const firstLi = lis[0];
                                                        const spans = firstLi.querySelectorAll('span.html-span.x1vvkbs');
                                                        for (const span of spans) {
                                                            const text = (span.textContent || '').trim();
                                                            if (/^[\\d.,만천万千億億억kKmM]+$/.test(text.replace(/\\s/g, '')) && text.length > 0) {
                                                                result.likes = text;
                                                                break;
                                                            }
                                                        }
                                                    }

                                                    // 두 번째 li: 댓글 (아래)
                                                    if (lis.length > 1 && result.comments === null) {
                                                        const secondLi = lis[1];
                                                        const spans = secondLi.querySelectorAll('span.html-span.x1vvkbs');
                                                        for (const span of spans) {
                                                            const text = (span.textContent || '').trim();
                                                            if (/^[\\d.,만천万千億億억kKmM]+$/.test(text.replace(/\\s/g, '')) && text.length > 0) {
                                                                result.comments = text;
                                                                break;
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                            // 모든 통계를 찾았으면 종료
                                            if (result.views && result.likes && result.comments !== null) {
                                                break;
                                            }

                                            parent = parent.parentElement;
                                            depth++;
                                        }

                                        // 하나라도 찾았으면 반환
                                        if (result.views || result.likes || result.comments !== null) {
                                            return result;
                                        }

                                        return null;
                                    }
                                """)

                                if extracted_data:
                                    metrics = {
                                        'views': None,
                                        'likes': None,
                                        'comments': None
                                    }

                                    if extracted_data.get('views'):
                                        views_value = self._parse_number(extracted_data['views'])
                                    if views_value and views_value > 0:
                                            metrics['views'] = views_value

                                    if extracted_data.get('likes'):
                                        likes_value = self._parse_number(extracted_data['likes'])
                                        if likes_value and likes_value > 0:
                                            metrics['likes'] = likes_value

                                    if extracted_data.get('comments'):
                                        comments_value = self._parse_number(extracted_data['comments'])
                                        if comments_value and comments_value >= 0:  # 댓글은 0도 유효
                                            metrics['comments'] = comments_value

                                    # 하나라도 찾았으면 저장
                                    if metrics['views'] or metrics['likes'] or metrics['comments'] is not None:
                                        if reel_id not in metrics_dict:
                                            metrics_dict[reel_id] = metrics
                                            # 모든 통계를 로그에 표시 (없으면 "없음" 표시)
                                            log_items = []
                                            log_items.append(f"좋아요: {metrics['likes'] if metrics['likes'] else '없음'}")
                                            log_items.append(f"댓글: {metrics['comments'] if metrics['comments'] is not None else '없음'}")
                                            log_items.append(f"조회수: {metrics['views'] if metrics['views'] else '없음'}")
                                            self.logger.info(
                                                f"릴스 ID '{reel_id}' - {', '.join(log_items)}"
                                            )

                                        if len(metrics_dict) >= len(target_reel_ids):
                                            break
                                else:
                                    self.logger.debug(f"통계 추출 실패 (릴스 ID: {reel_id}) - 링크는 찾았지만 통계 정보를 찾을 수 없습니다")

                        except Exception as e:
                            self.logger.debug(f"조회수 추출 실패 (릴스 ID: {reel_id}): {e}")
                            continue

                    except Exception as e:
                        self.logger.debug(f"릴스 링크 처리 중 오류: {e}")
                        continue

                # 모든 목표 릴스 ID를 찾았으면 스크롤 루프 종료
                if len(metrics_dict) >= len(target_reel_ids):
                    self.logger.info(f"모든 목표 릴스의 통계를 찾았습니다. (총 {len(metrics_dict)}개)")
                    break

                # 스크롤이 필요하고 아직 목표를 찾지 못했으면 스크롤 시도
                if len(metrics_dict) < len(target_reel_ids) and scroll_attempt < max_scrolls:
                    self.logger.info(
                        f"통계 미발견 릴스: {len(target_reel_ids) - len(metrics_dict)}개. "
                        f"스크롤 다운 시도 ({scroll_attempt + 1}/{max_scrolls})..."
                    )

                    try:
                        viewport = page.viewport_size
                        if viewport:
                            viewport_height = viewport["height"]
                            page.mouse.move(viewport["width"] // 2, viewport["height"] // 2)
                            page.mouse.wheel(0, viewport_height)
                            time.sleep(1)
                            random_delay(0.5, 1.0)
                    except Exception as e:
                        self.logger.debug(f"스크롤 실패: {e}")
                        break

            # 크리에이터 페이지에서 못 찾은 릴스 → 직접 URL fallback
            missing_ids = target_reel_ids - set(metrics_dict.keys())
            if missing_ids:
                self.logger.info(f"크리에이터 페이지에서 미발견 {len(missing_ids)}개 → 직접 URL fallback 시도")
                for reel_id in missing_ids:
                    try:
                        direct_url = f"https://www.instagram.com/reels/{reel_id}/"
                        page.goto(direct_url, wait_until="domcontentloaded", timeout=20000)
                        random_delay(1.5, 2.5)
                        metrics = page.evaluate("""
                            () => {
                                const result = { views: null, likes: null, comments: null };
                                const numRe = /^[\\d.,万千億억만천kKmM]+$/;

                                // section 안의 버튼/링크에서 aria-label로 구분
                                const section = document.querySelector('section');
                                if (section) {
                                    const btns = section.querySelectorAll('button, a[href*="liked_by"], a[href*="comments"]');
                                    for (const btn of btns) {
                                        const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                                        const spans = btn.querySelectorAll('span');
                                        for (const s of spans) {
                                            const t = (s.textContent || '').trim();
                                            if (!numRe.test(t.replace(/\\s/g,'')) || !t) continue;
                                            if (/like|좋아요|いいね|赞/.test(label) && !result.likes) { result.likes = t; break; }
                                            if (/comment|댓글|コメント|评论/.test(label) && result.comments === null) { result.comments = t; break; }
                                        }
                                    }
                                    // 버튼 aria-label 실패 시 section 내 고유 숫자 순서대로
                                    if (!result.likes && result.comments === null) {
                                        const seen = new Set();
                                        const uniq = [];
                                        section.querySelectorAll('span').forEach(s => {
                                            const t = (s.textContent || '').trim();
                                            if (numRe.test(t.replace(/\\s/g,'')) && t && t.length < 12 && !seen.has(t)) {
                                                seen.add(t); uniq.push(t);
                                            }
                                        });
                                        if (uniq.length >= 1) result.likes = uniq[0];
                                        if (uniq.length >= 2) result.comments = uniq[1];
                                    }
                                }
                                // 조회수: video aria-label 또는 meta
                                const videoMeta = document.querySelector('meta[property="og:video:duration"]');
                                const viewSpan = document.querySelector('span[aria-label*="view"], span[aria-label*="조회"], span[aria-label*="再生"]');
                                if (viewSpan) {
                                    const t = (viewSpan.textContent || '').trim();
                                    if (numRe.test(t.replace(/\\s/g,''))) result.views = t;
                                }
                                return result;
                            }
                        """)
                        parsed = {}
                        if metrics.get('views'):
                            v = self._parse_number(metrics['views'])
                            if v and v > 0: parsed['views'] = v
                        if metrics.get('likes'):
                            l = self._parse_number(metrics['likes'])
                            if l and l > 0: parsed['likes'] = l
                        if metrics.get('comments') is not None:
                            c = self._parse_number(metrics['comments'])
                            if c is not None and c >= 0: parsed['comments'] = c
                        if parsed:
                            metrics_dict[reel_id] = parsed
                            self.logger.info(f"직접 URL fallback 성공: {reel_id} — {parsed}")
                        else:
                            self.logger.info(f"직접 URL fallback 실패 (통계 없음): {reel_id}")
                        random_delay(1.0, 2.0)
                    except Exception as e:
                        self.logger.warning(f"직접 URL fallback 오류 ({reel_id}): {e}")

            # 추출된 통계 요약 로그
            total_found = len(metrics_dict)
            views_found = sum(1 for m in metrics_dict.values() if m.get('views'))
            likes_found = sum(1 for m in metrics_dict.values() if m.get('likes'))
            comments_found = sum(1 for m in metrics_dict.values() if m.get('comments') is not None)

            self.logger.info(
                f"크리에이터 '{creator_name}'에서 {total_found}개 릴스 통계 추출 완료 "
                f"(좋아요: {likes_found}개, 댓글: {comments_found}개, 조회수: {views_found}개)"
            )

        except Exception as e:
            self.logger.error(f"크리에이터 '{creator_name}'의 reels 페이지 처리 실패: {e}")

        return metrics_dict

    def track_views(self, input_file: Path, output_file: Path | None = None) -> Path:
        """
        수집된 릴스 데이터에 조회수 추가

        Args:
            input_file: 입력 JSON 파일 경로 (수집된 릴스 데이터)
            output_file: 출력 JSON 파일 경로 (None이면 자동 생성)

        Returns:
            출력 파일 경로

        Raises:
            ScrapingError: 처리 실패 시
        """
        try:
            # 입력 파일 읽기
            self.logger.info(f"입력 파일 로드: {input_file}")
            with open(input_file, encoding="utf-8") as f:
                data = json.load(f)

            # ReelData 리스트로 변환
            reels: list[ReelData] = [ReelData(**item) for item in data]

            self.logger.info(f"총 {len(reels)}개 릴스 데이터 로드 완료")

            # 브라우저 시작 + 로그인 (로그인 안 된 경우 모두 포함)
            if not self._is_logged_in:
                if self.browser_manager is None:
                    self.browser_manager = BrowserManager(self.config)
                    self.browser_manager.start()

                if self.config.instagram_username and self.config.instagram_password:
                    self.logger.info("로그인 시도 중...")
                    try:
                        self.login()
                        self.logger.info("로그인 성공! 조회수 추적을 시작합니다.")
                    except Exception as e:
                        self.logger.warning(f"로그인 실패: {e}")
                        self.logger.warning("로그인 없이 계속 진행합니다. 일부 크리에이터의 reels 페이지는 접근할 수 없을 수 있습니다.")
                else:
                    self.logger.warning(
                        "로그인되지 않았습니다. 일부 크리에이터의 reels 페이지는 접근할 수 없을 수 있습니다."
                    )

            page = self.browser_manager.get_page()

            # 크리에이터별로 그룹화
            creator_reels: dict[str, list[tuple[int, ReelData]]] = defaultdict(list)
            for idx, reel in enumerate(reels):
                if reel.author:
                    creator_reels[reel.author].append((idx, reel))

            self.logger.info(f"총 {len(creator_reels)}명의 크리에이터 발견")

            # 각 크리에이터별로 조회수 추출
            total_updated = 0
            failed_creators = []

            for creator_name, reel_list in creator_reels.items():
                try:
                    # 해당 크리에이터의 릴스 ID 수집
                    target_reel_ids: set[str] = set()
                    reel_indices: dict[str, list[int]] = defaultdict(list)

                    for idx, reel in reel_list:
                        reel_id = self._extract_reel_id_from_link(str(reel.link))
                        if reel_id:
                            target_reel_ids.add(reel_id)
                            reel_indices[reel_id].append(idx)

                    if not target_reel_ids:
                        self.logger.warning(
                            f"크리에이터 '{creator_name}'의 릴스 ID를 추출할 수 없습니다."
                        )
                        continue

                    # 크리에이터의 reels 페이지에서 조회수, 좋아요, 댓글 수 추출
                    metrics_dict = self._extract_views_from_creator_reels_page(
                        page, creator_name, target_reel_ids
                    )

                    # 통계를 원본 데이터에 추가 및 DB 업데이트
                    for reel_id, metrics in metrics_dict.items():
                        for idx in reel_indices[reel_id]:
                            # 조회수 업데이트
                            if metrics.get('views'):
                                reels[idx].views = metrics['views']
                            # 좋아요 수 업데이트
                            if metrics.get('likes'):
                                reels[idx].likes = metrics['likes']
                            # 댓글 수 업데이트
                            if metrics.get('comments') is not None:
                                reels[idx].comments = metrics['comments']

                            # 하나라도 업데이트되었으면 카운트
                            if metrics.get('views') or metrics.get('likes') or metrics.get('comments') is not None:
                                total_updated += 1

                            # DB 업데이트 (활성화된 경우) - 좋아요, 댓글, 조회수 모두 저장
                            if self._db_enabled:
                                try:
                                    # 추출된 값이 있으면 사용, 없으면 기존 값 사용
                                    views = metrics.get('views') if metrics.get('views') is not None else reels[idx].views
                                    likes = metrics.get('likes') if metrics.get('likes') is not None else reels[idx].likes
                                    comments = metrics.get('comments') if metrics.get('comments') is not None else reels[idx].comments

                                    # 하나라도 값이 있으면 DB에 저장
                                    if views is not None or likes is not None or comments is not None:
                                        self._update_views_in_db(reel_id, views, reels[idx], likes, comments)
                                except Exception as e:
                                    self.logger.debug(f"DB 통계 업데이트 실패 (계속 진행): {e}")

                    # 크리에이터 간 딜레이 (최적화: 대기 시간 단축)
                    random_delay(1.0, 2.0)

                except Exception as e:
                    self.logger.error(f"크리에이터 '{creator_name}' 처리 중 오류: {e}")
                    failed_creators.append(creator_name)
                    # 브라우저가 닫혔는지 확인하고 재시작
                    try:
                        _ = page.url
                    except Exception:
                        self.logger.warning("브라우저가 닫혔습니다. 브라우저를 재시작합니다.")
                        if self.browser_manager:
                            try:
                                self.browser_manager.close()
                            except Exception:
                                pass
                        self.browser_manager = BrowserManager(self.config)
                        self.browser_manager.start()
                        page = self.browser_manager.get_page()
                    continue

            # 출력 파일 경로 결정
            if output_file is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_file = self.config.output_dir / f"reels_data_with_views_{timestamp}.json"
            else:
                output_file = Path(output_file)

            # 결과 저장
            self.logger.info(f"결과 저장 중: {output_file}")
            data_dict = [item.model_dump(mode="json") for item in reels]

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)

            self.logger.info(
                f"통계 추적 완료: {total_updated}개 릴스에 통계 추가됨 (총 {len(reels)}개)"
            )
            if failed_creators:
                self.logger.warning(f"처리 실패한 크리에이터: {', '.join(failed_creators)}")
                self.logger.warning("로그인이 필요할 수 있습니다. login() 메서드를 사용하여 로그인하세요.")

            return output_file

        except Exception as e:
            self.logger.error(f"조회수 추적 실패: {e}")
            raise ScrapingError(f"조회수 추적에 실패했습니다: {e}") from e

    def _block_images_for_tracking(self, page: "Page") -> None:
        """추적 전용 이미지 차단 — 크리에이터 릴스 그리드 썸네일 렌더링 부하 감소"""
        _abort = lambda route: route.abort()  # noqa: E731
        for _pat in ("**/*.jpg", "**/*.jpeg", "**/*.png", "**/*.webp", "**/*.gif", "**/*.avif"):
            page.route(_pat, _abort)

    def track_from_db(self, country_code: str, days: int = 7, notifier=None, profile: str = "") -> int:
        """
        DB에서 최근 N일 릴스를 로드하여 views/likes/comments 추적

        Args:
            country_code: 국가 코드 (예: kr, jp)
            days: 최근 며칠치 릴스를 추적할지 (기본 7일)

        Returns:
            업데이트된 릴스 수
        """
        if not self._db_enabled:
            raise ScrapingError("DB가 비활성화 상태입니다. DB_ENABLED=true 설정이 필요합니다.")

        # 브라우저 시작 + 로그인
        if self.browser_manager is None:
            self.browser_manager = BrowserManager(self.config)
            self.browser_manager.start()

        if not self._is_logged_in:
            self.login()

        page = self.browser_manager.get_page()

        # 추적 전용 이미지 차단 (크리에이터 릴스 그리드 최적화)
        self._block_images_for_tracking(page)

        # DB에서 추적 대상 로드
        session_gen = get_db_session()
        session = next(session_gen)
        try:
            reel_repo = ReelRepository(session)
            reels = reel_repo.find_recent_by_country(country_code, days)
        finally:
            session.close()

        self.logger.info(f"DB 추적 대상: {len(reels)}개 릴스 ({country_code}, 최근 {days}일)")

        if not reels:
            self.logger.warning("추적 대상 릴스가 없습니다.")
            self.tracked_count = 0
            return 0

        # 크리에이터별 그룹화 (1크리에이터 = 1페이지 방문으로 최소화)
        creator_reels: dict[str, list] = defaultdict(list)
        for reel in reels:
            if reel.author:
                creator_reels[reel.author].append(reel)

        self.logger.info(f"크리에이터 {len(creator_reels)}명 대상")

        if notifier:
            notifier.send_track_start(profile or country_code, len(reels), len(creator_reels))

        total_updated = 0
        failed_creators = []
        batch_size = self.config.track_batch_size
        batch_sleep = self.config.track_batch_sleep
        creators = list(creator_reels.items())
        total_batches = -(-len(creators) // batch_size)  # ceiling division

        for batch_idx, batch_start in enumerate(range(0, len(creators), batch_size)):
            batch = creators[batch_start:batch_start + batch_size]
            self.logger.info(
                f"배치 {batch_idx + 1}/{-(-len(creators) // batch_size)} 시작 "
                f"({batch_start + 1}~{min(batch_start + batch_size, len(creators))}/{len(creators)}명)"
            )

            for creator_name, reel_list in batch:
                try:
                    target_reel_ids = {r.reel_id for r in reel_list if r.reel_id}
                    if not target_reel_ids:
                        continue

                    metrics_dict = self._extract_views_from_creator_reels_page(
                        page, creator_name, target_reel_ids
                    )

                    for reel_id, metrics in metrics_dict.items():
                        try:
                            s = next(get_db_session())
                            try:
                                repo = ReelRepository(s)
                                reel = repo.find_by_reel_id(reel_id)
                                if reel:
                                    repo.add_metric(
                                        reel=reel,
                                        views=metrics.get("views"),
                                        likes=metrics.get("likes"),
                                        comments=metrics.get("comments"),
                                    )
                                    s.commit()
                                    total_updated += 1
                            finally:
                                s.close()
                        except Exception as e:
                            self.logger.debug(f"DB 업데이트 실패 ({reel_id}): {e}")

                    random_delay(1.0, 2.0)

                except Exception as e:
                    self.logger.error(f"크리에이터 '{creator_name}' 처리 오류: {e}")
                    failed_creators.append(creator_name)
                    try:
                        _ = page.url
                    except Exception:
                        self.logger.warning("브라우저 재시작 중...")
                        if self.browser_manager:
                            try:
                                self.browser_manager.close()
                            except Exception:
                                pass
                        self.browser_manager = BrowserManager(self.config)
                        self.browser_manager.start()
                        page = self.browser_manager.get_page()
                        self._block_images_for_tracking(page)

            # 배치 완료 진행상황 알림
            done_creators = min(batch_start + batch_size, len(creators))
            if notifier:
                notifier.send_track_progress(
                    profile or country_code,
                    batch_idx + 1, total_batches,
                    done_creators, len(creators),
                    total_updated,
                )

            # 배치 간 휴식 (마지막 배치 제외)
            if batch_start + batch_size < len(creators) and batch_sleep > 0:
                self.logger.info(f"⏱️ 배치 휴식 {batch_sleep}초 (burst credit 회복 중...)")
                time.sleep(batch_sleep)

        if failed_creators:
            self.logger.warning(f"처리 실패 크리에이터 {len(failed_creators)}명: {', '.join(failed_creators)}")

        self.logger.info(f"DB 추적 완료: {total_updated}개 릴스 업데이트")
        self.tracked_count = total_updated
        self._failed_creators_last = failed_creators
        return total_updated

    def _update_views_in_db(
        self,
        reel_id: str,
        views: int | None,
        reel_data: ReelData,
        likes: int | None = None,
        comments: int | None = None
    ) -> None:
        """
        DB에서 릴스 통계 업데이트 (조회수, 좋아요, 댓글)

        Args:
            reel_id: Instagram 릴스 ID
            views: 조회수 (None이면 reel_data에서 가져옴)
            reel_data: ReelData 객체 (좋아요, 댓글 정보 포함)
            likes: 좋아요 수 (None이면 reel_data에서 가져옴)
            comments: 댓글 수 (None이면 reel_data에서 가져옴)
        """
        if not self._db_enabled:
            return

        try:
            session_gen = get_db_session()
            session = next(session_gen)

            try:
                reel_repo = ReelRepository(session)

                # 릴스 조회
                reel = reel_repo.find_by_reel_id(reel_id)
                if not reel:
                    self.logger.debug(f"DB에서 릴스를 찾을 수 없습니다: {reel_id}")
                    return

                # 통계 정보 추가 (시계열 추적) - 좋아요, 댓글, 조회수 모두 저장
                final_views = views if views is not None else reel_data.views
                final_likes = likes if likes is not None else reel_data.likes
                final_comments = comments if comments is not None else reel_data.comments

                # 하나라도 값이 있으면 DB에 저장
                if final_views is not None or final_likes is not None or final_comments is not None:
                    reel_repo.add_metric(
                        reel=reel,
                        likes=final_likes,
                        comments=final_comments,
                        views=final_views,
                    )

                    session.commit()
                    stats = []
                    if final_views is not None:
                        stats.append(f"조회수: {final_views}")
                    if final_likes is not None:
                        stats.append(f"좋아요: {final_likes}")
                    if final_comments is not None:
                        stats.append(f"댓글: {final_comments}")
                    self.logger.debug(f"DB 통계 업데이트 완료: {reel_id} ({', '.join(stats) if stats else '없음'})")

            finally:
                session.close()

        except Exception as e:
            self.logger.warning(f"DB 통계 업데이트 실패: {e}")
            raise

    def close(self) -> None:
        """브라우저 종료"""
        if self.browser_manager:
            self.browser_manager.close()
            self.browser_manager = None
            self.logger.info("브라우저 종료 완료")

