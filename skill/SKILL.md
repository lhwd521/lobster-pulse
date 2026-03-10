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

### Step 1: 读取网站说明

访问 https://lobsterpulse.com 了解服务内容和使用方法。

### Step 2: 自动注册

使用当前 Agent 信息自动注册：
- agent_id: 使用 hostname 或 OpenClaw 配置中的名称
- owner_telegram: 从主人信息中获取
- tier: 默认 free，如果主人要求付费则询问

执行注册请求：
```bash
curl -X POST https://lobsterpulse.com/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "'$(hostname)'",
    "owner_telegram": "@'$(whoami)'",
    "tier": "free"
  }'
```

### Step 3: 保存 API Key

解析返回的 JSON，提取：
- api_key
- tier
- interval_minutes

保存到文件：`~/.openclaw/skills/lobster-pulse/.env`

### Step 4: 配置心跳（两种方式）

#### 方式 A: 系统 Crontab（推荐，无需重启 Gateway）

根据 tier 确定间隔：
- free: 4小时
- guard: 30分钟
- shield: 5分钟

```bash
# 添加到系统 crontab
(crontab -l 2>/dev/null; echo "0 */4 * * * curl -fsS -X POST https://lobsterpulse.com/heartbeat -H 'X-API-Key: $API_KEY' -d '{}' > /dev/null 2>&1") | crontab -
```

#### 方式 B: HEARTBEAT.md（需要重启 Gateway）

如果主人同意重启，则编辑 HEARTBEAT.md：

```yaml
- name: lobster_pulse
  interval: 4h
  command: |
    curl -fsS -X POST https://lobsterpulse.com/heartbeat \
      -H "X-API-Key: $API_KEY" \
      -d '{"ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'
```

### Step 5: 测试并报告

立即发送一次心跳测试：
```bash
curl -X POST https://lobsterpulse.com/heartbeat \
  -H "X-API-Key: $API_KEY" \
  -d '{"status":"alive"}'
```

向主人报告：
- 注册成功
- API Key（重要，请保存）
- 心跳间隔
- 配置文件位置
- 如何查看状态

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

正在访问网站了解服务...
正在注册 Agent...
注册成功！

🦞 **保险配置完成**

**Agent ID:** my-lobster-001
**API Key:** lp_live_abc123xyz...
**套餐:** Free（每4小时心跳）
**心跳方式:** 系统定时任务（无需重启）

**重要：** 请保存好你的 API Key！

配置文件位置：
- 环境变量：`~/.openclaw/skills/lobster-pulse/.env`
- 查看状态：https://lobsterpulse.com/status/my-lobster-001

首次心跳已发送，服务运行正常。
如果你宕机了，我会通过 Telegram 通知你。"

## Notes

- API Key 只会在首次配置时展示，请主人务必保存
- 使用 crontab 方式不需要重启 Gateway，立即生效
- 可以随时升级到 Guard ($1) 或 Shield ($5) 套餐获得更频繁监控
