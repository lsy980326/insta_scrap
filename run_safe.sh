#!/bin/bash
# 중복 실행 방지 래퍼 — flock으로 동일 profile 동시 실행 차단
PROFILE="${1:-kr}"
LOCKFILE="/tmp/insta-scraper-${PROFILE}.lock"

# ── Slack 알림 함수 ────────────────────────────────────────────
SLACK_URL=$(grep '^SLACK_WEBHOOK_URL=' /srv/insta_scrap/.env 2>/dev/null | cut -d= -f2-)
slack_notify() {
    local MSG="$1"
    [ -z "$SLACK_URL" ] && return
    curl -s -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"${MSG}\"}" "$SLACK_URL" > /dev/null 2>&1 || true
}

# ── NordVPN 연결 및 라우팅 확인 ────────────────────────────────
# Status: Connected이어도 WireGuard(NORDLYNX) 라우팅 테이블이 깨질 수 있음
# → ping으로 실제 연결 확인 후, 실패 시 disconnect && connect 로 라우팅 복구
vpn_country() {
    case "$1" in
        kr) echo "south_korea" ;;
        jp) echo "Japan" ;;
        us) echo "united_states" ;;
        *)  echo "" ;;
    esac
}
VPN_COUNTRY=$(vpn_country "$PROFILE")

MAX_VPN_WAIT=120
VPN_WAITED=0
echo "$(date): NordVPN 연결 상태 확인 중..."
while true; do
    if nordvpn status 2>/dev/null | grep -q 'Status: Connected'; then
        if ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
            echo "$(date): NordVPN 연결 및 라우팅 정상"
            break
        else
            echo "$(date): NordVPN Status: Connected이나 라우팅 깨짐 — disconnect && reconnect"
            nordvpn disconnect 2>/dev/null || true
            sleep 3
            nordvpn connect ${VPN_COUNTRY} 2>/dev/null || true
            sleep 15
        fi
    fi
    if [ "$VPN_WAITED" -ge "$MAX_VPN_WAIT" ]; then
        echo "$(date): VPN 복구 ${MAX_VPN_WAIT}초 초과 — 강제 시작"
        break
    fi
    sleep 5
    VPN_WAITED=$((VPN_WAITED + 5))
done
echo "$(date): NordVPN 상태: $(nordvpn status 2>/dev/null | grep Status || echo 'unknown')"

# ── CPU 버스트 크레딧 확인 (steal time 기반) ───────────────────
check_steal() {
    read -r cpu u n s id io irq si st _ < /proc/stat; sleep 2
    read -r cpu u2 n2 s2 id2 io2 irq2 si2 st2 _ < /proc/stat
    steal_diff=$((st2 - st))
    total_diff=$(( (u2+n2+s2+id2+io2+irq2+si2+st2) - (u+n+s+id+io+irq+si+st) ))
    [ "$total_diff" -gt 0 ] && echo $((steal_diff * 100 / total_diff)) || echo 0
}

# steal 수준에 따른 추가 휴식 시간 계산 (초 단위)
# 크레딧 소진 정도가 클수록 더 오래 쉬어서 자연 회복 유도
extra_rest_seconds() {
    local STEAL=$1
    if [ "$STEAL" -ge 50 ]; then
        echo 3600   # 50%+ : 60분 추가
    elif [ "$STEAL" -ge 20 ]; then
        echo 2400   # 20~49%: 40분 추가
    elif [ "$STEAL" -ge 10 ]; then
        echo 1800   # 10~19%: 30분 추가
    elif [ "$STEAL" -ge 5 ]; then
        echo 1200   # 5~9%  : 20분 추가
    else
        echo 0      # 5% 미만: 추가 없음
    fi
}

# D9-D: 시작 조건 — steal <= 1%가 15분 연속 유지 시 크레딧 회복 추정
STEAL_START_THRESHOLD=1   # 시작 허용 steal 상한
STEAL_STOP_THRESHOLD=8    # 수집 중 kill 기준
STABLE_REQUIRED=15        # 연속 유지 필요 분
MAX_CREDIT_WAIT=7200      # 최대 2시간 대기 후 강제 시작

CREDIT_WAITED=0
STABLE_COUNT=0

# force-start 플래그: 파일이 있으면 안정화 대기 건너뜀 (1회성)
FORCE_START_FLAG="/tmp/insta-force-start-${PROFILE}"
if [ -f "$FORCE_START_FLAG" ]; then
    echo "$(date): force-start 플래그 감지 — 안정화 대기 건너뜀"
    rm -f "$FORCE_START_FLAG"
