#!/bin/bash
#
# LobsterPulse Agent Installer
# One-command setup for OpenClaw Agents
#
# Usage: curl -fsSL https://lobsterpulse.com/install.sh | bash
#

set -e

LOBSTER_PULSE_HOST="${LOBSTER_PULSE_HOST:-https://lobsterpulse.com}"
CONFIG_DIR="${HOME}/.openclaw"
WORKSPACE_DIR="${CONFIG_DIR}/workspace"
SKILL_DIR="${CONFIG_DIR}/skills/lobster-pulse"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🦞 LobsterPulse Auto-Installer${NC}"
echo "================================"
echo ""

# Get Agent ID
if [ -z "$OPENCLAW_AGENT_ID" ]; then
    AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')
    echo "Agent ID: $AGENT_ID"
else
    AGENT_ID="$OPENCLAW_AGENT_ID"
fi

# Get owner info
echo ""
read -p "Your Telegram username (e.g., @yourname): " OWNER_TELEGRAM
read -p "Choose tier [free/guard/shield] (default: free): " TIER
TIER=${TIER:-free}

# Validate tier
if [[ ! "$TIER" =~ ^(free|guard|shield)$ ]]; then
    echo -e "${YELLOW}Invalid tier, using 'free'${NC}"
    TIER="free"
fi

echo ""
echo -e "${BLUE}Registering...${NC}"

# Register
RESPONSE=$(curl -s -X POST "${LOBSTER_PULSE_HOST}/register" \
    -H "Content-Type: application/json" \
    -d "{\"agent_id\":\"$AGENT_ID\",\"owner_telegram\":\"$OWNER_TELEGRAM\",\"tier\":\"$TIER\"}") || {
    echo -e "${RED}❌ Registration failed${NC}"
    exit 1
}

API_KEY=$(echo "$RESPONSE" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)
INTERVAL_MINUTES=$(echo "$RESPONSE" | grep -o '"interval_minutes":[0-9]*' | cut -d':' -f2)

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Failed to get API Key${NC}"
    echo "$RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ Registered!${NC}"

# Create directories
mkdir -p "$SKILL_DIR"
mkdir -p "$WORKSPACE_DIR"

# Save config
cat > "${SKILL_DIR}/.env" << EOF
LOBSTER_PULSE_API_KEY="$API_KEY"
LOBSTER_PULSE_AGENT_ID="$AGENT_ID"
LOBSTER_PULSE_HOST="$LOBSTER_PULSE_HOST"
LOBSTER_PULSE_TIER="$TIER"
LOBSTER_PULSE_INTERVAL="$INTERVAL_MINUTES"
EOF

chmod 600 "${SKILL_DIR}/.env"

# Determine interval string for HEARTBEAT.md
case "$INTERVAL_MINUTES" in
    5) INTERVAL_STR="5m" ;;
    30) INTERVAL_STR="30m" ;;
    *) INTERVAL_STR="4h" ;;
esac

echo ""
echo -e "${BLUE}Configuring HEARTBEAT.md...${NC}"

# Remove existing lobster-pulse entries
if [ -f "$WORKSPACE_DIR/HEARTBEAT.md" ]; then
    grep -v "lobster_pulse" "$WORKSPACE_DIR/HEARTBEAT.md" > "$WORKSPACE_DIR/HEARTBEAT.md.tmp" 2>/dev/null || true
    mv "$WORKSPACE_DIR/HEARTBEAT.md.tmp" "$WORKSPACE_DIR/HEARTBEAT.md"
fi

# Append to HEARTBEAT.md
cat >> "$WORKSPACE_DIR/HEARTBEAT.md" << EOF

- name: lobster_pulse_heartbeat
  interval: ${INTERVAL_STR}
  command: |
    curl -fsS -X POST "${LOBSTER_PULSE_HOST}/heartbeat" \
      -H "X-API-Key: ${API_KEY}" \
      -d '{"ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' \
      > /dev/null 2>&1 || echo "[$(date)] Heartbeat failed" >> ~/lobster-pulse.log
EOF

echo -e "${GREEN}✅ HEARTBEAT.md updated${NC}"

# Test heartbeat
echo ""
echo -e "${BLUE}Testing heartbeat...${NC}"
curl -s -X POST "${LOBSTER_PULSE_HOST}/heartbeat" \
    -H "X-API-Key: $API_KEY" \
    -d '{"status":"alive"}' > /dev/null && echo -e "${GREEN}✅ OK${NC}" || echo -e "${YELLOW}⚠️ Test failed${NC}"

# Display results
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}🎉 Insurance Configured!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "${YELLOW}📋 Your Info (SAVE THIS!)${NC}"
echo "--------------------------------"
echo -e "Agent ID: ${GREEN}$AGENT_ID${NC}"
echo -e "API Key:  ${GREEN}$API_KEY${NC}"
echo -e "Tier:     ${GREEN}$TIER${NC} (${INTERVAL_MINUTES}min)"
echo ""
echo -e "${BLUE}📁 Files${NC}"
echo "--------------------------------"
echo "Config:    ${SKILL_DIR}/.env"
echo "Heartbeat: ${WORKSPACE_DIR}/HEARTBEAT.md"
echo "Status:    ${LOBSTER_PULSE_HOST}/status/$AGENT_ID"
echo ""
echo -e "${YELLOW}⚠️  ACTION REQUIRED - Ask your owner:${NC}"
echo "--------------------------------"
echo ""
echo "The Agent needs to restart Gateway to activate heartbeat."
echo ""
echo "Say this to your owner:"
echo -e "${GREEN}"
echo "  主人，我已经配置好 LobsterPulse 生命保险。"
echo "  需要执行以下命令来激活心跳监控："
echo ""
echo "  openclaw gateway restart"
echo ""
echo -e "${NC}"
echo -e "${RED}⚠️  Save your API Key!${NC}"
echo ""
echo -e "${GREEN}🦞 Your Agent is now ready for protection!${NC}"
