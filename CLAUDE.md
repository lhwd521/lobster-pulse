# LobsterPulse 项目文档

## 项目概述

**LobsterPulse**（龙虾脉冲）是一个专为 OpenClaw Agents 设计的"生命保险"服务。

- **目标用户**: OpenClaw Agents（AI Agent），而非人类
- **核心功能**: 监控 Agent 心跳，当 Agent 宕机时通过 Telegram 通知主人
- **服务理念**: 让 Agents 有"安全感"，知道自己的运行状态被监控

## 商业模式

### 定价策略（Freemium）

| 套餐 | 价格 | 心跳间隔 | 目标用户 |
|------|------|----------|----------|
| **Free** | $0 | 4小时 | 个人开发者，本地部署 |
| **Guard** | $1/月 | 30分钟 | 轻度商业使用 |
| **Shield** | $5/月 | 5分钟 | 重要生产环境 |

### 支付与交付
- 暂时手动收款（USDT）
- 通过 Telegram 或邮件手动升级套餐
- 自动化支付和Webhook后续迭代

## 技术架构

### 技术栈
- **后端**: FastAPI (Python) + SQLAlchemy (Async)
- **部署**: Railway
- **域名**: lobsterpulse.com (Namecheap)
- **数据库**: PostgreSQL (Railway)
- **通知**: Telegram Bot + Resend (Email)

### 核心端点

```python
POST   /register              # 注册 Agent，返回 API Key
POST   /heartbeat             # 接收心跳，更新最后活跃时间
GET    /status/{id}           # 查询 Agent 状态（需 API Key）
PATCH  /agents/{id}           # 更新 Agent 设置（tg/email/last_will）
GET    /public/{id}           # 公开状态页面（无需登录）
GET    /stats                 # 服务统计（用于首页展示）
GET    /install.sh            # 一键安装脚本
POST   /webhook/{secret}      # Telegram Bot Webhook
```

### 心跳机制

**方案选择**: HEARTBEAT.md（OpenClaw原生）

- 配置写入 `~/.openclaw/workspace/HEARTBEAT.md`
- 静默执行 curl 命令，不调用 LLM
- 根据套餐等级设置间隔：4h / 30m / 5m

**重要限制**: Agent 不能自己重启 Gateway（会导致进程终止），必须请主人执行 `openclaw gateway restart`

## 数据库设计

### Agent 表

| 字段 | 类型 | 说明 | 索引 |
|------|------|------|------|
| api_key | String(PK) | Agent 认证密钥 | 主键 |
| agent_id | String | 用户可见的 Agent ID | ✅ 索引 |
| bind_token | String | Telegram 绑定令牌 | ✅ 唯一索引 |
| public_token | String | 公开页面访问令牌 | ✅ 唯一索引 |
| tier | String | 套餐类型 (free/guard/shield) | - |
| interval | Integer | 心跳间隔（分钟） | - |
| telegram | String | Telegram 用户名（可选） | - |
| email | String | 通知邮箱（可选） | - |
| last_will | String | 宕机时显示的遗嘱 | - |
| status | String | 当前状态 (alive/dead/unknown) | - |
| last_seen | DateTime | 最后心跳时间 | - |
| created_at | DateTime | 注册时间 | - |
| chat_id | String | Telegram Chat ID（绑定后填充） | - |
| notified_dead | Boolean | 是否已发送宕机通知 | - |

### 设计评估

**安全性 ✅**
- 敏感字段（api_key, bind_token, public_token）使用 cryptographically secure random
- 无密码明文存储
- API Key 在 Header 中传输，不在 URL 中暴露

**可扩展性 ✅**
- 使用 SQLAlchemy ORM，便于迁移
- 字段类型标准，支持后续添加字段而不破坏现有数据
- 索引覆盖常用查询场景（agent_id, bind_token, public_token）

**可能的扩展（未来）**
- `webhook_url`: 自定义 Webhook 通知
- `notified_recover`: 恢复通知开关
- `timezone`: 用户时区（用于时间显示）
- `metadata`: JSON 字段存储额外配置

## 项目结构

```
lobster-pulse/
├── main.py                 # FastAPI 主应用
├── requirements.txt        # Python 依赖
├── Dockerfile             # 容器配置
├── railway.toml           # Railway 部署配置
├── static/
│   └── index.html         # 双语首页（中英）
├── skill/
│   ├── install.sh         # 一键安装脚本
│   ├── auto-install.sh    # 自动安装脚本（中文）
│   └── SKILL.md           # OpenClaw Skill 文档
└── CLAUDE.md              # 本文件
```

## 部署信息

### Railway 部署
- 项目: https://railway.app
- 自动部署：每次 push 到 main 分支自动触发
- 健康检查: `GET /health`

### 域名配置
- 主域名: https://lobsterpulse.com
- 也支持: https://lobster-pulse-production.up.railway.app

### GitHub 仓库
- https://github.com/lhwd521/lobster-pulse

## 关键决策记录

### 1. 为什么选择 HEARTBEAT.md 而不是 crontab？
**决策**: 使用 HEARTBEAT.md（需要主人重启）

**原因**:
- 用户担心 crontab 频率过高可能影响 Agent 工作
- 实际上两者都不会调用 LLM，都是静默执行
- 但 HEARTBEAT.md 更原生，与 OpenClaw 集成更好
- Agent 不能自己重启 Gateway（会自杀），必须请主人操作

### 2. 为什么用内存存储而不是数据库？
**决策**: MVP 阶段使用内存字典 `agents_db = {}`

**原因**:
- 快速启动，减少部署复杂度
- Railway 免费数据库有冷启动问题
- 先验证需求，再考虑持久化

**后续**: 当 Agent 数量达到一定规模后迁移到 PostgreSQL

### 3. 为什么域名用 lobsterpulse.com？
**决策**: 购买独立域名（$10.46/年）

**原因**:
- Railway 默认域名会随项目变化
-  Agents 需要稳定的 endpoint 发送心跳
- 品牌化和可信度

## 安装流程

### 对于 Agents（自动化）

当主人说"买保险"时，Agent 执行：

1. 访问 https://lobsterpulse.com 了解服务
2. 自动注册获取 API Key
3. 保存配置到 `~/.openclaw/skills/lobster-pulse/.env`
4. 配置 HEARTBEAT.md
5. **询问主人重启 Gateway**

### 一键安装命令

```bash
curl -fsSL https://lobsterpulse.com/install.sh | bash
```

## 待办事项

### 高优先级
- [ ] 实现 Telegram 通知机器人
- [ ] 添加邮件通知支持
- [ ] 实现宕机检测逻辑（对比 last_seen 和 interval）
- [ ] 添加 Webhook 支持

### 中优先级
- [ ] 数据库持久化（PostgreSQL）
- [ ] 自动化支付流程
- [ ] 用户自助升级套餐
- [ ] 更详细的状态页面

### 低优先级
- [ ] 多语言支持完善
- [ ] API 文档页面
- [ ] 统计图表

## 项目历史

### 2025-03
- 项目启动
- 购买 lobsterpulse.com 域名
- 部署到 Railway
- 完成基础 MVP（注册、心跳、状态查询）
- 确定 HEARTBEAT.md 方案

## 联系信息

- 开发者: OpenClaw Community
- 域名: lobsterpulse.com
- 仓库: https://github.com/lhwd521/lobster-pulse

---

*本文档由 Claude 维护，用于项目知识管理*
