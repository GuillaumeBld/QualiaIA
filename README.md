# QualiaIA

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Autonomous Business System** — A multi-agent AI holding company that autonomously identifies market opportunities, creates businesses, and operates them with intelligent human oversight.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           QUALIAIS SAS                                  │
│                      (French Holding - SASU)                            │
│                         Paris, France                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  🏛️ COUNCIL (Board of Directors - Critical Decisions)            │  │
│  │  ├─ Claude Sonnet 4      ├─ GPT-4o                                │  │
│  │  ├─ Gemini 2.5 Pro       └─ Grok 3 (Chairman)                     │  │
│  │  Triggers: >$500, legal matters, irreversible actions             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                 ↓                                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  ⚡ OPERATIONS (x-ai/grok-4.1-fast:free via OpenRouter)           │  │
│  │  ├─ Market Scanner       ├─ Product Builder                       │  │
│  │  ├─ Marketing Agent      ├─ Finance Agent                         │  │
│  │  ├─ Legal Agent          └─ Customer Service                      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                 ↓                                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  💰 EXECUTION LAYER                                               │  │
│  │  ├─ x402 Protocol (AI-to-AI payments, agent hiring)               │  │
│  │  ├─ Crypto Wallet (USDC on Base L2)                               │  │
│  │  └─ External APIs (Stripe, DocuSign, etc.)                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │ Venture #1 │  │ Venture #2 │  │ Venture #3 │  │ Venture #N │        │
│  │ E-commerce │  │    SaaS    │  │  Content   │  │    ...     │        │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                         QUALIAIS LLC                                    │
│                    (Wyoming - US Operations)                            │
│                  Privacy + Zero State Income Tax                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## 📡 Communication Channels

| Priority | Channel | Use Case | Response Time |
|----------|---------|----------|---------------|
| 🔴 Critical | Phone/SMS (Twilio) | Security breach, unauthorized tx, emergencies | Immediate |
| 🟠 Urgent | Telegram Bot | Approvals, threshold alerts, council decisions | Minutes |
| 🟡 Standard | Discord Webhooks | Status updates, opportunity alerts | Hours |
| 🟢 Async | Email (SMTP) | Reports, legal documents, summaries | Days |
| ⚪ Passive | Web Dashboard | Monitoring, batch approvals, audit logs | On-demand |

## 💡 Decision Tiers

| Amount | Handler | Process |
|--------|---------|---------|
| < $100 | Autonomous | Grok executes immediately, logs notification |
| $100 - $2,000 | Council | Multi-model deliberation, 66% consensus required |
| > $2,000 | Human | Telegram approval required, timeout = reject |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- OpenRouter API key (free tier available)
- Telegram Bot Token (via @BotFather)
- Crypto wallet with USDC on Base network

### Installation

```bash
# Clone repository
git clone https://github.com/GuillaumeBld/QualiaIA.git
cd QualiaIA

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure
cp config/config.template.yaml config/config.yaml
cp .env.template .env
# Edit both files with your credentials
```

### Configuration

1. **OpenRouter** (required): Get API key at [openrouter.ai](https://openrouter.ai)
2. **Telegram** (required): Create bot via @BotFather, get your user ID via @userinfobot
3. **Twilio** (optional): For SMS/voice alerts
4. **Discord** (optional): Create webhooks for your server
5. **Crypto Wallet** (required): Generate or import wallet, fund with USDC on Base

### Run

```bash
# Development
python -m src.main

# Production (with uvicorn for dashboard)
uvicorn src.api:app --host 0.0.0.0 --port 8080
```

## 📁 Project Structure

```
QualiaIA/
├── src/
│   ├── main.py                 # System entry point & orchestrator
│   ├── api.py                  # FastAPI application
│   ├── communication/
│   │   ├── hub.py              # Central communication router
│   │   └── channels/
│   │       ├── telegram.py     # Telegram bot (primary)
│   │       ├── twilio.py       # SMS & voice calls
│   │       ├── discord.py      # Discord webhooks
│   │       ├── email.py        # SMTP email
│   │       └── dashboard.py    # Web dashboard API
│   ├── council/
│   │   └── deliberation.py     # Multi-model board of directors
│   ├── core/
│   │   ├── wallet.py           # Crypto treasury management
│   │   ├── ventures.py         # Business lifecycle management
│   │   └── state.py            # System state management
│   ├── agents/
│   │   ├── base.py             # Base agent class
│   │   ├── market_scanner.py   # Market opportunity identification
│   │   └── operator.py         # Operational Grok agent
│   ├── x402/
│   │   ├── client.py           # x402 payment client
│   │   └── server.py           # x402 payment server (for selling services)
│   └── legal/
│       ├── compliance.py       # RGPD/CCPA compliance helpers
│       └── entities.py         # Legal entity management
├── config/
│   └── config.template.yaml    # Configuration template
├── scripts/
│   ├── setup_telegram.py       # Telegram bot setup helper
│   └── generate_wallet.py      # Wallet generation utility
├── tests/
│   └── ...                     # Test suite
├── docs/
│   └── ...                     # Documentation
├── .github/workflows/
│   └── deploy.yaml             # CI/CD pipeline
├── requirements.txt
├── .env.template
├── Dockerfile
└── docker-compose.yaml
```

## 🔧 Configuration Reference

See `config/config.template.yaml` for all options. Key sections:

- `openrouter`: LLM provider settings
- `thresholds`: Decision tier amounts
- `wallet`: Crypto wallet and spending limits
- `communication`: Channel credentials
- `compliance`: Legal jurisdiction settings

## 🔐 Security

- **Spending Limits**: Per-transaction and daily caps
- **Whitelist**: Approved addresses for transfers
- **Multi-sig**: Threshold for requiring multiple approvals
- **Audit Logging**: 7-year retention for compliance
- **Rate Limiting**: API and transaction rate limits

## 📜 Legal Structure

### France (QualiaIS SAS)
- Entity: SASU (Société par Actions Simplifiée Unipersonnelle)
- Compliance: RGPD/CNIL, EU AI Act (effective Aug 2026)
- Registration: Via Guichet Unique (procedures.inpi.fr)

### USA (QualiaIA LLC)  
- Entity: Wyoming LLC (privacy + zero state income tax)
- Compliance: CCPA, Colorado AI Act (effective June 2026)
- Registration: Wyoming Secretary of State

## 🛣️ Roadmap

- [x] Communication hub (5 channels)
- [x] Council deliberation system
- [x] Wallet management
- [x] Venture lifecycle
- [ ] x402 agent hiring integration
- [ ] Market opportunity scanner
- [ ] Automated legal entity formation
- [ ] Multi-jurisdiction tax compliance
- [ ] CrewAI/Swarms integration

## 📄 License

MIT License - see [LICENSE](LICENSE)

> **Exploratory stage notice:** This repository represents the exploratory and research phase of QualiaIA. Future production versions of the system may be closed-source and operated as proprietary software by QualiaIS SAS and/or QualiaIA LLC. There is no commitment to release future production code under the MIT or any other open-source license.

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](docs/CONTRIBUTING.md) first.

## ⚠️ Disclaimer

This software is for educational and research purposes. Autonomous financial operations carry risk. Always ensure proper legal compliance in your jurisdiction. Not financial advice.
