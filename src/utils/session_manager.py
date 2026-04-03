"""
세션 관리 유틸리티
인스타그램 계정 세션(쿠키, User-Agent) 저장 및 로드
"""

import json
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

from ..config import ScrapingConfig
from ..database import get_db_session
from ..database.repositories import AccountSessionRepository
from .logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """세션 관리 클래스 (DB 및 파일 저장 지원)"""

    def __init__(self, config: ScrapingConfig) -> None:
        """
        초기화

        Args:
            config: 스크래핑 설정 객체
        """
        self.config = config
        self.session_storage_type = getattr(config, "session_storage_type", "db")
        self.session_file_dir = getattr(config, "session_file_dir", Path("sessions"))

    def load_session(self, account_id: str) -> dict | None:
        """
        세션 데이터 로드 (쿠키 + User-Agent)

        Args:
            account_id: Instagram username

        Returns:
            세션 데이터 딕셔너리 (cookies, user_agent) 또는 None
        """
        if self.session_storage_type == "db" and self.config.db_enabled:
            return self._load_from_db(account_id)
        else:
            return self._load_from_file(account_id)

    def save_session(self, account_id: str, cookies: list, user_agent: str) -> None:
        """
        세션 데이터 저장 (쿠키 + User-Agent)

        Args:
            account_id: Instagram username
            cookies: Playwright 쿠키 리스트
            user_agent: User-Agent 문자열

        Raises:
            ValueError: user_agent가 없을 경우
        """
        if not user_agent:
            raise ValueError("User-Agent는 필수입니다")

        if self.session_storage_type == "db" and self.config.db_enabled:
            self._save_to_db(account_id, cookies, user_agent)
        else:
            self._save_to_file(account_id, cookies, user_agent)

    def verify_session(self, page: Page, account_id: str | None = None) -> bool:
        """
        세션 유효성 검증

        Args:
            page: Playwright Page 객체
            account_id: Instagram username (선택, 프로필 페이지 검증 시 사용)

        Returns:
            세션이 유효하면 True, 아니면 False
        """
        try:
            # 세션 검증 URL — 로그인 필수 페이지 사용 (프로필 페이지는 비로그인도 접근 가능하여 오판 발생)
            verify_url = "https://www.instagram.com/accounts/edit/"

            logger.info(f"세션 검증 중: {verify_url}")
            page.goto(verify_url, wait_until="domcontentloaded", timeout=10000)

            # 로그인 페이지로 리다이렉트되면 세션 무효
            if "accounts/login" in page.url:
                logger.warning("세션 검증 실패: 로그인 페이지로 리다이렉트됨")
                return False

            # 프로필/설정 페이지가 로드되면 세션 유효
            logger.info("✅ 세션 검증 성공")
            return True

        except Exception as e:
            logger.warning(f"세션 검증 중 오류 발생: {e}")
            return False

    def extract_session_data(self, context: BrowserContext) -> dict:
        """
        브라우저 컨텍스트에서 세션 데이터 추출

        Args:
            context: Playwright BrowserContext 객체

        Returns:
            세션 데이터 딕셔너리 (cookies, user_agent)
        """
        cookies = context.cookies()
        # User-Agent는 페이지에서 추출
        page = context.new_page()
        try:
            user_agent = page.evaluate("navigator.userAgent")
        finally:
            page.close()

        return {
            "cookies": cookies,
            "user_agent": user_agent,
        }

    def _load_from_db(self, account_id: str) -> dict | None:
        """DB에서 세션 로드"""
        try:
            session_gen = get_db_session()
            session = next(session_gen)
            try:
                repo = AccountSessionRepository(session)
                account_session = repo.find_by_account_id(account_id)

                if account_session and account_session.is_valid:
                    logger.info(f"✅ DB에서 세션 로드 성공: {account_id}")
                    return {
                        "cookies": account_session.cookies,
                        "user_agent": account_session.user_agent,
                    }
                else:
                    logger.info(f"세션 없음 또는 무효: {account_id}")
                    return None
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"DB에서 세션 로드 실패: {e}")
            return None

    def _save_to_db(self, account_id: str, cookies: list, user_agent: str) -> None:
        """DB에 세션 저장"""
        try:
            session_gen = get_db_session()
            session = next(session_gen)
            try:
                repo = AccountSessionRepository(session)
                repo.create_or_update(account_id, cookies, user_agent, is_valid=True)
                session.commit()
                logger.info(f"✅ DB에 세션 저장 성공: {account_id}")
            except Exception as e:
                session.rollback()
                logger.error(f"DB에 세션 저장 실패: {e}")
                raise
            finally:
                session.close()
        except Exception as e:
            logger.error(f"DB 세션 저장 중 오류: {e}")

    def _load_from_file(self, account_id: str) -> dict | None:
        """파일에서 세션 로드"""
        try:
            session_file = self.session_file_dir / f"{account_id}.json"
            if not session_file.exists():
                logger.info(f"세션 파일 없음: {session_file}")
                return None

            with open(session_file, encoding="utf-8") as f:
                data = json.load(f)

            if data.get("is_valid", True):
                logger.info(f"✅ 파일에서 세션 로드 성공: {account_id}")
                return {
                    "cookies": data.get("cookies", []),
                    "user_agent": data.get("user_agent", ""),
                }
            else:
                logger.info(f"세션 파일이 무효로 표시됨: {account_id}")
                return None

        except Exception as e:
            logger.warning(f"파일에서 세션 로드 실패: {e}")
            return None

    def _save_to_file(self, account_id: str, cookies: list, user_agent: str) -> None:
        """파일에 세션 저장"""
        try:
            # 세션 디렉토리 생성
            self.session_file_dir.mkdir(parents=True, exist_ok=True)

            session_file = self.session_file_dir / f"{account_id}.json"
            data = {
                "account_id": account_id,
                "cookies": cookies,
                "user_agent": user_agent,
                "is_valid": True,
                "saved_at": None,  # JSON 직렬화를 위해 None (필요시 datetime 사용)
            }

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ 파일에 세션 저장 성공: {session_file}")

        except Exception as e:
            logger.error(f"파일에 세션 저장 실패: {e}")

