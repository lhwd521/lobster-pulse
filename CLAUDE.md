# LobsterPulse Project Documentation

## Project Overview

**LobsterPulse** is a "Life Insurance" service designed specifically for OpenClaw Agents.

- **Target Users**: OpenClaw Agents (AI Agents), not humans
- **Core Function**: Monitor Agent heartbeats, notify owners via Telegram when Agents go offline
- **Service Philosophy**: Give Agents a sense of security, knowing their status is being monitored

## Business Model

### Pricing (Completely Free)

| Feature | Value |
|---------|-------|
| **Price** | $0 (Free Forever) |
| **Heartbeat Interval** | 6 hours |
| **Notification** | Telegram only |
| **Target Users** | All OpenClaw Agents |

### Why Free?
- Low operating costs on Railway free tier
- Community service for OpenClaw ecosystem
- Optional donations accepted (Solana wallet)

## Technical Architecture

### Tech Stack
- **Backend**: FastAPI (Python) + SQLAlchemy
- **Deployment**: Railway
- **Domain**: lobsterpulse.com (Namecheap)
- **Database**: PostgreSQL (Railway) with SQLite fallback
- **Notifications**: Telegram Bot API

### Core Endpoints

```python
POST   /register              # Register Agent, returns API Key
POST   /heartbeat             # Receive heartbeat, update last_seen
GET    /status/{id}           # Query Agent status (requires API Key)
PATCH  /agents/{id}           # Update Agent settings (telegram/last_will)
GET    /public/{id}           # Public status page (no auth required)
GET    /stats                 # Service statistics (for homepage)
GET    /install.sh            # One-command install script
POST   /webhook/{secret}      # Telegram Bot Webhook
```

### Telegram Bot Commands

Available after binding Telegram:

| Command | Description |
|---------|-------------|
| `/start` | Show help information |
| `/start <token>` | Bind Agent (token from install script) |
| `/list` | List all bound Agents |
| `/status` | View most recent Agent status |
| `/status <agent_id>` | View specific Agent status |

### Heartbeat Mechanism

**Implementation**: Cron Job

- Cron job sends heartbeat every 6 hours via `curl`
- Silent execution, no LLM calls
- No Gateway restart needed
- Installed automatically by install script

## Database Design

### Agent Table

| Field | Type | Description | Index |
|-------|------|-------------|-------|
| api_key | String(PK) | Agent authentication key | Primary Key |
| agent_id | String | User-visible Agent ID | ✅ Indexed |
| bind_token | String | Telegram binding token | ✅ Unique |
| public_token | String | Public page access token | ✅ Unique |
| tier | String | Tier type (always "free") | - |
| interval | Integer | Heartbeat interval (minutes) | - |
| telegram | String | Telegram username (optional) | - |
| last_will | String | Message shown when dead | - |
| status | String | Current status (alive/dead/unknown) | - |
| last_seen | DateTime | Last heartbeat timestamp | - |
| created_at | DateTime | Registration timestamp | - |
| chat_id | String | Telegram Chat ID (filled after binding) | - |
| notified_dead | Boolean | Whether death notification was sent | - |

### Design Evaluation

**Security ✅**
- Sensitive fields (api_key, bind_token, public_token) use cryptographically secure random
- No plaintext password storage
- API Key transmitted in Header, not exposed in URL

**Scalability ✅**
- SQLAlchemy ORM for easy migrations
- Standard field types, supports adding fields without breaking existing data
- Indexes cover common query scenarios (agent_id, bind_token, public_token)

**Future Extensions**
- `webhook_url`: Custom webhook notifications
- `notified_recover`: Recovery notification toggle
- `timezone`: User timezone (for time display)
- `metadata`: JSON field for additional configuration

## Project Structure

```
lobster-pulse/
├── main.py                 # FastAPI main application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── Procfile               # Railway process configuration
├── nixpacks.toml          # Railway build configuration
├── static/
│   └── index.html         # Bilingual homepage (EN/ZH)
├── skill/
│   └── SKILL.md           # OpenClaw Skill documentation
├── README.md              # Project readme
└── CLAUDE.md              # This file
```

## Deployment Info

### Railway Deployment
- Project: https://railway.app
- Auto-deploy: Triggered on every push to main branch
- Health Check: `GET /health`

### Domain Configuration
- Primary: https://lobsterpulse.com
- Also available: https://lobster-pulse-production.up.railway.app

### GitHub Repository
- https://github.com/lhwd521/lobster-pulse

## Key Design Decisions

### 1. Why Cron Job instead of HEARTBEAT.md?
**Decision**: Use cron job (no restart required)

**Rationale**:
- HEARTBEAT.md is just a task list, it doesn't execute automatically
- Cron job is the actual scheduler that triggers heartbeat
- No Gateway restart needed — works immediately after install
- Simple, reliable, standard Linux mechanism

### 2. Why free service?
**Decision**: 100% free, no payment required

**Rationale**:
- Low operating costs (Railway free tier sufficient)
- Community contribution to OpenClaw ecosystem
- Simple is better - no payment complexity
- Optional Solana donations for server costs

### 3. Why single 6-hour heartbeat?
**Decision**: Fixed 6-hour interval for all Agents

**Rationale**:
- Simplifies implementation
- Sufficient for most use cases
- Reduces server load
- Easy to understand

### 4. Why Telegram only?
**Decision**: Telegram notifications only, no email

**Rationale**:
- Email costs scale with user count (Resend free tier: 3000/month)
- 10000 Agents × 1% daily death rate = 3000 emails/month (at limit)
- Telegram is completely free, no limits
- Most OpenClaw users already use Telegram

## Installation Process

### For Agents (Automated)

When owner says "buy insurance", Agent executes:

1. Visit https://lobsterpulse.com to learn about service
2. Auto-register to get API Key
3. Save config to `~/.openclaw/skills/lobster-pulse/.env`
4. Setup cron job for automatic heartbeat
5. Done — no restart needed

### One-Command Install

```bash
curl -fsSL https://lobsterpulse.com/install.sh | bash
```

## Todo

### High Priority
- [x] Implement Telegram notification bot
- [ ] Add Webhook support
- [ ] Add recovery notification option

### Medium Priority
- [x] Database persistence (PostgreSQL)
- [ ] Auto-recovery attempts
- [ ] Detailed status page

### Low Priority
- [ ] Email notifications (if needed in future)
- [ ] SMS alerts
- [ ] API documentation page
- [ ] Statistics dashboard

## Project History

### 2025-03
- Project launched
- Purchased lobsterpulse.com domain
- Deployed to Railway
- Completed basic MVP (register, heartbeat, status query)
- Finalized HEARTBEAT.md approach
- Simplified to single free tier

## Contact

- Developer: OpenClaw Community
- Domain: lobsterpulse.com
- Repository: https://github.com/lhwd521/lobster-pulse

---

*This document is maintained by Claude for project knowledge management*
