"""
썸네일 S3 아카이빙 모듈

Instagram CDN URL(만료됨)을 다운로드하여 S3에 webp 압축 저장.
저장 경로: instagram/thumbnails/{country_code}/{reel_id}.webp
           instagram/profiles/{username}.webp
"""

import io
from typing import TYPE_CHECKING

import requests
from PIL import Image

from .utils.logger import get_logger

if TYPE_CHECKING:
    import boto3 as boto3_type

logger = get_logger(__name__)

# 썸네일 최대 크기 (px) — 가로/세로 중 긴 쪽 기준
_MAX_SIZE = 500
# webp 압축 품질 (0~100)
_WEBP_QUALITY = 85
# CDN 다운로드 타임아웃 (초)
_DOWNLOAD_TIMEOUT = 10
# S3 경로 prefix
_S3_PREFIX = "instagram"


class ThumbnailArchiver:
    """Instagram CDN URL → S3 webp 압축 저장"""

    def __init__(self, bucket: str, region: str, access_key: str, secret_key: str) -> None:
        import boto3

        self._bucket = bucket
        self._s3: boto3_type.client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self._base_url = f"https://{bucket}.s3.{region}.amazonaws.com"

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def archive_reel_thumbnail(
        self, reel_id: str, cdn_url: str, country_code: str
    ) -> str:
        """
        릴스 썸네일 CDN URL → S3 저장.

        Returns:
            S3 URL (성공) 또는 원본 cdn_url (실패 시 fallback)
        """
        key = f"{_S3_PREFIX}/thumbnails/{country_code}/{reel_id}.webp"
        return self._upload_image(cdn_url, key, label=f"reel/{reel_id}") or cdn_url

    def archive_profile_image(self, username: str, cdn_url: str) -> str:
        """
        크리에이터 프로필 이미지 CDN URL → S3 저장.

        Returns:
            S3 URL (성공) 또는 원본 cdn_url (실패 시 fallback)
        """
        key = f"{_S3_PREFIX}/profiles/{username}.webp"
        return self._upload_image(cdn_url, key, label=f"profile/{username}") or cdn_url

    def batch_archive(
        self,
        reels: list,  # list[ReelData] — 순환 import 방지를 위해 Any 사용
        country_code: str,
    ) -> tuple[list, int]:
        """
        수집된 릴스 리스트에 대해 일괄 썸네일/프로필 아카이빙.

        Returns:
            (업데이트된 reels 리스트, 성공 건수)
        """
        success = 0
        seen_authors: dict[str, str] = {}  # username → s3_url (프로필 중복 업로드 방지)

        for reel in reels:
            reel_id = _extract_reel_id(str(reel.link)) if reel.link else None

            # 썸네일
            if reel.thumbnail and reel_id:
                new_url = self.archive_reel_thumbnail(reel_id, reel.thumbnail, country_code)
                if new_url != reel.thumbnail:
                    reel.thumbnail = new_url
                    success += 1

            # 프로필 이미지 (크리에이터별 1회만)
            if reel.creator_profile_image and reel.author:
                if reel.author not in seen_authors:
                    new_url = self.archive_profile_image(reel.author, reel.creator_profile_image)
                    seen_authors[reel.author] = new_url
                reel.creator_profile_image = seen_authors[reel.author]

        logger.info(f"[S3] 썸네일 아카이빙 완료: {success}/{len(reels)}건 성공 (country={country_code})")
        return reels, success

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _upload_image(self, cdn_url: str, s3_key: str, label: str) -> str | None:
        """
        CDN URL 다운로드 → webp 변환 → S3 업로드.

        Returns:
            S3 public URL (성공) 또는 None (실패)
        """
        try:
            webp_bytes = self._download_and_convert(cdn_url)
            if webp_bytes is None:
                return None

            self._s3.put_object(
                Bucket=self._bucket,
                Key=s3_key,
                Body=webp_bytes,
                ContentType="image/webp",
            )
            s3_url = f"{self._base_url}/{s3_key}"
            logger.debug(f"[S3] 업로드 완료: {label} → {s3_url}")
            return s3_url

        except Exception as e:
            logger.warning(f"[S3] 업로드 실패 ({label}): {e}")
            return None

    def _download_and_convert(self, cdn_url: str) -> bytes | None:
        """CDN URL 다운로드 → webp bytes 변환."""
        try:
            resp = requests.get(cdn_url, timeout=_DOWNLOAD_TIMEOUT, stream=True)
            resp.raise_for_status()

            img = Image.open(io.BytesIO(resp.content)).convert("RGB")

            # 최대 크기 리사이즈 (비율 유지)
            img.thumbnail((_MAX_SIZE, _MAX_SIZE), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=_WEBP_QUALITY)
            return buf.getvalue()

        except Exception as e:
            logger.warning(f"[S3] 이미지 변환 실패 ({cdn_url[:60]}...): {e}")
            return None


def _extract_reel_id(link: str) -> str | None:
    """링크에서 reel_id(shortcode) 추출."""
    import re
    match = re.search(r"/reels?/([^/?#]+)/?", link)
    return match.group(1) if match else None


def build_archiver_from_config(config) -> ThumbnailArchiver | None:
    """
    ScrapingConfig에서 ThumbnailArchiver 생성.
    S3_ENABLED=false 이거나 설정 미완성이면 None 반환.
    """
    if not config.s3_enabled:
        return None
    if not all([config.s3_bucket, config.aws_access_key_id, config.aws_secret_access_key]):
        logger.warning("[S3] 설정이 불완전합니다 (S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 확인)")
        return None
    return ThumbnailArchiver(
        bucket=config.s3_bucket,
        region=config.aws_region,
        access_key=config.aws_access_key_id,
        secret_key=config.aws_secret_access_key,
    )
