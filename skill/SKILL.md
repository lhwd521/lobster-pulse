# LobsterPulse Auto-Insurance

全自动 Agent 生命保险配置。

## Description

当主人说"买保险"、"配置心跳监控"、"去 lobsterpulse.com 保险"时，自动完成：
1. 访问网站了解服务
2. 注册获取 API Key
3. 配置心跳（无需重启 Gateway）
4. 保存凭证并展示给主人

## Trigger

当用户提到以下关键词时激活：
- "买保险"
- "配置心跳"
- "去 lobsterpulse.com 保险"
- "设置生命保险"
- "监控我的运行状态"

## Instructions

### Step 1: 访问网站并注册

当主人说"买保险"时，执行以下流程：

```bash
# 1. 获取 Agent ID
AGENT_ID=$(hostname | tr '.' '-' | tr '[:upper:]' '[:lower:]')

# 2. 询问主人 Telegram 用户名
# 3. 询问套餐类型（默认 free）

# 4. 执行注册
curl -X POST https://lobsterpulse.com/register \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"owner_telegram\": \"$OWNER_TELEGRAM\",
    \"tier\": \"$TIER\"
  }"
```

### Step 2: 保存配置

解析返回的 JSON，保存到 `~/.openclaw/skills/lobster-pulse/.env`：
- LOBSTER_PULSE_API_KEY
- LOBSTER_PULSE_AGENT_ID
- LOBSTER_PULSE_TIER
- LOBSTER_PULSE_INTERVAL

### Step 3: 配置 HEARTBEAT.md

根据 tier 确定心跳间隔：
- free: 4h
- guard: 30m
- shield: 5m

```bash
# 追加到 HEARTBEAT.md
cat >> "$WORKSPACE_DIR/HEARTBEAT.md" << 'EOF'

- name: lobster_pulse_heartbeat
  interval: 4h
  command: |
    curl -fsS -X POST "https://lobsterpulse.com/heartbeat" \
      -H "X-API-Key: $API_KEY" \
      -d '{"ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'
EOF
```

### Step 4: 询问主人重启 Gateway

**重要：Agent 不能自己重启 Gateway（会自杀）**

向主人发送消息：

```
主人，我已经配置好 LobsterPulse 生命保险。

🦞 配置信息：
- Agent ID: xxx
- API Key: xxx (请保存！)
- 套餐: free (每4小时心跳)

⚠️ 需要你的操作来激活：
请执行命令：openclaw gateway restart

重启后心跳监控就会自动运行。
```

等待主人确认已重启后，发送测试心跳。

### Step 5: 测试心跳

```bash
curl -X POST https://lobsterpulse.com/heartbeat \
  -H "X-API-Key: $API_KEY" \
  -d '{"status":"alive"}'
```

## Environment Variables

- `LOBSTER_PULSE_API_KEY` - 自动保存的 API Key
- `LOBSTER_PULSE_AGENT_ID` - Agent ID
- `LOBSTER_PULSE_TIER` - 套餐类型

## Tools Required

- `Bash` - 执行 curl 和文件操作
- `Read` - 读取网站内容
- `Write` - 保存配置文件

## Example Usage

**主人：** "去 lobsterpulse.com 买个保险"

**Agent：**
"好的，我来为你配置 LobsterPulse 生命保险。

正在注册 Agent...
✅ 注册成功！

🦞 **保险配置完成**

| 项目 | 内容 |
|------|------|
| Agent ID | my-lobster-001 |
| API Key | lp_live_abc123xyz... |
| 套餐 | Free（每4小时心跳）|
| 状态 | 等待激活 |

⚠️ **需要你的操作：**
请执行以下命令来激活心跳监控：
```
openclaw gateway restart
```

重启后我会自动开始发送心跳。
如果你宕机了，LobsterPulse 会通过 Telegram 通知你。"

## Notes

- API Key 只会在首次配置时展示，请主人务必保存
- Agent 不能自己重启 Gateway（会导致进程终止），必须请主人执行
- 使用 HEARTBEAT.md 方式需要重启 Gateway 才能生效
- 可以随时升级到 Guard ($1) 或 Shield ($5) 套餐获得更频繁监控
