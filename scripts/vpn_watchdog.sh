#!/bin/bash
# VPN 라우팅 워치독 — Status: Connected이나 WireGuard 라우팅 깨진 경우 자동 복구
# cron: * * * * * ubuntu /srv/insta_scrap/scripts/vpn_watchdog.sh {국가} >> /srv/insta_scrap/logs/vpn_watchdog.log 2>&1
PROFILE="${1:-kr}"

vpn_country() {
    case "$1" in
        kr) echo "south_korea" ;;
        jp) echo "Osaka" ;;
        us) echo "united_states" ;;
        *)  echo "" ;;
    esac
}
VPN_COUNTRY=$(vpn_country "$PROFILE")

SLACK_URL=$(grep '^SLACK_WEBHOOK_URL=' /srv/insta_scrap/.env 2>/dev/null | cut -d= -f2-)
slack_notify() {
    [ -z "$SLACK_URL" ] && return
    curl -s -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"$1\"}" "$SLACK_URL" > /dev/null 2>&1 || true
}

case "$PROFILE" in
    kr) _FLAG="🇰🇷" ;;
    jp) _FLAG="🇯🇵" ;;
    us) _FLAG="🇺🇸" ;;
    *)  _FLAG="[${PROFILE^^}]" ;;
esac

# VPN 연결 시도 (최대 3회, 2회 실패 시 nordvpnd 데몬 재시작 후 재시도)
connect_vpn() {
    for attempt in 1 2 3; do
        nordvpn disconnect 2>/dev/null || true
        sleep 2
        nordvpn connect ${VPN_COUNTRY} 2>/dev/null || true
        sleep 15
        if ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
            return 0
        fi
        echo "$(date): [vpn-watchdog][${PROFILE}] reconnect 시도 ${attempt}/3 실패"
        if [ "$attempt" -eq 2 ]; then
            echo "$(date): [vpn-watchdog][${PROFILE}] nordvpnd 데몬 재시작 시도..."
            sudo systemctl restart nordvpnd 2>/dev/null || true
            sleep 10
        fi
    done
    return 1
}

# 운영시간(09-13, 15-21 KST) 내이고 vpn-killed 플래그가 있으면 서비스 즉시 재시작
restart_if_needed() {
    local HOUR
    HOUR=$(date +%H)
    local in_ops=false
    if [ "$HOUR" -ge 9 ] && [ "$HOUR" -lt 13 ]; then in_ops=true; fi
    if [ "$HOUR" -ge 15 ] && [ "$HOUR" -lt 21 ]; then in_ops=true; fi

    local VPN_KILL_FLAG="/tmp/insta-vpn-killed-${PROFILE}"
    if $in_ops && [ -f "$VPN_KILL_FLAG" ]; then
        rm -f "$VPN_KILL_FLAG"
        echo "$(date): [vpn-watchdog][${PROFILE}] 운영시간 + vpn-killed 플래그 — 서비스 즉시 재시작"
        touch "/tmp/insta-force-start-${PROFILE}"
        sudo systemctl start "insta-scraper@${PROFILE}.service" 2>/dev/null || true
    fi
}

# ── 메인 로직 ──────────────────────────────────────────────────────────────
if nordvpn status 2>/dev/null | grep -q 'Status: Connected'; then
    if ! ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
        echo "$(date): [vpn-watchdog][${PROFILE}] 라우팅 깨짐 감지 — reconnect 시도"
        if connect_vpn; then
            echo "$(date): [vpn-watchdog][${PROFILE}] 재연결 성공"
            slack_notify "${_FLAG} *[VPN 자동 복구]* WireGuard 라우팅 깨짐 → reconnect 성공"
            restart_if_needed
        else
            echo "$(date): [vpn-watchdog][${PROFILE}] 재연결 3회 실패"
            slack_notify "${_FLAG} ⚠️ *[VPN 복구 실패]* reconnect 3회 실패 — 수동 확인 필요"
        fi
    fi
    # VPN 정상이면 조용히 종료 (매분 실행이므로 로그 없음)
else
    echo "$(date): [vpn-watchdog][${PROFILE}] VPN 미연결 — connect 시도"
    if connect_vpn; then
        echo "$(date): [vpn-watchdog][${PROFILE}] 연결 성공"
        slack_notify "${_FLAG} *[VPN 자동 복구]* VPN 미연결 감지 → connect 성공"
        restart_if_needed
    else
        echo "$(date): [vpn-watchdog][${PROFILE}] 연결 3회 실패"
        slack_notify "${_FLAG} ⚠️ *[VPN 연결 실패]* connect 3회 실패 — 수동 확인 필요"
    fi
fi
