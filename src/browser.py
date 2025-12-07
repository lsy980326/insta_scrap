"""
Playwright 브라우저 관리 모듈
"""

import platform
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .config import ScrapingConfig
from .exceptions import InstagramScraperError
from .utils.logger import get_logger


class BrowserManager:
    """Playwright 브라우저 관리 클래스"""

    def __init__(self, config: ScrapingConfig) -> None:
        """
        초기화

        Args:
            config: 스크래핑 설정 객체
        """
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self) -> None:
        """브라우저 시작"""
        try:
            self.logger.info("Playwright 브라우저 시작 중...")
            self.playwright = sync_playwright().start()

            # 실제 Chrome 실행 파일 경로 찾기 (Windows)
            chrome_executable_path = None
            if platform.system() == "Windows":
                possible_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
                ]
                for path in possible_paths:
                    if Path(path).exists():
                        chrome_executable_path = str(path)
                        self.logger.info(f"실제 Chrome 발견: {chrome_executable_path}")
                        break

            # 브라우저 타입 선택
            browser_type_map = {
                "chromium": self.playwright.chromium,
                "firefox": self.playwright.firefox,
                "webkit": self.playwright.webkit,
            }

            browser_type = browser_type_map.get(
                self.config.playwright_browser.lower(), self.playwright.chromium
            )

            # 봇 감지 우회를 위한 브라우저 인자 (더 강력한 스텔스 모드)
            browser_args = [
                "--disable-blink-features=AutomationControlled",  # 자동화 감지 비활성화
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-translate",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-domain-reliability",
                "--disable-component-extensions-with-background-pages",
                "--disable-default-apps",
                "--disable-sync",
                "--metrics-recording-only",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
                "--password-store=basic",
                "--use-mock-keychain",
                "--enable-automation=false",  # 자동화 비활성화
            ]

            # 브라우저 실행 옵션
            launch_options = {
                "headless": self.config.playwright_headless,
                "args": browser_args,
            }

            # 실제 Chrome 실행 파일이 있으면 사용
            if chrome_executable_path and self.config.playwright_browser.lower() == "chromium":
                launch_options["executable_path"] = chrome_executable_path
                self.logger.info("실제 Chrome 브라우저 사용 (봇 감지 우회 강화)")

            # 브라우저 실행
            self.browser = browser_type.launch(**launch_options)

            # 실제 사용자처럼 보이게 하는 User-Agent (최신 Chrome)
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )

            # 프록시 설정
            proxy_config = None
            if self.config.proxy_server:
                self.logger.info(f"프록시 사용: {self.config.proxy_server}")
                proxy_config = {
                    "server": self.config.proxy_server,
                }
                # 프록시 인증 정보가 있으면 추가
                if self.config.proxy_username and self.config.proxy_password:
                    proxy_config["username"] = self.config.proxy_username
                    proxy_config["password"] = self.config.proxy_password
                    self.logger.info("프록시 인증 정보 설정됨")

            # 컨텍스트 생성 옵션 준비
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": user_agent,
                "locale": "ko-KR",  # 한국어 로케일
                "timezone_id": "Asia/Seoul",  # 한국 시간대
                "permissions": ["geolocation", "notifications"],  # 권한 설정
                "color_scheme": "light",  # 다크모드 방지
                # 실제 사용자처럼 보이게 하는 추가 설정
                # 주의: CORS 정책을 위반하지 않도록 최소한의 헤더만 설정
                # Cache-Control과 같은 헤더는 CORS preflight 요청에서 문제를 일으킬 수 있음
                "extra_http_headers": {
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                },
                # JavaScript 실행 허용
                "java_script_enabled": True,
                # 이미지 로드 허용
                "ignore_https_errors": False,
            }

            # 프록시 설정이 있으면 추가
            if proxy_config:
                context_options["proxy"] = proxy_config

            # 컨텍스트 생성 (쿠키, 세션 등 관리)
            self.context = self.browser.new_context(**context_options)

            # 페이지 생성
            self.page = self.context.new_page()
            self.page.set_default_timeout(self.config.playwright_timeout)

            # 강화된 WebDriver 속성 제거 및 스텔스 모드 (봇 감지 우회)
            self.page.add_init_script(
                """
                // WebDriver 속성 완전 제거
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });

                // navigator.webdriver를 완전히 삭제
                delete navigator.__proto__.webdriver;

                // Chrome 객체 추가 (완전한 버전)
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };

                // Permissions API 수정
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // Plugins 배열 추가 (실제 플러그인처럼)
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        const plugins = [];
                        for (let i = 0; i < 5; i++) {
                            plugins.push({
                                0: { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                                description: 'Portable Document Format',
                                filename: 'internal-pdf-viewer',
                                length: 1,
                                name: 'Chrome PDF Plugin'
                            });
                        }
                        return plugins;
                    }
                });

                // Languages 설정
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en']
                });

                // Platform 설정
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });

                // Hardware concurrency 설정
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });

                // Device memory 설정
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });

                // Connection 설정
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                        saveData: false,
                        onchange: null,
                        addEventListener: function() {},
                        removeEventListener: function() {},
                        dispatchEvent: function() { return true; }
                    })
                });

                // Canvas fingerprinting 방지
                const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function() {
                    const context = this.getContext('2d');
                    if (context) {
                        const imageData = context.getImageData(0, 0, this.width, this.height);
                        for (let i = 0; i < imageData.data.length; i += 4) {
                            imageData.data[i] += Math.floor(Math.random() * 10) - 5;
                        }
                        context.putImageData(imageData, 0, 0);
                    }
                    return originalToDataURL.apply(this, arguments);
                };

                // WebGL fingerprinting 방지
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter.apply(this, arguments);
                };

                // AudioContext fingerprinting 방지
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (AudioContext) {
                    const originalCreateOscillator = AudioContext.prototype.createOscillator;
                    AudioContext.prototype.createOscillator = function() {
                        const oscillator = originalCreateOscillator.apply(this, arguments);
                        const originalFrequency = oscillator.frequency.value;
                        Object.defineProperty(oscillator.frequency, 'value', {
                            get: () => originalFrequency + Math.random() * 0.0001,
                            set: (val) => { oscillator.frequency.value = val; }
                        });
                        return oscillator;
                    };
                }

                // Notification 권한 설정
                const originalNotification = window.Notification;
                window.Notification = function(title, options) {
                    return new originalNotification(title, options);
                };
                window.Notification.permission = 'default';
                window.Notification.requestPermission = function() {
                    return Promise.resolve('default');
                };

                // Battery API 수정
                if (navigator.getBattery) {
                    navigator.getBattery = function() {
                        return Promise.resolve({
                            charging: true,
                            chargingTime: 0,
                            dischargingTime: Infinity,
                            level: 1.0,
                            onchargingchange: null,
                            onchargingtimechange: null,
                            ondischargingtimechange: null,
                            onlevelchange: null,
                            addEventListener: function() {},
                            removeEventListener: function() {},
                            dispatchEvent: function() { return true; }
                        });
                    };
                }
            """
            )

            self.logger.info(f"브라우저 시작 완료: {self.config.playwright_browser}")

        except Exception as e:
            self.logger.error(f"브라우저 시작 실패: {e}")
            raise InstagramScraperError(f"브라우저 시작에 실패했습니다: {e}") from e

    def close(self) -> None:
        """브라우저 종료"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()

            self.logger.info("브라우저 종료 완료")

        except Exception as e:
            self.logger.warning(f"브라우저 종료 중 오류: {e}")

    def get_page(self) -> Page:
        """
        현재 페이지 반환

        Returns:
            Playwright Page 객체

        Raises:
            InstagramScraperError: 브라우저가 시작되지 않은 경우
        """
        if self.page is None:
            raise InstagramScraperError("브라우저가 시작되지 않았습니다. start()를 먼저 호출하세요.")
        return self.page

    def __enter__(self) -> "BrowserManager":
        """컨텍스트 매니저 진입"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """컨텍스트 매니저 종료"""
        self.close()
