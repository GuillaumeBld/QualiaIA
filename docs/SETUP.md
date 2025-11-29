# QualiaIA Setup Guide

## Prerequisites

- Python 3.11+
- OpenRouter API key
- Telegram account
- (Optional) Twilio account
- (Optional) Discord server

## Step-by-Step Setup

### 1. Clone and Install

```bash
git clone https://github.com/GuillaumeBld/QualiaIA.git
cd QualiaIA

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure OpenRouter

1. Go to https://openrouter.ai/keys
2. Create a new API key
3. Set in `.env`:
```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### 3. Create Telegram Bot

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token

Get your user ID:
1. Message @userinfobot on Telegram
2. Note your user ID

Set in `.env`:
```
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_AUTHORIZED_USER_IDS=your_user_id
```

### 4. Generate Wallet (Optional)

```bash
python scripts/generate_wallet.py
```

Save the private key securely and set in `.env`:
```
WALLET_PRIVATE_KEY=0x...
```

Fund with USDC on Base network for transactions.

### 5. Copy Configuration

```bash
cp config/config.template.yaml config/config.yaml
```

Edit `config/config.yaml` with your settings.

### 6. Run

Development:
```bash
python -m src.main
```

Production:
```bash
docker-compose up -d
```

## Verification

1. Send `/status` to your Telegram bot
2. Check http://localhost:8080/health
3. View metrics at http://localhost:9090/metrics

## Troubleshooting

### Telegram bot not responding
- Verify bot token is correct
- Check authorized user IDs include your ID
- Ensure bot is not blocked

### OpenRouter errors
- Verify API key is valid
- Check rate limits on OpenRouter dashboard
- Ensure sufficient credits

### Wallet not working
- Verify RPC URL is accessible
- Check private key format (must start with 0x)
- Ensure network is correct (base by default)
