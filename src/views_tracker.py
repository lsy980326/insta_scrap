"""
조회수 추적 모듈
수집된 릴스 데이터에 조회수를 추가하는 모듈
"""

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page

from .browser import BrowserManager
from .config import ScrapingConfig
from .database import get_db_session, init_db
from .database.repositories import ReelRepository, ScrapingSessionRepository
from .exceptions import LoginError, ScrapingError
from .models import ReelData
from .utils.human_behavior import random_delay, simulate_page_interaction
from .utils.logger import get_logger
from .utils.wait_utils import safe_fill_input, wait_for_element


class ReelViewsTracker:
    """
    릴스 조회수 추적 클래스

    수집된 릴스 데이터를 기반으로 크리에이터의 reels 페이지에서 조회수를 추출합니다.
    """

    def __init__(self, config: Optional[ScrapingConfig] = None) -> None:
        """
        초기화

        Args:
            config: 스크래핑 설정 객체
        """
        self.config = config or ScrapingConfig()
        self.browser_manager: Optional[BrowserManager] = None
        self.logger = get_logger(self.__class__.__name__)
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

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        인스타그램에 로그인 (조회수 추적용 - 릴스 탭 이동/수집 없이 로그인만 수행)

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

        try:
            self.logger.info(f"로그인 시도: {username}")

            # 브라우저 시작 (아직 시작되지 않은 경우)
            if self.browser_manager is None:
                self.browser_manager = BrowserManager(self.config)
                self.browser_manager.start()

            page = self.browser_manager.get_page()

            # 인스타그램 메인 페이지로 이동 (원래 방식대로)
            self.logger.info("인스타그램 메인 페이지로 이동 중...")
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)

            # 페이지가 완전히 로드될 때까지 대기
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

            # 사용자명 입력 필드 찾기 및 입력
            username_selectors = [
                "#loginForm > div > div:nth-child(1) > div > label > input",
                '#loginForm input[type="text"]',
                'input[name="username"]',
                'input[aria-label*="전화번호"]',
                'input[aria-label*="사용자 이름"]',
            ]

            username_input = wait_for_element(
                page, username_selectors, timeout=5000, description="사용자명 입력 필드"
            )

            if not username_input:
                raise LoginError("사용자명 입력 필드를 찾을 수 없습니다.")

            if not safe_fill_input(username_input, username, description="사용자명"):
                raise LoginError("사용자명 입력에 실패했습니다.")

            # 비밀번호 입력 필드 찾기 및 입력
            password_selectors = [
                "#loginForm > div > div:nth-child(2) > div > label > input",
                '#loginForm input[type="password"]',
                'input[name="password"]',
                'input[type="password"]',
            ]

            password_input = wait_for_element(
                page, password_selectors, timeout=5000, description="비밀번호 입력 필드"
            )

            if not password_input:
                raise LoginError("비밀번호 입력 필드를 찾을 수 없습니다.")

            if not safe_fill_input(password_input, password, description="비밀번호"):
                raise LoginError("비밀번호 입력에 실패했습니다.")

            # 로그인 버튼 찾기 및 클릭
            login_button_selectors = [
                "#loginForm > div > div:nth-child(3)",
                "#loginForm > div > div:nth-child(3) button",
                '#loginForm button[type="submit"]',
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("로그인")',
            ]

            login_button = wait_for_element(
                page, login_button_selectors, timeout=5000, description="로그인 버튼"
            )

            if not login_button:
                raise LoginError("로그인 버튼을 찾을 수 없습니다.")

            # 버튼이 활성화될 때까지 대기
            self.logger.info("로그인 버튼 활성화 대기 중...")
            try:
                login_button.wait_for(state="attached", timeout=3000)
                page.wait_for_timeout(500)
            except Exception:
                pass

            # 로그인 버튼 클릭
            self.logger.info("로그인 버튼 클릭 중...")
            try:
                if login_button.is_enabled():
                    login_button.click()
                    self.logger.info("로그인 버튼 클릭 완료")
                else:
                    inner_button = login_button.locator("button").first
                    if inner_button.is_visible():
                        inner_button.click()
                        self.logger.info("내부 버튼 클릭 완료")
                    else:
                        login_button.click(force=True)
                        self.logger.info("강제 클릭 완료")
            except Exception as e:
                self.logger.warning(f"일반 클릭 실패, 강제 클릭 시도: {e}")
                login_button.click(force=True)
                self.logger.info("강제 클릭 완료")

            # 로그인 버튼 클릭 후 대기
            self.logger.info("로그인 처리 대기 중... (20초)")
            time.sleep(20)  # Python의 time.sleep 사용

            # 로그인 결과 확인
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

    def _parse_number(self, text: str) -> Optional[int]:
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

        # 만 단위 처리
        if "만" in text:
            match = re.search(r"([\d.]+)", text)
            if match:
                try:
                    num = float(match.group(1))
                    return int(num * 10000)
                except ValueError:
                    pass

        # 천 단위 처리
        elif "천" in text:
            match = re.search(r"([\d.]+)", text)
            if match:
                try:
                    num = float(match.group(1))
                    return int(num * 1000)
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

    def _extract_reel_id_from_link(self, link: str) -> Optional[str]:
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
    ) -> dict[str, int]:
        """
        크리에이터의 reels 페이지에서 조회수 추출

        Args:
            page: Playwright Page 객체
            creator_name: 크리에이터 이름
            target_reel_ids: 찾아야 할 릴스 ID 집합

        Returns:
            {릴스ID: 조회수} 딕셔너리
        """
        views_dict: dict[str, int] = {}

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
                    time.sleep(1)
                    random_delay(0.5, 1.0)
            except Exception:
                pass
            
            page.goto(
                reels_url,
                wait_until="domcontentloaded",
                timeout=30000,
                referer="https://www.instagram.com/",
            )

            # 페이지 로드 대기
            time.sleep(3)
            random_delay(1.0, 2.0)
            
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            # 로그인 상태 확인
            current_url = page.url
            if "accounts/login" in current_url or "/login" in current_url:
                self.logger.warning(
                    f"크리에이터 '{creator_name}'의 reels 페이지 접근 시 로그인이 풀렸습니다. "
                    "로그인 페이지로 리다이렉트되었습니다."
                )
                return views_dict

            self.logger.info(f"크리에이터 '{creator_name}'의 reels 페이지에서 조회수 추출 중...")

            max_scrolls = 3  # 최대 스크롤 횟수
            
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
                        if reel_id in views_dict:
                            continue

                        # 조회수 추출
                        try:
                            element_handle = link_elem.element_handle()
                            if element_handle:
                                extracted_data = element_handle.evaluate("""
                                    (link) => {
                                        const viewContainer = link.querySelector('div._aajy');
                                        if (!viewContainer) return null;

                                        const viewIcon = viewContainer.querySelector('svg[aria-label="조회수 아이콘"]');
                                        if (!viewIcon) return null;

                                        const spans = viewContainer.querySelectorAll('span.html-span.x1vvkbs, span.x1vvkbs');
                                        for (const span of spans) {
                                            const text = (span.textContent || '').trim();
                                            if (/^[\\d.,만천]+$/.test(text.replace(/\\s/g, ''))) {
                                                return text;
                                            }
                                        }
                                        return null;
                                    }
                                """)

                                if extracted_data:
                                    views_value = self._parse_number(extracted_data)
                                    if views_value and views_value > 0:
                                        if reel_id not in views_dict:
                                            views_dict[reel_id] = views_value
                                            self.logger.info(
                                                f"릴스 ID '{reel_id}' 조회수: {views_value} ({extracted_data})"
                                            )
                                        
                                        if len(views_dict) >= len(target_reel_ids):
                                            break

                        except Exception as e:
                            self.logger.debug(f"조회수 추출 실패 (릴스 ID: {reel_id}): {e}")
                            continue

                    except Exception as e:
                        self.logger.debug(f"릴스 링크 처리 중 오류: {e}")
                        continue
                
                # 모든 목표 릴스 ID를 찾았으면 스크롤 루프 종료
                if len(views_dict) >= len(target_reel_ids):
                    self.logger.info(f"모든 목표 릴스의 조회수를 찾았습니다. (총 {len(views_dict)}개)")
                    break
                
                # 스크롤이 필요하고 아직 목표를 찾지 못했으면 스크롤 시도
                if len(views_dict) < len(target_reel_ids) and scroll_attempt < max_scrolls:
                    self.logger.info(
                        f"조회수 미발견 릴스: {len(target_reel_ids) - len(views_dict)}개. "
                        f"스크롤 다운 시도 ({scroll_attempt + 1}/{max_scrolls})..."
                    )
                    
                    try:
                        viewport = page.viewport_size
                        if viewport:
                            viewport_height = viewport["height"]
                            page.mouse.move(viewport["width"] // 2, viewport["height"] // 2)
                            page.mouse.wheel(0, viewport_height)
                            time.sleep(2)
                            random_delay(1.0, 2.0)
                    except Exception as e:
                        self.logger.debug(f"스크롤 실패: {e}")
                        break

            self.logger.info(
                f"크리에이터 '{creator_name}'에서 {len(views_dict)}개 조회수 추출 완료"
            )

        except Exception as e:
            self.logger.error(f"크리에이터 '{creator_name}'의 reels 페이지 처리 실패: {e}")

        return views_dict

    def track_views(self, input_file: Path, output_file: Optional[Path] = None) -> Path:
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
            with open(input_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # ReelData 리스트로 변환
            reels: list[ReelData] = [ReelData(**item) for item in data]

            self.logger.info(f"총 {len(reels)}개 릴스 데이터 로드 완료")

            # 브라우저 시작 (로그인되지 않은 경우)
            if self.browser_manager is None:
                self.browser_manager = BrowserManager(self.config)
                self.browser_manager.start()
                
                # 로그인 정보가 있으면 자동 로그인 시도
                if self.config.instagram_username and self.config.instagram_password:
                    self.logger.info("로그인 정보가 있습니다. 로그인을 시도합니다...")
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

                    # 크리에이터의 reels 페이지에서 조회수 추출
                    views_dict = self._extract_views_from_creator_reels_page(
                        page, creator_name, target_reel_ids
                    )

                    # 조회수를 원본 데이터에 추가 및 DB 업데이트
                    for reel_id, views in views_dict.items():
                        for idx in reel_indices[reel_id]:
                            reels[idx].views = views
                            total_updated += 1
                            
                            # DB 업데이트 (활성화된 경우)
                            if self._db_enabled:
                                try:
                                    self._update_views_in_db(reel_id, views, reels[idx])
                                except Exception as e:
                                    self.logger.debug(f"DB 조회수 업데이트 실패 (계속 진행): {e}")

                    # 크리에이터 간 딜레이
                    random_delay(2.0, 4.0)
                    
                except Exception as e:
                    self.logger.error(f"크리에이터 '{creator_name}' 처리 중 오류: {e}")
                    failed_creators.append(creator_name)
                    # 브라우저가 닫혔는지 확인하고 재시작
                    try:
                        page.url
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
                f"조회수 추적 완료: {total_updated}개 릴스에 조회수 추가됨 (총 {len(reels)}개)"
            )
            if failed_creators:
                self.logger.warning(f"처리 실패한 크리에이터: {', '.join(failed_creators)}")
                self.logger.warning("로그인이 필요할 수 있습니다. login() 메서드를 사용하여 로그인하세요.")
            
            return output_file

        except Exception as e:
            self.logger.error(f"조회수 추적 실패: {e}")
            raise ScrapingError(f"조회수 추적에 실패했습니다: {e}") from e

    def _update_views_in_db(self, reel_id: str, views: int, reel_data: ReelData) -> None:
        """
        DB에서 릴스 조회수 업데이트

        Args:
            reel_id: Instagram 릴스 ID
            views: 조회수
            reel_data: ReelData 객체 (좋아요, 댓글 정보 포함)
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

                # 통계 정보 추가 (시계열 추적)
                reel_repo.add_metric(
                    reel=reel,
                    likes=reel_data.likes,
                    comments=reel_data.comments,
                    views=views,
                )

                session.commit()
                self.logger.debug(f"DB 조회수 업데이트 완료: {reel_id} (조회수: {views})")

            finally:
                session.close()

        except Exception as e:
            self.logger.warning(f"DB 조회수 업데이트 실패: {e}")
            raise

    def close(self) -> None:
        """브라우저 종료"""
        if self.browser_manager:
            self.browser_manager.close()
            self.browser_manager = None
            self.logger.info("브라우저 종료 완료")

