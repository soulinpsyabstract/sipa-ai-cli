#!/usr/bin/env bash
# SIPA AI CLI · install.sh · V1.1
# Установка: sha256 + TAG + manifest + audit entry + binary sync
# Запуск: bash /home/sipa/apps/sipa-ai-cli/install.sh

set -euo pipefail

SRC_CLI="/home/sipa/apps/sipa-ai-cli/sipa_ai_cli.py"
SRC_API="/home/sipa/apps/sipa-ai-cli/api.py"
BIN="/home/sipa/bin/sipa-ai"
APP_DIR="/home/sipa/apps/sipa-ai-cli"
FORENSIC_DIR="${APP_DIR}"
HUB_AI_MLL="/home/sipa/PROJECT/PAYTON_HUBS/HUB_AI_MLL"
MANIFEST="${HUB_AI_MLL}/MANIFEST__SIPA_AI_CLI.tsv"
AUDIT_LOG="/home/sipa/PROJECT/PAYTON_HUBS/HUB_LEGAL_FORENSIC/AUDIT__LEGAL_FIXATIONS.log"
SYSTEMD_SRC="${APP_DIR}/systemd/sipa-ai.service"
DATE=$(date +%Y-%m-%d)
TS=$(date +%Y-%m-%d__%H-%M-%S)

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  S I P A   A I   C L I  ·  install      ║"
echo "║  V1.1 · MLL L01-L10 · Protocol 0        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Binary ────────────────────────────────────────────────────────────────
cp "$SRC_CLI" "$BIN"
chmod +x "$BIN"
echo "✓ binary    $BIN"

# ── 2. SHA256 + TAG ──────────────────────────────────────────────────────────
FULLHASH=$(sha256sum "$BIN" | awk '{print $1}')
SHORTHASH="${FULLHASH:0:8}"
SIZE=$(wc -c < "$BIN")

echo "$FULLHASH  $BIN" > "${FORENSIC_DIR}/sipa-ai.sha256"
echo "✓ sha256    ${FORENSIC_DIR}/sipa-ai.sha256  [${SHORTHASH}]"

cat > "${FORENSIC_DIR}/sipa-ai.TAG" <<EOF
FILE=sipa-ai
VERSION=V1.1
HASH=${SHORTHASH}
SHA256=${FULLHASH}
SIZE=${SIZE}
DATE=${DATE}
HUB=HUB_AI_MLL
PROTOCOL=0
MLL=L01-L10
GUARDIAN=AUDIT__LEGAL_FIXATIONS.log
PATH_BIN=${BIN}
PATH_SRC=${SRC_CLI}
PATH_API=${SRC_API}
PORT_API=5003
ENDPOINTS=/health /ask /models /session /mcp /webhook
WORKER=sipa-ai.sipa-os.org
TUNNEL=sipa-ai-backend.soulinpsy.info
DOMAIN=sipa-ai.sipa-os.org
MCP_TOOLS=sipa_ask sipa_models sipa_status
EOF
echo "✓ TAG       ${FORENSIC_DIR}/sipa-ai.TAG"

# ── 3. Manifest (TSV) ────────────────────────────────────────────────────────
mkdir -p "$HUB_AI_MLL"
if [ ! -f "$MANIFEST" ]; then
    echo -e "DATE\tFILE\tVERSION\tHASH\tSIZE\tHUB\tNOTES" > "$MANIFEST"
fi
echo -e "${DATE}\tsipa-ai\tV1.1\t${SHORTHASH}\t${SIZE}\tHUB_AI_MLL\tMLL:L01-L10·Guard·Guardian·MCP·webhook·:5003" >> "$MANIFEST"
echo "✓ manifest  $MANIFEST"

# ── 4. Guardian audit entry ──────────────────────────────────────────────────
echo "[${TS}] [SIPA_AI_CLI] [INSTALL] layer=- model=- elapsed=0.0s | hash=${SHORTHASH} version=V1.1 size=${SIZE}" >> "$AUDIT_LOG"
echo "✓ audit     $AUDIT_LOG"

# ── 5. Summary ───────────────────────────────────────────────────────────────
echo ""
echo "── ENDPOINTS ───────────────────────────────────────"
API_STATUS=$(curl -s http://127.0.0.1:5003/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('✓ UP  ')" 2>/dev/null || echo "✗ DOWN")
echo "  CLI      sipa-ai"
echo "  API      http://127.0.0.1:5003        ${API_STATUS}"
echo "  health   http://127.0.0.1:5003/health"
echo "  ask      http://127.0.0.1:5003/ask    POST {message, layer, model}"
echo "  webhook  http://127.0.0.1:5003/webhook POST {message, source, secret}"
echo "  mcp      http://127.0.0.1:5003/mcp    JSON-RPC 2.0"
echo "  models   http://127.0.0.1:5003/models"
echo "  worker   https://sipa-ai.sipa-os.org"
echo "  tunnel   https://sipa-ai-backend.soulinpsy.info"
echo ""

# ── 6. Systemd ───────────────────────────────────────────────────────────────
echo "── SYSTEMD (нужен sudo) ─────────────────────────────"
echo "  sudo cp ${SYSTEMD_SRC} /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now sipa-ai.service"
echo "  sudo systemctl status sipa-ai.service"
echo ""
echo "── ГОТОВО ───────────────────────────────────────────"
echo "  hash: ${SHORTHASH}  size: ${SIZE}B  date: ${DATE}"
echo ""
