"""
숏트렌드 스크래퍼 모듈
숏트렌드 사이트에서 릴스 데이터를 수집하는 클래스
"""

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page

from .browser import BrowserManager
from .config import ScrapingConfig
from .exceptions import InstagramScraperError, LoginError, ScrapingError
from .models import ShortrendReelData
from .utils.human_behavior import random_delay, simulate_page_interaction
from .utils.logger import get_logger
from .utils.wait_utils import safe_fill_input, wait_for_element


class ShortrendScraper:
    """
    숏트렌드 사이트를 스크래핑하는 클래스
    """

    def __init__(
        self,
        config: Optional[ScrapingConfig] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """
        초기화

        Args:
            config: 스크래핑 설정 객체
            email: 숏트렌드 이메일 (선택, config보다 우선)
            password: 숏트렌드 비밀번호 (선택, config보다 우선)
        """
        self.config = config or ScrapingConfig()
        # 직접 전달받은 값 우선, 없으면 config에서 가져오기
        self.email = email or self.config.shortrend_email
        self.password = password or self.config.shortrend_password
        self.browser_manager: Optional[BrowserManager] = None
        self.logger = get_logger(self.__class__.__name__)

        # 출력 디렉토리 생성
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("ShortrendScraper 초기화 완료")

    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        숏트렌드에 로그인

        Args:
            email: 숏트렌드 이메일 (None이면 기존 값 사용)
            password: 숏트렌드 비밀번호 (None이면 기존 값 사용)

        Returns:
            로그인 성공 여부

        Raises:
            LoginError: 로그인 실패 시
        """
        email = email or self.email
        password = password or self.password

        if not email or not password:
            raise LoginError("이메일과 비밀번호가 필요합니다.")

        try:
            self.logger.info(f"로그인 시도: {email}")

            # 브라우저 시작 (아직 시작되지 않은 경우)
            if self.browser_manager is None:
                self.browser_manager = BrowserManager(self.config)
                self.browser_manager.start()

            page = self.browser_manager.get_page()

            # 숏트렌드 로그인 페이지로 이동
            self.logger.info("숏트렌드 로그인 페이지로 이동 중...")
            page.goto(
                "https://shortrend.com/login_page",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            # 페이지가 완전히 로드될 때까지 대기
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                self.logger.debug("페이지 로드 대기 실패 (계속 진행)")

            random_delay(1.0, 2.0)  # 사용자처럼 랜덤 대기

            # 페이지 상호작용 시뮬레이션 (봇 감지 우회)
            simulate_page_interaction(page, min_actions=1, max_actions=2)

            # 로그인 폼이 나타날 때까지 대기
            self.logger.info("로그인 폼 확인 중...")
            try:
                # 이메일 입력 필드가 나타날 때까지 대기
                page.wait_for_selector("#login-email", timeout=10000, state="visible")
                self.logger.info("로그인 폼 로드 완료")
            except Exception as e:
                self.logger.warning(f"로그인 폼 대기 실패, 계속 진행: {e}")

            # 추가 안정화 대기
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1000)

            # 디버깅: 페이지 HTML 저장 및 스크린샷 저장
            self.logger.info("=" * 60)
            self.logger.info("로그인 페이지 로드 완료")
            self.logger.info("=" * 60)
            self.logger.info("현재 페이지 URL: " + page.url)

            # 페이지 HTML 저장 (디버깅용)
            html_content = page.content()
            debug_dir = self.config.output_dir / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)

            html_file = debug_dir / "shortrend_login_page.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            self.logger.info(f"페이지 HTML 저장: {html_file}")

            # 스크린샷 저장
            screenshot_file = debug_dir / "shortrend_login_page.png"
            page.screenshot(path=str(screenshot_file), full_page=True)
            self.logger.info(f"스크린샷 저장: {screenshot_file}")

            self.logger.info("입력 필드와 로그인 버튼을 찾는 중...")

            # 이메일 입력 필드 찾기 및 입력
            email_selectors = [
                "#login-email",  # 제공된 셀렉터
                'input[type="email"]',
                'input[name="email"]',
                'input[id*="email"]',
            ]

            email_input = wait_for_element(
                page, email_selectors, timeout=5000, description="이메일 입력 필드"
            )

            if not email_input:
                raise LoginError("이메일 입력 필드를 찾을 수 없습니다.")

            # 안전하게 입력 (유틸리티 함수 사용)
            if not safe_fill_input(email_input, email, description="이메일"):
                raise LoginError("이메일 입력에 실패했습니다.")

            # 비밀번호 입력 필드 찾기 및 입력
            password_selectors = [
                "#login-password",  # 제공된 셀렉터
                'input[type="password"]',
                'input[name="password"]',
                'input[id*="password"]',
            ]

            password_input = wait_for_element(
                page, password_selectors, timeout=5000, description="비밀번호 입력 필드"
            )

            if not password_input:
                raise LoginError("비밀번호 입력 필드를 찾을 수 없습니다.")

            # 안전하게 입력 (유틸리티 함수 사용)
            if not safe_fill_input(password_input, password, description="비밀번호"):
                raise LoginError("비밀번호 입력에 실패했습니다.")

            # 로그인 버튼 찾기 및 클릭
            login_button_selectors = [
                'button[type="submit"]',  # 제공된 셀렉터
                'button:has-text("로그인")',
                'button:has-text("Log in")',
                'form button[type="submit"]',
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
                page.wait_for_timeout(500)  # 추가 안정화 대기
            except Exception:
                pass  # 대기 실패해도 계속 진행

            # 로그인 버튼 클릭
            self.logger.info("로그인 버튼 클릭 중...")
            try:
                if login_button.is_enabled():
                    login_button.click()
                    self.logger.info("로그인 버튼 클릭 완료")
                else:
                    # 버튼이 비활성화되어 있으면 강제 클릭 시도
                    login_button.click(force=True)
                    self.logger.info("강제 클릭 완료")
            except Exception as e:
                self.logger.warning(f"일반 클릭 실패, 강제 클릭 시도: {e}")
                login_button.click(force=True)
                self.logger.info("강제 클릭 완료")

            # 로그인 처리 대기
            self.logger.info("로그인 처리 대기 중... (5초)")
            time.sleep(5)  # Python의 time.sleep 사용

            # 로그인 결과 확인
            try:
                current_url = page.url
                self.logger.info(f"현재 URL: {current_url}")

                # 로그인 페이지에 여전히 있으면 경고만 출력
                if "login_page" in current_url or "login" in current_url:
                    self.logger.warning(
                        "로그인 페이지에 여전히 있습니다. 로그인 실패 가능성이 있습니다."
                    )
                else:
                    self.logger.info("로그인 성공으로 보입니다 (로그인 페이지가 아님)")
            except Exception as e:
                self.logger.warning(f"URL 가져오기 실패: {e}")

            self.email = email
            self.password = password
            self.logger.info("로그인 프로세스 완료")

            # 로그인 후 필터 설정 (날짜 선택 및 새 영상만 보기 토글)
            try:
                self.logger.info("필터 설정 중...")
                self._setup_filters(page)
            except Exception as e:
                self.logger.warning(f"필터 설정 중 오류 (계속 진행): {e}")

            return True

        except Exception as e:
            self.logger.error(f"로그인 실패: {e}")
            raise LoginError(f"로그인에 실패했습니다: {e}") from e

    def _setup_filters(self, page: Page) -> None:
        """
        필터 설정 (날짜 선택 및 새 영상만 보기 토글)

        Args:
            page: Playwright Page 객체
        """
        try:
            # 페이지가 완전히 로드될 때까지 대기
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            random_delay(1.0, 2.0)

            # 1. 날짜를 오늘 날짜로 설정
            self.logger.info("날짜 필드 설정 중...")
            today = datetime.now().strftime("%Y-%m-%d")

            date_selectors = [
                "#date",  # 제공된 셀렉터
                'input[type="date"]',
                'input[id="date"]',
            ]

            date_input = wait_for_element(
                page, date_selectors, timeout=5000, description="날짜 입력 필드"
            )

            if date_input:
                # JavaScript로 날짜 값 설정
                page.evaluate(
                    f"""
                    (() => {{
                        const dateInput = document.querySelector('#date');
                        if (dateInput) {{
                            dateInput.value = '{today}';
                            // change 이벤트 발생
                            dateInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            dateInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }})();
                    """
                )
                self.logger.info(f"날짜 설정 완료: {today}")
                page.wait_for_timeout(500)
            else:
                self.logger.warning("날짜 입력 필드를 찾을 수 없습니다.")

            # 2. 새 영상만 보기 토글 활성화
            self.logger.info("새 영상만 보기 토글 활성화 중...")

            # bg-gray-200가 있는 div는 꺼진 상태이므로, 이를 클릭하면 켜집니다
            toggle_selectors = [
                'div.bg-gray-200',  # 꺼진 상태의 토글
                'div[class*="bg-gray-200"]',  # 클래스에 bg-gray-200가 포함된 경우
            ]

            # 토글 컨테이너 찾기 (부모 요소에서 찾기)
            toggle_found = False
            for selector in toggle_selectors:
                try:
                    toggles = page.locator(selector).all()
                    for toggle in toggles[:5]:  # 최대 5개까지만 확인
                        try:
                            if toggle.is_visible(timeout=1000):
                                # 토글 클릭
                                toggle.click()
                                self.logger.info("새 영상만 보기 토글 활성화 완료")
                                toggle_found = True
                                page.wait_for_timeout(500)
                                break
                        except Exception:
                            continue
                    if toggle_found:
                        break
                except Exception:
                    continue

            if not toggle_found:
                self.logger.warning("새 영상만 보기 토글을 찾을 수 없습니다.")

            random_delay(0.5, 1.0)
            self.logger.info("필터 설정 완료")

        except Exception as e:
            self.logger.warning(f"필터 설정 중 오류: {e}")

    def keep_browser_open(self) -> None:
        """
        브라우저를 열어둔 상태로 유지
        사용자가 직접 닫을 때까지 대기
        """
        if self.browser_manager is None:
            self.logger.warning("브라우저가 시작되지 않았습니다.")
            return

        self.logger.info("=" * 60)
        self.logger.info("브라우저가 열려있습니다.")
        self.logger.info("브라우저를 닫으려면 이 스크립트를 종료하거나 close()를 호출하세요.")
        self.logger.info("=" * 60)

        try:
            # 사용자가 종료할 때까지 대기
            while True:
                time.sleep(1)
                # 브라우저가 닫혔는지 확인
                try:
                    page = self.browser_manager.get_page()
                    # 페이지가 여전히 유효한지 확인
                    _ = page.url  # B018: 변수에 할당하여 사용
                except Exception:
                    self.logger.info("브라우저가 닫혔습니다.")
                    break
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 중단되었습니다.")

    def _parse_number(self, text: str) -> Optional[int]:
        """
        텍스트에서 숫자 추출 (예: "208.6만" -> 2086000, "8.0만" -> 80000)

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

    def _extract_reel_data(self, reel_card) -> Optional[ShortrendReelData]:
        """
        릴스 카드에서 데이터 추출 (최적화: JavaScript로 일괄 추출)

        Args:
            reel_card: 릴스 카드 Locator

        Returns:
            추출된 릴스 데이터, 실패 시 None
        """
        try:
            # JavaScript로 한 번에 모든 데이터 추출 (훨씬 빠름)
            # Locator를 DOM 요소로 변환
            element_handle = reel_card.element_handle()
            if not element_handle:
                return None

            extracted_data = element_handle.evaluate("""
                (card) => {
                    const data = {};

                    // 썸네일 이미지 URL (여러 방법 시도)
                    let thumbnail = null;

                    // 방법 1: data-image-url 속성 (가장 확실)
                    const container = card.querySelector('div[data-image-url]');
                    if (container) {
                        thumbnail = container.getAttribute('data-image-url');
                    }

                    // 방법 2: img[alt="릴스 썸네일"]
                    if (!thumbnail) {
                        const img = card.querySelector('img[alt="릴스 썸네일"]');
                        if (img && img.src) {
                            thumbnail = img.src;
                        }
                    }

                    // 방법 3: img 태그에서 cdninstagram 포함된 것
                    if (!thumbnail) {
                        const imgs = card.querySelectorAll('img[src*="cdninstagram"]');
                        for (let img of imgs) {
                            if (img.src && img.src.includes('cdninstagram')) {
                                thumbnail = img.src;
                                break;
                            }
                        }
                    }

                    // 썸네일이 없으면 null 반환
                    if (!thumbnail) return null;

                    data.thumbnail_url = thumbnail;

                    // 랭킹 정보
                    const rankBadge = Array.from(card.querySelectorAll('div'))
                        .find(d => d.textContent && d.textContent.includes('TOP'));
                    if (rankBadge) {
                        data.rank = rankBadge.textContent.trim();
                        const rankMatch = data.rank.match(/TOP\\s*(\\d+)/);
                        if (rankMatch) {
                            data.rank_number = parseInt(rankMatch[1]);
                        }
                    }

                    // 날짜
                    const dateElem = Array.from(card.querySelectorAll('div')).find(d => {
                        const classes = d.className || '';
                        return (
                            classes.includes('bg-black') &&
                            d.textContent &&
                            d.textContent.includes('월')
                        );
                    });
                    if (dateElem) {
                        data.date = dateElem.textContent.trim();
                    }

                    // 증가율
                    const growthBadge = Array.from(card.querySelectorAll('div')).find(
                        d =>
                            d.textContent &&
                            d.textContent.includes('+') &&
                            d.textContent.includes('%')
                    );
                    if (growthBadge) {
                        data.growth_rate = growthBadge.textContent.trim();
                    }

                    // 통계 정보 (조회수, 좋아요, 댓글)
                    const stats = Array.from(
                        card.querySelectorAll('div.flex.flex-col.items-center')
                    );
                    stats.slice(0, 3).forEach((stat, i) => {
                        const mainSpan = stat.querySelector('span.text-xs.font-medium');
                        if (mainSpan) {
                            const mainText = mainSpan.textContent.trim();
                            const mainNum =
                                parseFloat(mainText.replace(/[^\\d.]/g, '')) || 0;
                            const keys = ['views', 'likes', 'comments'];
                            if (mainText.includes('만')) {
                                data[keys[i]] = Math.floor(mainNum * 10000);
                            } else if (mainText.includes('천')) {
                                data[keys[i]] = Math.floor(mainNum * 1000);
                            } else {
                                data[keys[i]] = Math.floor(mainNum);
                            }

                            // 변화율 (모든 span에서 찾기)
                            const allSpans = Array.from(stat.querySelectorAll('span'));
                            allSpans.forEach((span, idx) => {
                                const text = span.textContent.trim();
                                if (text === '일' || text === '주') {
                                    const nextSpan = allSpans[idx + 1];
                                    if (nextSpan) {
                                        const changeText = nextSpan.textContent.trim();
                                        const dailyKeys = [
                                            'views_daily_change',
                                            'likes_daily_change',
                                            'comments_daily_change',
                                        ];
                                        const weeklyKeys = [
                                            'views_weekly_change',
                                            'likes_weekly_change',
                                            'comments_weekly_change',
                                        ];
                                        if (text === '일') {
                                            data[dailyKeys[i]] = changeText;
                                        } else if (text === '주') {
                                            data[weeklyKeys[i]] = changeText;
                                        }
                                    }
                                }
                            });
                        }
                    });

                    // 작성자 정보
                    const usernameSpan = Array.from(
                        card.querySelectorAll('span.text-sm.font-medium')
                    ).find(s => s.textContent && s.textContent.includes('@'));
                    if (usernameSpan) {
                        data.author_username = usernameSpan.textContent.trim();
                    }

                    const displayNameSpan = card.querySelector(
                        'span.text-xs.text-gray-500'
                    );
                    if (displayNameSpan) {
                        data.author_display_name = displayNameSpan.textContent.trim();
                    }

                    const followersSpan = Array.from(
                        card.querySelectorAll('span.bg-gray-100')
                    ).find(s => s.textContent && s.textContent.includes('만'));
                    if (followersSpan) {
                        const followersText = followersSpan.textContent.trim();
                        const followersNum = parseFloat(followersText.replace(/[^\\d.]/g, '')) || 0;
                        if (followersText.includes('만')) {
                            data.author_followers = Math.floor(followersNum * 10000);
                        } else if (followersText.includes('천')) {
                            data.author_followers = Math.floor(followersNum * 1000);
                        } else {
                            data.author_followers = Math.floor(followersNum);
                        }
                    }

                    // 제목/캡션
                    const titleElem = card.querySelector('p.text-sm.font-bold.line-clamp-2');
                    if (titleElem) {
                        data.title = titleElem.textContent.trim();
                    }

                    // 영상 길이
                    const durationElem = Array.from(card.querySelectorAll('div')).find(d => {
                        const classes = d.className || '';
                        return (
                            classes.includes('bg-black') &&
                            d.textContent &&
                            d.textContent.includes(':')
                        );
                    });
                    if (durationElem) {
                        data.duration = durationElem.textContent.trim();
                    }

                    // Instagram 링크
                    const instagramLink = card.querySelector('a[href*="instagram.com"]');
                    if (instagramLink) {
                        data.instagram_link = instagramLink.getAttribute('href');
                    }

                    return data;
                }
            """)

            if not extracted_data or not extracted_data.get('thumbnail_url'):
                return None

            # JavaScript에서 추출한 데이터를 모델로 변환
            data = ShortrendReelData(
                thumbnail_url=extracted_data.get('thumbnail_url'),
                rank=extracted_data.get('rank'),
                rank_number=extracted_data.get('rank_number'),
                date=extracted_data.get('date'),
                growth_rate=extracted_data.get('growth_rate'),
                views=extracted_data.get('views'),
                views_daily_change=extracted_data.get('views_daily_change'),
                views_weekly_change=extracted_data.get('views_weekly_change'),
                likes=extracted_data.get('likes'),
                likes_daily_change=extracted_data.get('likes_daily_change'),
                likes_weekly_change=extracted_data.get('likes_weekly_change'),
                comments=extracted_data.get('comments'),
                comments_daily_change=extracted_data.get('comments_daily_change'),
                comments_weekly_change=extracted_data.get('comments_weekly_change'),
                author_username=extracted_data.get('author_username'),
                author_display_name=extracted_data.get('author_display_name'),
                author_followers=extracted_data.get('author_followers'),
                title=extracted_data.get('title'),
                duration=extracted_data.get('duration'),
                instagram_link=extracted_data.get('instagram_link'),
            )

            return data

        except Exception as e:
            self.logger.debug(f"릴스 데이터 추출 실패: {e}")
            return None

    def collect_reels(self, max_count: int = 100) -> list[ShortrendReelData]:
        """
        무한 스크롤로 릴스 수집

        Args:
            max_count: 최대 수집 개수 (기본: 100)

        Returns:
            수집된 릴스 데이터 리스트

        Raises:
            ScrapingError: 수집 실패 시
        """
        try:
            if self.browser_manager is None:
                raise ScrapingError("브라우저가 시작되지 않았습니다. 먼저 로그인하세요.")

            page = self.browser_manager.get_page()
            self.logger.info(f"릴스 수집 시작 (최대 {max_count}개)...")

            # 페이지 로딩 대기
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            random_delay(1.0, 2.0)

            collected_reels: list[ShortrendReelData] = []
            collected_thumbnails: set[str] = set()  # 중복 체크용

            # 릴스 카드 컨테이너 찾기 (여러 셀렉터 시도)
            reel_container_selectors = [
                'div.relative > div.bg-white.rounded-xl',
                'div.bg-white.rounded-xl.shadow-md',
                'div.relative',
            ]

            reel_cards = []
            for selector in reel_container_selectors:
                try:
                    cards = page.locator(selector).all()
                    if len(cards) > 0:
                        reel_cards = cards
                        self.logger.info(f"릴스 카드 컨테이너 찾음: {selector} ({len(cards)}개)")
                        break
                except Exception:
                    continue

            if not reel_cards:
                raise ScrapingError("릴스 카드 컨테이너를 찾을 수 없습니다.")

            last_count = 0
            no_change_count = 0
            max_no_change = 5  # 5번 연속 변화 없으면 종료

            while len(collected_reels) < max_count:
                # 현재 보이는 릴스 카드 수 확인
                reel_cards = page.locator(reel_container_selectors[0]).all()
                current_count = len(reel_cards)

                self.logger.info(
                    f"현재 로드된 릴스: {current_count}개, "
                    f"수집된 릴스: {len(collected_reels)}개"
                )

                # 새로운 카드가 로드되었는지 확인
                if current_count == last_count:
                    no_change_count += 1
                    if no_change_count >= max_no_change:
                        self.logger.warning("더 이상 새로운 릴스가 로드되지 않습니다.")
                        break
                else:
                    no_change_count = 0

                last_count = current_count

                # 각 릴스 카드에서 데이터 추출
                for i, reel_card in enumerate(reel_cards):
                    try:
                        # 데이터 추출
                        reel_data = self._extract_reel_data(reel_card)

                        if reel_data and reel_data.thumbnail_url:
                            # 중복 체크
                            if reel_data.thumbnail_url not in collected_thumbnails:
                                collected_reels.append(reel_data)
                                collected_thumbnails.add(reel_data.thumbnail_url)
                                thumb_preview = (
                                    reel_data.thumbnail_url[:50]
                                    if len(reel_data.thumbnail_url) > 50
                                    else reel_data.thumbnail_url
                                )
                                self.logger.info(
                                    f"수집 완료: {len(collected_reels)}/{max_count} - "
                                    f"@{reel_data.author_username or 'unknown'} "
                                    f"(썸네일: {thumb_preview}...)"
                                )

                                if len(collected_reels) >= max_count:
                                    break
                            else:
                                thumb_preview = (
                                    reel_data.thumbnail_url[:50]
                                    if len(reel_data.thumbnail_url) > 50
                                    else reel_data.thumbnail_url
                                )
                                self.logger.debug(f"중복 릴스 건너뜀: {thumb_preview}...")
                        else:
                            # 디버깅: 첫 번째 카드의 HTML 저장
                            if i == 0 and len(collected_reels) == 0:
                                try:
                                    html = reel_card.inner_html()
                                    debug_dir = self.config.output_dir / "debug"
                                    debug_dir.mkdir(parents=True, exist_ok=True)
                                    debug_file = debug_dir / "reel_card_sample.html"
                                    with open(debug_file, "w", encoding="utf-8") as f:
                                        f.write(html)
                                    self.logger.warning(
                                        f"릴스 {i} 데이터 추출 실패 (썸네일 없음). "
                                        f"샘플 HTML 저장: {debug_file}"
                                    )
                                except Exception:
                                    pass
                            else:
                                self.logger.debug(f"릴스 {i} 데이터 추출 실패 (썸네일 없음)")

                    except Exception as e:
                        self.logger.warning(f"릴스 {i} 추출 중 오류: {e}")
                        continue

                # 목표 개수에 도달했는지 확인
                if len(collected_reels) >= max_count:
                    break

                # 스크롤 다운
                self.logger.info("스크롤 다운 중...")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                # 새 콘텐츠 로딩 대기 (시간 단축)
                page.wait_for_timeout(1000)  # 2초 -> 1초로 단축

            self.logger.info(f"릴스 수집 완료: {len(collected_reels)}개")
            return collected_reels

        except Exception as e:
            self.logger.error(f"릴스 수집 실패: {e}")
            raise ScrapingError(f"릴스 수집에 실패했습니다: {e}") from e

    def save_to_json(self, data: list[ShortrendReelData], filename: Optional[str] = None) -> Path:
        """
        데이터를 JSON 파일로 저장

        Args:
            data: 저장할 데이터
            filename: 파일명 (None이면 자동 생성)

        Returns:
            저장된 파일 경로
        """
        import json

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"shortrend_reels_{timestamp}.json"

        filepath = self.config.output_dir / filename

        try:
            self.logger.info(f"데이터 저장 중: {filepath}")
            # Pydantic 모델을 dict로 변환
            data_dict = [item.model_dump(mode="json", exclude_none=True) for item in data]

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)

            self.logger.info(f"데이터 저장 완료: {len(data)}개 항목")
            return filepath
        except Exception as e:
            self.logger.error(f"데이터 저장 실패: {e}")
            raise InstagramScraperError(f"데이터 저장에 실패했습니다: {e}") from e

    def close(self) -> None:
        """브라우저 종료"""
        if self.browser_manager:
            self.browser_manager.close()
            self.browser_manager = None
            self.logger.info("브라우저 종료 완료")

