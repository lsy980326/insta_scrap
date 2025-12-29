"""
mitmweb 실행 스크립트
"""
import sys
from pathlib import Path
from mitmproxy.tools.main import mitmweb

if __name__ == "__main__":
    # 포트 설정
    proxy_port = 8080  # 프록시 포트
    web_port = 8081    # 웹 UI 포트
    script_file = None  # capture.py 스크립트
    
    # 명령줄 인자 파싱
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "-s" or arg == "--script":
            if i + 1 < len(sys.argv):
                script_file = sys.argv[i + 1]
                i += 2
            else:
                print("오류: -s 옵션 뒤에 스크립트 파일 경로가 필요합니다")
                sys.exit(1)
        elif arg.isdigit():
            proxy_port = int(arg)
            i += 1
        else:
            i += 1
    
    # capture.py 또는 capture_bypass.py가 있으면 자동으로 사용
    if script_file is None:
        # 우선 capture_bypass.py 사용 (SSL 우회 모드)
        bypass_path = Path("capture_bypass.py")
        capture_path = Path("capture.py")
        
        if bypass_path.exists():
            script_file = str(bypass_path)
            print(f"[*] capture_bypass.py 스크립트 자동 감지 (SSL 우회 모드)")
        elif capture_path.exists():
            script_file = str(capture_path)
            print(f"[*] capture.py 스크립트 자동 감지")
    
    print("=" * 60)
    print("mitmweb 실행 중...")
    print("=" * 60)
    print(f"프록시 포트: {proxy_port}")
    print(f"웹 UI: http://127.0.0.1:{web_port}")
    print("무시할 호스트: googleapis.com, google.com")
    if script_file:
        print(f"스크립트: {script_file}")
    print("=" * 60)
    print("종료하려면 Ctrl+C를 누르세요")
    print("=" * 60)
    print()
    
    try:
        # mitmweb 실행 (포트 지정)
        # --set confdir=~/.mitmproxy : 인증서 설정
        # --set ssl_insecure=true : SSL 검증 완화 (디버깅용, 주의!)
        args = [
            "mitmweb",
            "--mode", f"regular@{proxy_port}",
            "--web-port", str(web_port),
            "--ignore-hosts", "googleapis.com|google.com",
            # SSL 검증 완화 (주의: 보안상 프로덕션에서는 사용하지 마세요)
            "--set", "ssl_insecure=true",
            # 인증서 검증 완화
            "--set", "verify_upstream_cert=false",
        ]
        if script_file:
            args.extend(["-s", script_file])
        
        sys.argv = args
        mitmweb()
    except KeyboardInterrupt:
        print("\n\nmitmweb 종료")
    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()

