"""
QualiaIA Configuration Management

Loads and validates configuration from YAML and environment variables.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class OpenRouterConfig(BaseModel):
    """OpenRouter LLM configuration"""
    api_key: str = Field(default="", description="OpenRouter API key")
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    operational_model: str = Field(default="x-ai/grok-4.1-fast:free")
    council_models: List[Dict[str, Any]] = Field(default_factory=list)
    fallback_models: List[str] = Field(default_factory=list)
    requests_per_minute: int = Field(default=60)
    max_retries: int = Field(default=3)
    retry_delay_seconds: int = Field(default=5)
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v.startswith("sk-or-v1-XXXX"):
            raise ValueError(
                "OPENROUTER_API_KEY not configured. "
                "Get your API key at https://openrouter.ai/keys"
            )
        return v


class ThresholdsConfig(BaseModel):
    """Decision threshold configuration"""
    auto_approve_usd: float = Field(default=100)
    council_review_usd: float = Field(default=500)
    human_required_usd: float = Field(default=2000)
    consensus_required: float = Field(default=0.66)
    min_confidence: float = Field(default=0.7)
    council_timeout_seconds: int = Field(default=120)
    approval_timeout_hours: int = Field(default=24)
    reminder_after_hours: int = Field(default=4)


class WalletLimitsConfig(BaseModel):
    """Wallet spending limits"""
    max_single_tx_usd: float = Field(default=1000)
    max_daily_spend_usd: float = Field(default=5000)
    max_weekly_spend_usd: float = Field(default=20000)


class WalletConfig(BaseModel):
    """Crypto wallet configuration"""
    network: str = Field(default="base")
    currency: str = Field(default="USDC")
    rpc_urls: Dict[str, str] = Field(default_factory=dict)
    usdc_contracts: Dict[str, str] = Field(default_factory=dict)
    limits: WalletLimitsConfig = Field(default_factory=WalletLimitsConfig)
    multisig_threshold_usd: float = Field(default=2000)
    max_gas_price_gwei: int = Field(default=50)
    gas_limit_multiplier: float = Field(default=1.2)
    approved_addresses: List[str] = Field(default_factory=list)


class TelegramConfig(BaseModel):
    """Telegram bot configuration"""
    bot_token: str = Field(default="")
    authorized_user_ids: List[int] = Field(default_factory=list)
    parse_mode: str = Field(default="Markdown")
    disable_notification_standard: bool = Field(default=True)
    
    @field_validator('bot_token')
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        if not v or ":" not in v:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN not configured. "
                "Create a bot via @BotFather on Telegram"
            )
        return v
    
    @field_validator('authorized_user_ids', mode='before')
    @classmethod
    def parse_user_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        if isinstance(v, list):
            return [int(x) for x in v]
        return []


class TwilioConfig(BaseModel):
    """Twilio SMS/Voice configuration"""
    enabled: bool = Field(default=False)
    account_sid: str = Field(default="")
    auth_token: str = Field(default="")
    from_number: str = Field(default="")
    to_numbers: List[str] = Field(default_factory=list)
    voice: str = Field(default="alice")
    language: str = Field(default="en-US")
    
    @field_validator('to_numbers', mode='before')
    @classmethod
    def parse_to_numbers(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v or []


class DiscordConfig(BaseModel):
    """Discord webhook configuration"""
    enabled: bool = Field(default=False)
    webhooks: Dict[str, str] = Field(default_factory=dict)


class EmailSmtpConfig(BaseModel):
    """SMTP configuration"""
    host: str = Field(default="smtp.gmail.com")
    port: int = Field(default=587)
    username: str = Field(default="")
    password: str = Field(default="")
    use_tls: bool = Field(default=True)


class EmailConfig(BaseModel):
    """Email configuration"""
    enabled: bool = Field(default=False)
    smtp: EmailSmtpConfig = Field(default_factory=EmailSmtpConfig)
    from_address: str = Field(default="")
    to_addresses: List[str] = Field(default_factory=list)
    
    @field_validator('to_addresses', mode='before')
    @classmethod
    def parse_to_addresses(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v or []


class DashboardConfig(BaseModel):
    """Web dashboard configuration"""
    enabled: bool = Field(default=True)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    api_keys: List[str] = Field(default_factory=list)
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    
    @field_validator('api_keys', mode='before')
    @classmethod
    def parse_api_keys(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v or []
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v or ["*"]


class CommunicationConfig(BaseModel):
    """Communication channels configuration"""
    priority_routing: Dict[str, List[str]] = Field(default_factory=dict)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    twilio: TwilioConfig = Field(default_factory=TwilioConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)


class VenturesConfig(BaseModel):
    """Venture management configuration"""
    min_validation_score: float = Field(default=0.7)
    min_profit_margin: float = Field(default=0.2)
    max_burn_months: int = Field(default=6)
    scale_trigger_revenue_usd: float = Field(default=10000)
    scale_trigger_margin: float = Field(default=0.3)
    shutdown_loss_threshold_usd: float = Field(default=-5000)
    shutdown_consecutive_loss_months: int = Field(default=3)


class X402Config(BaseModel):
    """x402 protocol configuration"""
    enabled: bool = Field(default=True)
    facilitator_url: str = Field(default="https://x402.org/facilitator")
    max_agent_hire_usd: float = Field(default=500)
    max_daily_hires: int = Field(default=10)
    trusted_services: List[str] = Field(default_factory=list)


class MonitoringAlertsConfig(BaseModel):
    """Alert thresholds"""
    wallet_low_balance_usd: float = Field(default=500)
    error_rate_threshold: float = Field(default=0.05)
    response_time_ms: int = Field(default=5000)
    council_timeout_rate: float = Field(default=0.1)


class MonitoringConfig(BaseModel):
    """Monitoring configuration"""
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)
    alerts: MonitoringAlertsConfig = Field(default_factory=MonitoringAlertsConfig)


class AuditConfig(BaseModel):
    """Audit logging configuration"""
    enabled: bool = Field(default=True)
    path: str = Field(default="logs/audit.log")
    retention_days: int = Field(default=2555)  # 7 years


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default="INFO")
    format: str = Field(default="json")
    audit: AuditConfig = Field(default_factory=AuditConfig)


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="sqlite+aiosqlite:///./qualiaIA.db")
    pool_size: int = Field(default=5)
    max_overflow: int = Field(default=10)


class SchedulerConfig(BaseModel):
    """Scheduler configuration"""
    daily_report_hour: int = Field(default=9)
    daily_report_minute: int = Field(default=0)
    health_check_interval: int = Field(default=300)
    market_scan_interval: int = Field(default=3600)
    balance_check_interval: int = Field(default=300)


class QualiaIAConfig(BaseModel):
    """Root configuration model"""
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    wallet: WalletConfig = Field(default_factory=WalletConfig)
    communication: CommunicationConfig = Field(default_factory=CommunicationConfig)
    ventures: VenturesConfig = Field(default_factory=VenturesConfig)
    x402: X402Config = Field(default_factory=X402Config)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)


def substitute_env_vars(config_str: str) -> str:
    """
    Substitute environment variables in config string.
    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.
    """
    # Pattern for ${VAR:-default}
    pattern_with_default = r'\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]*)\}'
    # Pattern for ${VAR}
    pattern_simple = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'
    
    # First replace vars with defaults
    def replace_with_default(match):
        var_name, default = match.groups()
        return os.environ.get(var_name, default)
    
    config_str = re.sub(pattern_with_default, replace_with_default, config_str)
    
    # Then replace simple vars
    def replace_simple(match):
        var_name = match.group(1)
        value = os.environ.get(var_name, "")
        return value
    
    config_str = re.sub(pattern_simple, replace_simple, config_str)
    
    return config_str


def load_config(config_path: Optional[str] = None) -> QualiaIAConfig:
    """
    Load configuration from YAML file with environment variable substitution.
    
    Args:
        config_path: Path to config file. Defaults to config/config.yaml
        
    Returns:
        Validated QualiaIAConfig object
    """
    if config_path is None:
        config_path = os.environ.get("QUALIAIS_CONFIG", "config/config.yaml")
    
    path = Path(config_path)
    
    if not path.exists():
        # Try template
        template_path = Path("config/config.template.yaml")
        if template_path.exists():
            print(f"WARNING: Config not found at {config_path}")
            print(f"Please copy {template_path} to {config_path} and configure")
            path = template_path
        else:
            print(f"WARNING: No config found, using defaults")
            return QualiaIAConfig()
    
    with open(path, 'r') as f:
        config_str = f.read()
    
    # Substitute environment variables
    config_str = substitute_env_vars(config_str)
    
    # Parse YAML
    config_dict = yaml.safe_load(config_str) or {}
    
    # Handle nested structures
    if 'communication' in config_dict:
        comm = config_dict['communication']
        if 'telegram' in comm and 'authorized_user_ids' in comm['telegram']:
            # Handle string to list conversion for user IDs
            user_ids = comm['telegram']['authorized_user_ids']
            if isinstance(user_ids, str):
                comm['telegram']['authorized_user_ids'] = [
                    int(x.strip()) for x in user_ids.split(',') if x.strip().isdigit()
                ]
    
    # Validate and return
    return QualiaIAConfig(**config_dict)


@lru_cache()
def get_config() -> QualiaIAConfig:
    """Get cached configuration singleton"""
    from dotenv import load_dotenv
    load_dotenv()
    return load_config()
