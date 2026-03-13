#!/bin/bash
# =====================================================================
# Instagram Scraper - Lightsail 서버 초기 셋업 스크립트
# 사용법: bash scripts/server_setup.sh [kr|jp|us]
# NordVPN은 이미 설치 및 로그인 완료 가정
# =====================================================================

set -e  # 오류 발생 시 즉시 중단

PROFILE=${1:-kr}
PROJECT_DIR="/srv/insta_scrap"
SERVICE_USER="ubuntu"

# 국가별 NordVPN exit node
declare -A VPN_COUNTRY=( ["kr"]="south_korea" ["jp"]="japan" ["us"]="united_states" )
declare -A CRON_TZ=( ["kr"]="Asia/Seoul" ["jp"]="Asia/Tokyo" ["us"]="America/New_York" )

VPN_NODE=${VPN_COUNTRY[$PROFILE]:-south_korea}
TZ_NAME=${CRON_TZ[$PROFILE]:-Asia/Seoul}

echo "======================================================"
echo "  Instagram Scraper 서버 셋업"
echo "  Profile  : $PROFILE"
echo "  VPN Node : $VPN_NODE"
echo "  Timezone : $TZ_NAME"
echo "======================================================"

# ── 1. 시스템 패키지 ───────────────────────────────────────────────
echo "[1/7] 시스템 패키지 설치 중..."
sudo apt update -qq
sudo apt install -y git curl python3 python3-pip libglib2.0-0 \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64

# ── 2. 서버 타임존 ─────────────────────────────────────────────────
echo "[2/7] 서버 타임존 설정 ($TZ_NAME)..."
sudo timedatectl set-timezone "$TZ_NAME"

# ── 3. Poetry ──────────────────────────────────────────────────────
echo "[3/7] Poetry 설치 중..."
if ! command -v poetry &> /dev/null; then
    curl -sSL https://install.python-poetry.org | python3 -
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "Poetry 버전: $(poetry --version)"

# ── 4. 프로젝트 설치 ──────────────────────────────────────────────
echo "[4/7] 프로젝트 의존성 설치 중..."
cd "$PROJECT_DIR"
poetry install --without dev
poetry run playwright install chromium
poetry run playwright install-deps chromium
echo "의존성 설치 완료"

# ── 5. 디렉토리 생성 ──────────────────────────────────────────────
echo "[5/7] 디렉토리 생성 중..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/output/$PROFILE"
mkdir -p "$PROJECT_DIR/sessions"
echo "디렉토리 생성 완료"

# ── 6. NordVPN 자동 연결 (systemd) ────────────────────────────────
echo "[6/7] NordVPN 자동 연결 설정 중 ($VPN_NODE)..."
sudo tee /etc/systemd/system/nordvpn-autoconnect.service > /dev/null <<EOF
[Unit]
Description=NordVPN Auto Connect
After=network.target nordvpnd.service
Requires=nordvpnd.service

[Service]
Type=oneshot
ExecStart=/usr/bin/nordvpn connect $VPN_NODE
RemainAfterExit=yes
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nordvpn-autoconnect.service
sudo nordvpn connect "$VPN_NODE" || echo "VPN 연결 실패 (로그인 여부 확인 필요)"
echo "NordVPN 자동 연결 설정 완료"

# ── 7. Cron 등록 ──────────────────────────────────────────────────
echo "[7/7] Cron 등록 중..."
CRON_FILE="/etc/cron.d/insta-scraper-$PROFILE"

sudo tee "$CRON_FILE" > /dev/null <<EOF
# Instagram Scraper - $PROFILE
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin:/root/.local/bin

# 매일 02:00 릴스 수집 (로그는 loguru가 logs/scraper.log에 기록)
0 2 * * * $SERVICE_USER cd $PROJECT_DIR && poetry run python main.py --profile $PROFILE > /dev/null 2>&1

# 매일 06:00 조회수 추적
0 6 * * * $SERVICE_USER cd $PROJECT_DIR && poetry run python track_views.py output/$PROFILE/\$(date +\\%Y\\%m\\%d)*.json --profile $PROFILE > /dev/null 2>&1

# 매시간 헬스체크 (NordVPN, DB, 수집 건수, 디스크)
0 * * * * $SERVICE_USER cd $PROJECT_DIR && poetry run python scripts/health_check.py --profile $PROFILE > /dev/null 2>&1

# 매주 일요일 03:00 output JSON 30일 이상, 압축 로그 10일 이상 삭제
0 3 * * 0 $SERVICE_USER find $PROJECT_DIR/output -name "*.json" -mtime +30 -delete
0 3 * * 0 $SERVICE_USER find $PROJECT_DIR/logs -name "*.zip" -mtime +10 -delete
EOF

sudo chmod 644 "$CRON_FILE"
echo "Cron 등록 완료: $CRON_FILE"

# ── 7.5. logrotate 설정 ────────────────────────────────────────────
echo "[7.5] logrotate 설정 중..."
sudo tee "/etc/logrotate.d/insta-scraper" > /dev/null <<EOF
$PROJECT_DIR/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
EOF
echo "logrotate 설정 완료: /etc/logrotate.d/insta-scraper"

# ── 완료 ──────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo "  셋업 완료!"
echo "======================================================"
echo ""
echo "  다음 단계:"
echo "  1. .env 파일 확인 (DB, S3 설정)"
echo "  2. accounts.yaml의 '$PROFILE' 계정 정보 확인"
echo "  3. VPN 연결 확인: nordvpn status"
echo "  4. 수동 1회 실행 테스트:"
echo "     cd $PROJECT_DIR && poetry run python main.py --profile $PROFILE"
echo ""
echo "  현재 VPN 상태:"
nordvpn status 2>/dev/null || echo "  (nordvpn 명령 실패 - 설치 확인 필요)"