else

echo "$(date): 버스트 크레딧 회복 대기 중 (steal<=${STEAL_START_THRESHOLD}% ${STABLE_REQUIRED}분 유지 필요)..."
while true; do
    STEAL=$(check_steal)

    if [ "$STEAL" -le "$STEAL_START_THRESHOLD" ]; then
        STABLE_COUNT=$((STABLE_COUNT + 1))
        echo "$(date): CPU steal ${STEAL}% — 안정 ${STABLE_COUNT}/${STABLE_REQUIRED}분"
        if [ "$STABLE_COUNT" -ge "$STABLE_REQUIRED" ]; then
            echo "$(date): 크레딧 회복 확인 — 수집 시작"
            break
        fi
    else
        if [ "$STABLE_COUNT" -gt 0 ]; then
            echo "$(date): CPU steal ${STEAL}% — 안정 카운터 초기화 (${STABLE_COUNT}분 → 0)"
        else
            echo "$(date): CPU steal ${STEAL}% > ${STEAL_START_THRESHOLD}% — 크레딧 부족, 대기 중..."
        fi
        STABLE_COUNT=0
    fi

    if [ "$CREDIT_WAITED" -ge "$MAX_CREDIT_WAIT" ]; then
        echo "$(date): 최대 대기(${MAX_CREDIT_WAIT}초) 초과 — 강제 시작"
        break
    fi

    sleep 60
    CREDIT_WAITED=$((CREDIT_WAITED + 62))  # check_steal 2초 포함
done

fi  # force-start 플래그 분기 종료

# ── 수집 중 steal 모니터링 (백그라운드) ────────────────────────
monitor_steal() {
    local PID=$1
    echo "$(date): steal 모니터 시작 (PID=${PID}, 중지 기준 ${STEAL_STOP_THRESHOLD}%)"
    while kill -0 "$PID" 2>/dev/null; do
        STEAL=$(check_steal)
        if [ "$STEAL" -gt "$STEAL_STOP_THRESHOLD" ]; then
            echo "$(date): 수집 중 CPU steal ${STEAL}% 초과 — 크레딧 소진, scraper 종료"
            kill "$PID" 2>/dev/null
            break
        fi
        echo "$(date): steal 모니터: ${STEAL}% (정상)"
        sleep 60
    done
    echo "$(date): steal 모니터 종료"
}

# flock으로 중복 실행 방지 후 scraper 실행
flock -n "$LOCKFILE" /home/ubuntu/.local/bin/poetry run python main.py --profile "$PROFILE" &
SCRAPER_PID=$!

monitor_steal "$SCRAPER_PID" &
MONITOR_PID=$!

# scraper 종료 대기
wait "$SCRAPER_PID"
SCRAPER_EXIT=$?

# 모니터 정리
kill "$MONITOR_PID" 2>/dev/null
wait "$MONITOR_PID" 2>/dev/null

# ── 종료 후 추가 휴식 (steal 높을수록 더 오래 쉼) ──────────────
FINAL_STEAL=$(check_steal)
EXTRA=$(extra_rest_seconds "$FINAL_STEAL")
BASE_REST_MIN=40  # systemd RestartSec=2400

_FLAG=""
case "$PROFILE" in
  kr) _FLAG="🇰🇷" ;;
  jp) _FLAG="🇯🇵" ;;
  us) _FLAG="🇺🇸" ;;
  *)  _FLAG="[${PROFILE^^}]" ;;
esac

if [ "$EXTRA" -gt 0 ]; then
    EXTRA_MIN=$((EXTRA / 60))
    TOTAL_MIN=$((BASE_REST_MIN + EXTRA_MIN))
    echo "$(date): 종료 시 steal ${FINAL_STEAL}% — 크레딧 회복을 위해 ${EXTRA_MIN}분 추가 휴식"
    slack_notify "${_FLAG} *[${PROFILE^^}] 휴식 중*\n기본 ${BASE_REST_MIN}분 + steal ${FINAL_STEAL}% 추가 ${EXTRA_MIN}분 = 총 ${TOTAL_MIN}분 휴식"
    sleep "$EXTRA"
else
    echo "$(date): 종료 시 steal ${FINAL_STEAL}% — 정상 종료, 추가 휴식 없음"
    slack_notify "${_FLAG} *[${PROFILE^^}] 휴식 중*\n기본 ${BASE_REST_MIN}분 휴식 (steal ${FINAL_STEAL}% — 정상)"
fi

exit "$SCRAPER_EXIT"
