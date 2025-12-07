"""
대기 유틸리티
웹 페이지 로딩 및 요소 대기를 위한 유틸리티 함수
"""

from typing import Optional

from playwright.sync_api import Locator, Page

from .logger import get_logger

logger = get_logger(__name__)


def wait_for_page_load(page: Page, timeout: int = 30000) -> None:
    """
    페이지가 완전히 로드될 때까지 대기

    Args:
        page: Playwright Page 객체
        timeout: 타임아웃 (밀리초)
    """
    try:
        # 네트워크가 안정될 때까지 대기
        page.wait_for_load_state("networkidle", timeout=timeout)
        # DOM이 로드될 때까지 대기
        page.wait_for_load_state("domcontentloaded", timeout=timeout)
        logger.debug("페이지 로드 완료")
    except Exception as e:
        logger.warning(f"페이지 로드 대기 중 오류 (계속 진행): {e}")


def wait_for_element(
    page: Page,
    selectors: list[str],
    timeout: int = 5000,
    state: str = "visible",  # type: ignore[assignment]
    description: str = "요소",
) -> Optional[Locator]:
    """
    여러 셀렉터 중 하나가 나타날 때까지 대기

    Args:
        page: Playwright Page 객체
        selectors: 시도할 셀렉터 리스트
        timeout: 각 셀렉터당 타임아웃 (밀리초)
        state: 대기할 상태 ("visible", "attached", "hidden")
        description: 요소 설명 (로깅용)

    Returns:
        찾은 Locator 객체, 없으면 None
    """
    for selector in selectors:
        try:
            logger.debug(f"{description} 찾는 중: {selector}")
            page.wait_for_selector(selector, timeout=timeout, state=state)
            locator = page.locator(selector).first
            locator.wait_for(state=state, timeout=2000)

            if state == "visible" and locator.is_visible():
                logger.info(f"{description} 찾음: {selector}")
                return locator
            elif state != "visible":
                logger.info(f"{description} 찾음: {selector}")
                return locator
        except Exception as e:
            logger.debug(f"셀렉터 실패: {selector} - {e}")
            continue

    logger.error(f"{description}을(를) 찾을 수 없습니다.")
    return None


def safe_fill_input(locator: Locator, value: str, description: str = "입력 필드") -> bool:
    """
    입력 필드에 안전하게 값 입력

    Args:
        locator: 입력 필드 Locator
        value: 입력할 값
        description: 필드 설명 (로깅용)

    Returns:
        입력 성공 여부
    """
    try:
        # 클릭하여 포커스
        locator.click()
        locator.page.wait_for_timeout(300)

        # 기존 내용 지우기
        locator.clear()
        locator.page.wait_for_timeout(200)

        # 값 입력
        locator.fill(value, timeout=5000)
        locator.page.wait_for_timeout(500)

        # 입력 확인
        input_value = locator.input_value()
        if input_value == value or (description == "비밀번호" and len(input_value) == len(value)):
            logger.info(f"{description} 입력 완료")
            return True
        else:
            logger.warning(f"{description} 입력값 불일치. 재시도...")
            locator.clear()
            locator.fill(value)
            locator.page.wait_for_timeout(500)
            return True
    except Exception as e:
        logger.error(f"{description} 입력 실패: {e}")
        return False
