#!/bin/bash
#
# LobsterPulse Agent Installer
# One-command setup for OpenClaw agents
#

set -e

LOBSTER_PULSE_HOST="${LOBSTER_PULSE_HOST:-https://lobsterpulse.up.railway.app}"
CONFIG_DIR="${HOME}/.openclaw"
WORKSPACE_DIR="${CONFIG_DIR}/workspace"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🦞 LobsterPulse Agent Installer${NC}"
echo "================================"
echo ""

# Check if running inside OpenClaw environment
if [ -z "$OPENCLAW_AGENT_ID" ]; then
    # Try to get from hostname or generate
    AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')
    echo -e "${YELLOW}⚠ Warning: OPENCLAW_AGENT_ID not set, using hostname: $AGENT_ID${NC}"
else
    AGENT_ID="$OPENCLAW_AGENT_ID"
fi

# Get owner contact info
echo "Setting up LobsterPulse monitoring for agent: $AGENT_ID"
echo ""

read -p "Enter your Telegram username (e.g., @yourname): " OWNER_TELEGRAM
read -p "Enter your email (optional): " OWNER_EMAIL
read -p "Choose tier [free/guard/shield] (default: free): " TIER
TIER=${TIER:-free}

# Validate tier
if [[ ! "$TIER" =~ ^(free|guard|shield)$ ]]; then
    echo -e "${RED}❌ Invalid tier. Using 'free'.${NC}"
    TIER="free"
fi

echo ""
echo "Registering agent with LobsterPulse..."
echo "Host: $LOBSTER_PULSE_HOST"
echo ""

# Create temporary file for response
RESPONSE_FILE=$(mktemp)

# Register agent
REGISTER_PAYLOAD=$(cat <<EOF
{
    "agent_id": "$AGENT_ID",
    "owner_telegram": "$OWNER_TELEGRAM",
    "owner_email": "$OWNER_EMAIL",
    "tier": "$TIER",
    "last_will": "If I'm dead, please check the server status and restart OpenClaw Gateway."
}
EOF
)

HTTP_CODE=$(curl -s -w "%{http_code}" -o "$RESPONSE_FILE" \
    -X POST "${LOBSTER_PULSE_HOST}/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_PAYLOAD" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ Registration failed (HTTP $HTTP_CODE)${NC}"
    cat "$RESPONSE_FILE"
    rm "$RESPONSE_FILE"
    exit 1
fi

# Extract API key and config
API_KEY=$(grep -o '"api_key":"[^"]*"' "$RESPONSE_FILE" | cut -d'"' -f4)
INTERVAL_MINUTES=$(grep -o '"interval_minutes":[0-9]*' "$RESPONSE_FILE" | cut -d':' -f2)

rm "$RESPONSE_FILE"

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Failed to get API key from response${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Agent registered successfully!${NC}"
echo ""
echo "Configuration:"
echo "  Agent ID: $AGENT_ID"
echo "  Tier: $TIER"
echo "  Interval: $INTERVAL_MINUTES minutes"
echo "  API Key: ${API_KEY:0:20}..."
echo ""

# Create skill directory
SKILL_DIR="${CONFIG_DIR}/skills/lobster-pulse"
mkdir -p "$SKILL_DIR"

# Create heartbeat script
cat > "${SKILL_DIR}/heartbeat.sh" << 'SCRIPT_EOF'
#!/bin/bash
# LobsterPulse Heartbeat Script

API_KEY="${1:-}"
AGENT_ID="${2:-}"
HOST="${3:-https://lobsterpulse.up.railway.app}"

if [ -z "$API_KEY" ] || [ -z "$AGENT_ID" ]; then
    echo "Usage: heartbeat.sh <api_key> <agent_id> [host]"
    exit 1
fi

# Send heartbeat
curl -fsS -m 30 --retry 3 \
    -X POST "${HOST}/heartbeat" \
    -H "X-API-Key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"agent_id\":\"${AGENT_ID}\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
    > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] Heartbeat OK"
else
    echo "[$(date)] Heartbeat FAILED"
fi
SCRIPT_EOF

chmod +x "${SKILL_DIR}/heartbeat.sh"

# Convert interval minutes to cron-like format for HEARTBEAT.md
if [ "$INTERVAL_MINUTES" -eq 5 ]; then
    INTERVAL_STR="5m"
elif [ "$INTERVAL_MINUTES" -eq 30 ]; then
    INTERVAL_STR="30m"
elif [ "$INTERVAL_MINUTES" -eq 240 ]; then
    INTERVAL_STR="4h"
else
    INTERVAL_STR="${INTERVAL_MINUTES}m"
fi

# Update or create HEARTBEAT.md
HEARTBEAT_FILE="${WORKSPACE_DIR}/HEARTBEAT.md"

if [ -f "$HEARTBEAT_FILE" ]; then
    # Remove existing lobster-pulse entry if present
    grep -v "lobster_pulse" "$HEARTBEAT_FILE" > "${HEARTBEAT_FILE}.tmp" || true
    mv "${HEARTBEAT_FILE}.tmp" "$HEARTBEAT_FILE"
fi

# Add new entry
cat >> "$HEARTBEAT_FILE" << EOF

- name: lobster_pulse_heartbeat
  interval: ${INTERVAL_STR}
  command: |
    ${SKILL_DIR}/heartbeat.sh ${API_KEY} ${AGENT_ID} ${LOBSTER_PULSE_HOST}
EOF

echo -e "${GREEN}✅ HEARTBEAT.md updated${NC}"
echo ""

# Save credentials
cat > "${SKILL_DIR}/.env" << EOF
LOBSTER_PULSE_API_KEY=${API_KEY}
LOBSTER_PULSE_AGENT_ID=${AGENT_ID}
LOBSTER_PULSE_HOST=${LOBSTER_PULSE_HOST}
EOF

chmod 600 "${SKILL_DIR}/.env"

echo -e "${GREEN}✅ Credentials saved to ${SKILL_DIR}/.env${NC}"
echo ""

# Test heartbeat
echo "Testing heartbeat..."
"${SKILL_DIR}/heartbeat.sh" "$API_KEY" "$AGENT_ID" "$LOBSTER_PULSE_HOST"

echo ""
echo -e "${GREEN}🎉 Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Restart OpenClaw Gateway: openclaw gateway restart"
echo "2. You will receive a welcome message on Telegram"
echo "3. If your agent goes offline, you'll be notified"
echo ""
echo "To check status: curl -H 'X-API-Key: ${API_KEY:0:10}...' ${LOBSTER_PULSE_HOST}/status/${AGENT_ID}"
echo "To upgrade tier: curl -H 'X-API-Key: ${API_KEY:0:10}...' -X POST ${LOBSTER_PULSE_HOST}/upgrade -d '{\"tier\":\"guard\"}'"
