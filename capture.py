"""
mitmproxy 스크립트: 인스타그램 앱의 네트워크 트래픽 캡처

사용법:
    mitmweb -s capture.py

또는 mitmdump로 실행:
    mitmdump -s capture.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from mitmproxy import http


# 출력 디렉토리 설정
OUTPUT_DIR = Path("output/mitmproxy_capture")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_data(url: str, data: Any, response_type: str = "json") -> None:
    """
    캡처한 데이터를 파일로 저장

    Args:
        url: 요청 URL
        data: 저장할 데이터
        response_type: 데이터 타입 (json, text 등)
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # URL에서 도메인 추출
        domain = url.split("/")[2] if "/" in url else "unknown"
        domain = domain.replace(".", "_")
        
        # 파일명 생성
        filename = f"{domain}_{timestamp}.{response_type}"
        filepath = OUTPUT_DIR / filename
        
        # 데이터 저장
        if response_type == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(data))
        
        print(f"[✓] 데이터 저장: {filepath}")
    except Exception as e:
        print(f"[✗] 데이터 저장 실패: {e}")


def response(flow: http.HTTPFlow) -> None:
    """
    HTTP 응답을 가로채서 처리

    Args:
        flow: HTTP 요청/응답 플로우
    """
    url = flow.request.pretty_url
    host = flow.request.pretty_host
    
    # 인스타그램 관련 API 감지
    instagram_keywords = [
        "graph.instagram.com",
        "i.instagram.com",
        "clips/discover",  # 릴스 탐색
        "feed/timeline",  # 피드 타임라인
        "api/v1/feed",  # 피드 API
        "stories/reel",  # 릴스 스토리
        "media/",  # 미디어 관련
        "reels/",  # 릴스 관련
    ]
    
    # 인스타그램 관련 요청인지 확인
    is_instagram = any(keyword in url or keyword in host for keyword in instagram_keywords)
    
    if not is_instagram:
        return
    
    try:
        # 응답 본문 가져오기
        response_text = flow.response.text
        
        if not response_text:
            return
        
        # JSON 데이터 파싱 시도
        try:
            data = json.loads(response_text)
            
            # 데이터 구조 확인 및 출력
            print(f"\n{'='*60}")
            print(f"[*] 인스타그램 데이터 발견!")
            print(f"    URL: {url}")
            print(f"    Host: {host}")
            print(f"    Status: {flow.response.status_code}")
            print(f"    Content-Type: {flow.response.headers.get('Content-Type', 'unknown')}")
            
            # 데이터 타입 확인
            if isinstance(data, dict):
                # items 키가 있으면 (피드/릴스 데이터)
                if "items" in data:
                    items_count = len(data.get("items", []))
                    print(f"    Items: {items_count}개")
                    
                    # 첫 번째 아이템 정보 출력
                    if items_count > 0:
                        first_item = data["items"][0]
                        print(f"    첫 번째 아이템 키: {list(first_item.keys())[:5]}")
                
                # 더 많은 정보 출력
                print(f"    데이터 키: {list(data.keys())[:10]}")
            
            # 데이터 미리보기 (처음 200자)
            preview = str(data)[:200]
            print(f"    미리보기: {preview}...")
            print(f"{'='*60}\n")
            
            # 데이터 저장
            save_data(url, data, "json")
            
        except json.JSONDecodeError:
            # JSON이 아닌 경우 텍스트로 저장
            print(f"\n[*] 텍스트 데이터 발견: {url}")
            print(f"    미리보기: {response_text[:200]}...")
            save_data(url, response_text, "txt")
            
    except Exception as e:
        print(f"[✗] 응답 처리 중 오류: {e}")


def request(flow: http.HTTPFlow) -> None:
    """
    HTTP 요청을 가로채서 로깅 (선택적)

    Args:
        flow: HTTP 요청/응답 플로우
    """
    url = flow.request.pretty_url
    host = flow.request.pretty_host
    
    # 인스타그램 관련 요청만 로깅
    if "instagram.com" in host or "graph.instagram.com" in host:
        print(f"[→] 요청: {flow.request.method} {url}")


# mitmproxy 이벤트 훅
def start() -> None:
    """mitmproxy 시작 시 호출"""
    print("\n" + "="*60)
    print("인스타그램 트래픽 캡처 시작")
    print("="*60)
    print(f"출력 디렉토리: {OUTPUT_DIR.absolute()}")
    print("="*60 + "\n")


def done() -> None:
    """mitmproxy 종료 시 호출"""
    print("\n" + "="*60)
    print("인스타그램 트래픽 캡처 종료")
    print(f"저장된 파일: {OUTPUT_DIR.absolute()}")
    print("="*60 + "\n")

