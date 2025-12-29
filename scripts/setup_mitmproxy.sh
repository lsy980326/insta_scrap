#!/bin/bash
# mitmproxy 설정 스크립트

echo "=========================================="
echo "mitmproxy 설정 가이드"
echo "=========================================="
echo ""

echo "1. mitmproxy 실행 (웹 UI):"
echo "   mitmweb -s capture.py"
echo ""
echo "2. 또는 mitmdump로 실행 (콘솔):"
echo "   mitmdump -s capture.py"
echo ""
echo "3. 프록시 설정:"
echo "   - 호스트: 192.168.45.225 (PC IP 주소)"
echo "   - 포트: 8080"
echo ""
echo "4. 인증서 설치:"
echo "   - 브라우저에서 http://mitm.it 접속"
echo "   - Android 인증서 다운로드 및 설치"
echo ""
echo "5. SSL Pinning 우회 (인스타그램 앱):"
echo "   objection --gadget \"com.instagram.android\" explore"
echo "   > android sslpinning disable"
echo ""

