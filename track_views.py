"""
조회수 추적 실행 스크립트

사용 방법:
1. Poetry 사용 (권장):
   python -m poetry run python track_views.py [입력파일] [출력파일]

2. 가상 환경 활성화 후:
   python -m poetry shell
   python track_views.py [입력파일] [출력파일]

3. 직접 실행 (가상 환경 필요):
   python track_views.py [입력파일] [출력파일]

예시:
   python track_views.py output/reels_data_20260101_143155.json
   python track_views.py output/reels_data_20260101_143155.json output/reels_with_views.json
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.config import load_config
    from src.profile_loader import load_profile
    from src.views_tracker import ReelViewsTracker
    from src.utils.logger import setup_logger, get_logger
except ImportError as e:
    print("=" * 60)
    print("오류: 필요한 모듈을 찾을 수 없습니다.")
    print("=" * 60)
    print("\n해결 방법:")
    print("1. Poetry를 사용하여 실행하세요:")
    print("   python -m poetry run python track_views.py [입력파일]")
    print("\n2. 또는 가상 환경을 활성화한 후 실행하세요:")
    print("   python -m poetry shell")
    print("   python track_views.py [입력파일]")
    print("\n원본 오류:", str(e))
    print("=" * 60)
    sys.exit(1)


def main() -> None:
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Instagram Reels 조회수 추적")
    parser.add_argument("input_file", help="입력 JSON 파일 경로")
    parser.add_argument("output_file", nargs="?", help="출력 JSON 파일 경로 (선택)")
    parser.add_argument("--profile", "-p", help="계정 프로파일 (예: kr, jp)")
    args = parser.parse_args()

    # 설정 로드 (프로파일 우선)
    config = load_profile(args.profile) if args.profile else load_config()

    # 로거 설정
    setup_logger(
        log_level=config.log_level,
        log_file=config.log_file,
    )

    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("Instagram Reels 조회수 추적")
    logger.info("=" * 60)
    if args.profile:
        logger.info(f"프로파일: {args.profile} (계정: {config.instagram_username})")

    input_file = Path(args.input_file)
    output_file = Path(args.output_file) if args.output_file else None

    # 입력 파일 존재 확인
    if not input_file.exists():
        logger.error(f"입력 파일을 찾을 수 없습니다: {input_file}")
        sys.exit(1)

    logger.info(f"입력 파일: {input_file}")
    if output_file:
        logger.info(f"출력 파일: {output_file}")

    try:
        # 트래커 생성
        tracker = ReelViewsTracker(config=config)

        try:
            # 로그인 정보가 있으면 자동 로그인
            if config.instagram_username and config.instagram_password:
                logger.info("로그인 정보가 설정되어 있습니다. 로그인을 시도합니다...")
                try:
                    tracker.login()
                    logger.info("로그인 성공!")
                except Exception as e:
                    logger.warning(f"로그인 실패: {e}")
                    logger.warning("로그인 없이 계속 진행합니다. 일부 크리에이터의 reels 페이지는 접근할 수 없을 수 있습니다.")
            else:
                logger.warning("로그인 정보가 없습니다. 일부 크리에이터의 reels 페이지는 접근할 수 없을 수 있습니다.")

            # 조회수 추적 실행
            result_file = tracker.track_views(input_file, output_file)
            logger.info("=" * 60)
            logger.info(f"조회수 추적 완료!")
            logger.info(f"결과 파일: {result_file}")
            logger.info("=" * 60)

        except KeyboardInterrupt:
            logger.info("\n사용자에 의해 중단되었습니다.")
        except Exception as e:
            logger.error(f"조회수 추적 중 오류 발생: {e}")
            raise
        finally:
            # 브라우저 종료
            tracker.close()

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()

