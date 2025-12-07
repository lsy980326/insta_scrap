"""
로깅 유틸리티
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """
    로거 설정

    Args:
        log_level: 로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로 (None이면 파일 로깅 안 함)
        rotation: 로그 파일 회전 크기
        retention: 로그 파일 보관 기간
    """
    # 기본 로거 제거
    logger.remove()

    # 콘솔 출력 설정
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True,
    )

    # 파일 출력 설정 (선택)
    if log_file and str(log_file).strip():
        try:
            log_path = Path(log_file)
            # 디렉토리가 아닌 파일 경로인지 확인
            if log_path.suffix or log_path.name:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                logger.add(
                    log_path,
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                    level=log_level,
                    rotation=rotation,
                    retention=retention,
                    encoding="utf-8",
                )
        except (ValueError, OSError) as e:
            # 로그 파일 생성 실패 시 콘솔만 사용
            logger.warning(f"로그 파일 생성 실패, 콘솔만 사용: {e}")


def get_logger(name: str = __name__):
    """
    로거 인스턴스 반환

    Args:
        name: 로거 이름

    Returns:
        로거 인스턴스
    """
    return logger.bind(name=name)
