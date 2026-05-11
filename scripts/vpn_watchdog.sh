#!/bin/bash
# VPN 라우팅 워치독 — Status: Connected이나 WireGuard 라우팅 깨진 경우 자동 복구
# cron: */5 * * * * ubuntu /srv/insta_scrap/scripts/vpn_watchdog.sh {국가} >> /srv/insta_scrap/logs/vpn_watchdog.log 2>&1
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

_FLAG=$(case "$PROFILE" in kr) echo "🇰🇷";; jp) echo "🇯🇵";; us) echo "🇺🇸";; *) echo "[${PROFILE^^}]";; esac)

if nordvpn status 2>/dev/null | grep -q 'Status: Connected'; then
    if ! ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
        echo "$(date): [vpn-watchdog][${PROFILE}] 라우팅 깨짐 감지 — reconnect 시도"
        nordvpn disconnect 2>/dev/null || true
        sleep 3
        nordvpn connect ${VPN_COUNTRY} 2>/dev/null || true
        sleep 15
        if ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
            echo "$(date): [vpn-watchdog][${PROFILE}] 재연결 성공"
            slack_notify "${_FLAG} *[VPN 자동 복구]* \`${PROFILE^^}\` WireGuard 라우팅 깨짐 감지 → reconnect 성공"
        else
            echo "$(date): [vpn-watchdog][${PROFILE}] 재연결 실패"
            slack_notify "${_FLAG} *[VPN 복구 실패]* \`${PROFILE^^}\` reconnect 후에도 ping 실패 — 수동 확인 필요"
        fi
    fi
else
    echo "$(date): [vpn-watchdog][${PROFILE}] VPN 미연결 — connect 시도"
    nordvpn connect ${VPN_COUNTRY} 2>/dev/null || true
    sleep 15
    if nordvpn status 2>/dev/null | grep -q 'Status: Connected'; then
        echo "$(date): [vpn-watchdog][${PROFILE}] VPN 연결 성공"
        slack_notify "${_FLAG} *[VPN 자동 복구]* \`${PROFILE^^}\` VPN 미연결 감지 → connect 성공"
    else
        echo "$(date): [vpn-watchdog][${PROFILE}] VPN 연결 실패"
        slack_notify "${_FLAG} *[VPN 연결 실패]* \`${PROFILE^^}\` connect 후에도 미연결 — 수동 확인 필요"
    fi
fi
