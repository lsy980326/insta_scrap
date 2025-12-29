"""
mitmproxy 스크립트: SSL 오류 시 우회 모드

인스타그램 관련 트래픽만 캡처하고,
SSL 오류가 발생하면 해당 연결을 우회합니다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from mitmproxy import http, connection


# 출력 디렉토리 설정
OUTPUT_DIR = Path("output/mitmproxy_capture")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_data(url: str, data: Any, response_type: str = "json") -> None:
    """캡처한 데이터를 파일로 저장"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        domain = url.split("/")[2] if "/" in url else "unknown"
        domain = domain.replace(".", "_")
        filename = f"{domain}_{timestamp}.{response_type}"
        filepath = OUTPUT_DIR / filename
        
        if response_type == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(data))
        
        print(f"[✓] 데이터 저장: {filepath}")
    except Exception as e:
        print(f"[✗] 데이터 저장 실패: {e}")


def server_connect(conn: connection.ServerConnection) -> None:
    """
    서버 연결 시 SSL 오류 처리
    
    SSL 오류가 발생하면 연결을 허용하여 우회합니다.
    """
    # 인스타그램 관련 도메인만 처리
    if "instagram.com" in conn.address[0] or "facebook.com" in conn.address[0]:
        # SSL 검증 오류 무시 (주의: 보안상 프로덕션에서는 사용하지 마세요)
        conn.ignore_ssl_errors = True


def response(flow: http.HTTPFlow) -> None:
    """HTTP 응답을 가로채서 처리"""
    url = flow.request.pretty_url
    host = flow.request.pretty_host
    
    # 인스타그램 관련 API 감지
    instagram_keywords = [
        "graph.instagram.com",
        "i.instagram.com",
        "clips/discover",
        "feed/timeline",
        "api/v1/feed",
        "stories/reel",
        "media/",
        "reels/",
    ]
    
    is_instagram = any(keyword in url or keyword in host for keyword in instagram_keywords)
    
    if not is_instagram:
        return
    
    try:
        response_text = flow.response.text
        
        if not response_text:
            return
        
        try:
            data = json.loads(response_text)
            
            print(f"\n{'='*60}")
            print(f"[*] 인스타그램 데이터 발견!")
            print(f"    URL: {url}")
            print(f"    Host: {host}")
            print(f"    Status: {flow.response.status_code}")
            
            if isinstance(data, dict):
                if "items" in data:
                    items_count = len(data.get("items", []))
                    print(f"    Items: {items_count}개")
            
            print(f"{'='*60}\n")
            
            save_data(url, data, "json")
            
        except json.JSONDecodeError:
            print(f"\n[*] 텍스트 데이터 발견: {url}")
            save_data(url, response_text, "txt")
            
    except Exception as e:
        print(f"[✗] 응답 처리 중 오류: {e}")


def request(flow: http.HTTPFlow) -> None:
    """HTTP 요청 로깅"""
    url = flow.request.pretty_url
    host = flow.request.pretty_host
    
    if "instagram.com" in host or "graph.instagram.com" in host:
        print(f"[→] 요청: {flow.request.method} {url}")


def start() -> None:
    """mitmproxy 시작 시 호출"""
    print("\n" + "="*60)
    print("인스타그램 트래픽 캡처 시작 (SSL 우회 모드)")
    print("="*60)
    print(f"출력 디렉토리: {OUTPUT_DIR.absolute()}")
    print("="*60 + "\n")


def done() -> None:
    """mitmproxy 종료 시 호출"""
    print("\n" + "="*60)
    print("인스타그램 트래픽 캡처 종료")
    print(f"저장된 파일: {OUTPUT_DIR.absolute()}")
    print("="*60 + "\n")

