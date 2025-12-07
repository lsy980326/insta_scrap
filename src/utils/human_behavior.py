"""
사용자 행동 시뮬레이션 유틸리티
실제 사용자처럼 보이게 하기 위한 마우스 움직임, 스크롤 등의 시뮬레이션
"""

import random
import time

from playwright.sync_api import Locator, Page

from .logger import get_logger

logger = get_logger(__name__)


def random_delay(min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
    """
    랜덤 딜레이 (사용자 행동 시뮬레이션)

    Args:
        min_seconds: 최소 대기 시간 (초)
        max_seconds: 최대 대기 시간 (초)
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def human_like_scroll(
    page: Page,
    scroll_pause_time: float = 1.0,
    scroll_amount: int = 500,
    direction: str = "down",
) -> None:
    """
    사람처럼 자연스럽게 스크롤

    Args:
        page: Playwright Page 객체
        scroll_pause_time: 스크롤 후 대기 시간 (초)
        scroll_amount: 한 번에 스크롤할 픽셀 수
        direction: 스크롤 방향 ("down" 또는 "up")
    """
    try:
        current_position = page.evaluate("window.pageYOffset")

        if direction == "down":
            target_position = current_position + scroll_amount
        else:
            target_position = max(0, current_position - scroll_amount)

        # 부드러운 스크롤 시뮬레이션
        steps = random.randint(3, 7)
        step_size = (target_position - current_position) / steps

        for i in range(steps):
            scroll_to = current_position + (step_size * (i + 1))
            page.evaluate(f"window.scrollTo(0, {scroll_to})")
            random_delay(0.1, 0.3)

        random_delay(scroll_pause_time, scroll_pause_time * 1.5)
        logger.debug(f"스크롤 완료: {direction} ({scroll_amount}px)")
    except Exception as e:
        logger.warning(f"스크롤 중 오류 (무시): {e}")


def human_like_click(locator: Locator, delay_before: float = 0.3, delay_after: float = 0.5) -> None:
    """
    사람처럼 자연스럽게 클릭 (마우스 움직임 시뮬레이션)

    Args:
        locator: 클릭할 요소의 Locator
        delay_before: 클릭 전 대기 시간 (초)
        delay_after: 클릭 후 대기 시간 (초)
    """
    try:
        # 요소로 마우스 이동
        locator.hover()
        random_delay(delay_before * 0.5, delay_before * 1.5)

        # 클릭
        locator.click()
        random_delay(delay_after * 0.5, delay_after * 1.5)

        logger.debug("클릭 완료 (사용자 행동 시뮬레이션)")
    except Exception as e:
        logger.warning(f"클릭 중 오류: {e}")
        raise


def random_mouse_movement(page: Page, duration: float = 0.5) -> None:
    """
    랜덤 마우스 움직임 시뮬레이션

    Args:
        page: Playwright Page 객체
        duration: 움직임 지속 시간 (초)
    """
    try:
        # 랜덤 위치로 마우스 이동
        viewport = page.viewport_size
        if viewport:
            x = random.randint(100, viewport["width"] - 100)
            y = random.randint(100, viewport["height"] - 100)
            page.mouse.move(x, y)
            random_delay(duration * 0.5, duration * 1.5)
            logger.debug(f"마우스 이동: ({x}, {y})")
    except Exception as e:
        logger.debug(f"마우스 이동 중 오류 (무시): {e}")


def simulate_typing(page: Page, selector: str, text: str, typing_delay: float = 0.1) -> None:
    """
    사람처럼 타이핑 시뮬레이션 (한 글자씩 입력)

    Args:
        page: Playwright Page 객체
        selector: 입력 필드 셀렉터
        text: 입력할 텍스트
        typing_delay: 글자 간 딜레이 (초)
    """
    try:
        locator = page.locator(selector).first
        locator.click()
        random_delay(0.2, 0.5)

        # 한 글자씩 입력
        for char in text:
            locator.type(char, delay=typing_delay * 1000)  # 밀리초로 변환
            random_delay(typing_delay * 0.5, typing_delay * 1.5)

        logger.debug(f"타이핑 완료: {len(text)}자")
    except Exception as e:
        logger.warning(f"타이핑 중 오류: {e}")
        raise


def simulate_page_interaction(page: Page, min_actions: int = 1, max_actions: int = 3) -> None:
    """
    페이지 상호작용 시뮬레이션 (스크롤, 마우스 움직임 등)

    Args:
        page: Playwright Page 객체
        min_actions: 최소 상호작용 횟수
        max_actions: 최대 상호작용 횟수
    """
    try:
        num_actions = random.randint(min_actions, max_actions)

        for _ in range(num_actions):
            action = random.choice(["scroll", "mouse"])

            if action == "scroll":
                human_like_scroll(
                    page, scroll_pause_time=0.5, scroll_amount=random.randint(200, 500)
                )
            elif action == "mouse":
                random_mouse_movement(page, duration=0.3)

            random_delay(0.5, 1.5)

        logger.debug(f"페이지 상호작용 완료: {num_actions}회")
    except Exception as e:
        logger.debug(f"페이지 상호작용 중 오류 (무시): {e}")
