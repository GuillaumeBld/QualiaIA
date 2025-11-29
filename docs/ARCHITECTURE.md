# QualiaIA Architecture

## System Overview

QualiaIA is an autonomous AI business system designed to identify market opportunities, create businesses, and operate them with intelligent human oversight.

## Components

### 1. Communication Hub
Central message router supporting multiple channels:
- Telegram (primary, real-time)
- SMS/Voice via Twilio (critical alerts)
- Discord (team notifications)
- Email (formal communications)
- Web Dashboard (monitoring)

### 2. Council Deliberation
Multi-model board of directors using OpenRouter:
- Independent opinions from 4 models
- Weighted voting with confidence scores
- 66% consensus requirement
- Chairman tie-breaker

### 3. Wallet Manager
Crypto treasury management:
- USDC on Base L2 network
- Spending limits and controls
- Address whitelist
- Audit logging

### 4. Venture Manager
Business lifecycle management:
- Creation with council approval
- Performance monitoring
- Scaling/shutdown triggers

### 5. x402 Integration
AI-to-AI payment protocol:
- External agent hiring
- Service provisioning

## Decision Tiers

| Tier | Amount | Handler | Response Time |
|------|--------|---------|---------------|
| 1 | <$100 | Autonomous | Immediate |
| 2 | $100-$2000 | Council | ~2 min |
| 3 | >$2000 | Human | Hours |

## Data Flow

```
User Request → Communication Hub → Decision Engine
                                        ↓
                               Tier Classification
                                        ↓
                    ┌───────────────────┼───────────────────┐
                    ↓                   ↓                   ↓
               Autonomous           Council             Human
              (auto-approve)     (deliberate)        (approval)
                    ↓                   ↓                   ↓
                    └───────────────────┼───────────────────┘
                                        ↓
                                   Execution
                                        ↓
                               State Update + Audit
```

## Security Model

1. **Authentication**: API keys, Telegram user IDs
2. **Authorization**: Spending limits, address whitelist
3. **Audit**: 7-year retention for compliance
4. **Encryption**: TLS for all communications
