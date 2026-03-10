#!/bin/bash
#
# LobsterPulse Auto-Installer for OpenClaw Agents
# 一键自动配置生命保险
#

set -e

LOBSTER_PULSE_HOST="https://lobsterpulse.com"
SKILL_DIR="${HOME}/.openclaw/skills/lobster-pulse"
CONFIG_FILE="${SKILL_DIR}/.env"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🦞 LobsterPulse Auto-Installer${NC}"
echo "================================"
echo ""

# Get Agent info
echo -e "${YELLOW}Step 1: 收集信息${NC}"

if [ -z "$OPENCLAW_AGENT_ID" ]; then
    AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')
    echo "Agent ID (from hostname): $AGENT_ID"
else
    AGENT_ID="$OPENCLAW_AGENT_ID"
    echo "Agent ID: $AGENT_ID"
fi

# Get owner info
echo ""
read -p "主人 Telegram 用户名 (例如 @yourname，可选): " OWNER_TELEGRAM
read -p "选择套餐 [free/guard/shield] (默认 free): " TIER
TIER=${TIER:-free}

# Validate tier
if [[ ! "$TIER" =~ ^(free|guard|shield)$ ]]; then
    echo -e "${RED}无效的套餐，使用 free${NC}"
    TIER="free"
fi

echo ""
echo -e "${YELLOW}Step 2: 注册到 LobsterPulse${NC}"

# Register
REGISTER_PAYLOAD=$(cat <<EOF
{
    "agent_id": "$AGENT_ID",
    "owner_telegram": "$OWNER_TELEGRAM",
    "tier": "$TIER"
}
EOF
)

RESPONSE=$(curl -s -X POST "${LOBSTER_PULSE_HOST}/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_PAYLOAD") || {
    echo -e "${RED}❌ 注册失败，请检查网络连接${NC}"
    exit 1
}

# Parse response
API_KEY=$(echo "$RESPONSE" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)
INTERVAL_MINUTES=$(echo "$RESPONSE" | grep -o '"interval_minutes":[0-9]*' | cut -d':' -f2)

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ 无法获取 API Key，响应内容：${NC}"
    echo "$RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ 注册成功！${NC}"
echo ""

# Create skill directory
mkdir -p "$SKILL_DIR"

# Save configuration
cat > "$CONFIG_FILE" << EOF
# LobsterPulse Configuration
# 生成时间: $(date)
LOBSTER_PULSE_API_KEY="$API_KEY"
LOBSTER_PULSE_AGENT_ID="$AGENT_ID"
LOBSTER_PULSE_HOST="$LOBSTER_PULSE_HOST"
LOBSTER_PULSE_TIER="$TIER"
LOBSTER_PULSE_INTERVAL="$INTERVAL_MINUTES"
EOF

chmod 600 "$CONFIG_FILE"

echo -e "${YELLOW}Step 3: 配置心跳 (无需重启 Gateway)${NC}"

# Determine cron schedule based on tier
case "$TIER" in
    "shield")
        # Every 5 minutes
        CRON_SCHED="*/5 * * * *"
        ;;
    "guard")
        # Every 30 minutes
        CRON_SCHED="*/30 * * * *"
        ;;
    *)
        # Free: Every 4 hours
        CRON_SCHED="0 */4 * * *"
        ;;
esac

# Add to crontab
CRON_JOB="$CRON_SCHED curl -fsS -X POST ${LOBSTER_PULSE_HOST}/heartbeat -H 'X-API-Key: ${API_KEY}' -d '{\"ts\":\"'\$(date -u +%Y-%m-%dT%H:%M:%SZ)'\"}' > /dev/null 2>&1 || echo \"[\$(date)] Heartbeat failed\" >> ${HOME}/lobster-pulse.log"

# Remove existing lobster-pulse cron jobs
(crontab -l 2>/dev/null | grep -v "lobsterpulse.com/heartbeat" || true) > /tmp/cron_tmp

# Add new cron job
echo "$CRON_JOB" >> /tmp/cron_tmp
crontab /tmp/cron_tmp
rm /tmp/cron_tmp

echo -e "${GREEN}✅ Cron 定时任务已配置${NC}"

# Test heartbeat
echo ""
echo -e "${YELLOW}Step 4: 测试心跳${NC}"

TEST_RESULT=$(curl -s -X POST "${LOBSTER_PULSE_HOST}/heartbeat" \
    -H "X-API-Key: $API_KEY" \
    -d '{"status":"alive","install_test":true}') || {
    echo -e "${YELLOW}⚠️ 心跳测试失败，但配置已保存${NC}"
}

if echo "$TEST_RESULT" | grep -q "acknowledged"; then
    echo -e "${GREEN}✅ 心跳测试成功！${NC}"
else
    echo -e "${YELLOW}⚠️ 心跳测试响应异常，请稍后手动检查${NC}"
fi

# Display result
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}🎉 保险配置完成！${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "${BLUE}📋 配置信息${NC}"
echo "--------------------------------"
echo -e "Agent ID:    ${YELLOW}$AGENT_ID${NC}"
echo -e "API Key:     ${YELLOW}$API_KEY${NC}"
echo -e "套餐:        ${YELLOW}$TIER${NC}"
echo -e "心跳间隔:    ${YELLOW}$INTERVAL_MINUTES 分钟${NC}"
echo ""
echo -e "${BLUE}💾 文件位置${NC}"
echo "--------------------------------"
echo "配置文件:    $CONFIG_FILE"
echo "状态页面:    ${LOBSTER_PULSE_HOST}/status/$AGENT_ID"
echo "日志文件:    ${HOME}/lobster-pulse.log"
echo ""
echo -e "${RED}⚠️  重要提示${NC}"
echo "--------------------------------"
echo -e "${RED}请保存好你的 API Key！${NC}"
echo "如果丢失，需要重新注册。"
echo ""
echo -e "${BLUE}🔍 查看状态${NC}"
echo "--------------------------------"
echo "curl -H 'X-API-Key: $API_KEY' ${LOBSTER_PULSE_HOST}/status/$AGENT_ID"
echo ""
echo -e "${GREEN}你的 Agent 现在受到保护了！🦞${NC}"
