"""
QualiaIA x402 Client

AI-to-AI payment protocol client for hiring external AI agents.
Implements the x402 HTTP Payment Protocol with EIP-712 signatures.

x402 Protocol: https://x402.org
Reference: https://github.com/coinbase/x402
"""

import asyncio
import base64
import json
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import logging
import uuid

import aiohttp

from ..config import get_config

logger = logging.getLogger(__name__)

# Try to import eth_account for EIP-712 signing
try:
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False
    logger.warning("eth_account not available. Run: pip install eth-account")


# =============================================================================
# x402 Protocol Constants
# =============================================================================

# EIP-712 Domain for x402 payments on Base
X402_DOMAIN = {
    "name": "x402",
    "version": "1",
    "chainId": 8453,  # Base mainnet
}

# EIP-712 Types for payment authorization
X402_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
    ],
    "PaymentAuthorization": [
        {"name": "recipient", "type": "address"},
        {"name": "amount", "type": "uint256"},
        {"name": "token", "type": "address"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}

# USDC contract on Base
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


@dataclass
class PaymentRequirement:
    """Payment details from 402 response"""
    recipient: str
    amount: int  # In token smallest unit (6 decimals for USDC)
    token: str
    network: str
    valid_until: int
    nonce: str
    description: Optional[str] = None
    
    @property
    def amount_usd(self) -> Decimal:
        """Amount in USD (USDC has 6 decimals)"""
        return Decimal(self.amount) / Decimal(10**6)
    
    @classmethod
    def from_header(cls, header_value: str) -> "PaymentRequirement":
        """Parse from X-Payment-Required header"""
        data = json.loads(base64.b64decode(header_value))
        return cls(
            recipient=data["recipient"],
            amount=int(data["amount"]),
            token=data.get("token", USDC_BASE),
            network=data.get("network", "base"),
            valid_until=int(data.get("validUntil", time.time() + 300)),
            nonce=data.get("nonce", os.urandom(32).hex()),
            description=data.get("description"),
        )
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "PaymentRequirement":
        """Parse from JSON body"""
        payment = data.get("payment", data)
        return cls(
            recipient=payment["recipient"],
            amount=int(payment["amount"]),
            token=payment.get("token", USDC_BASE),
            network=payment.get("network", "base"),
            valid_until=int(payment.get("validUntil", time.time() + 300)),
            nonce=payment.get("nonce", os.urandom(32).hex()),
            description=payment.get("description"),
        )


@dataclass
class AgentHire:
    """Record of hiring an external AI agent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    service_url: str = ""
    task: str = ""
    max_payment: Decimal = Decimal("0")
    actual_payment: Optional[Decimal] = None
    status: str = "pending"  # pending, paying, completed, failed, rejected
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tx_hash: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "service_url": self.service_url,
            "task": self.task[:100],
            "max_payment": float(self.max_payment),
            "actual_payment": float(self.actual_payment) if self.actual_payment else None,
            "status": self.status,
            "error": self.error,
            "tx_hash": self.tx_hash,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class X402Client:
    """
    x402 Protocol client for AI-to-AI payments.
    
    The x402 protocol enables AI agents to pay for services using HTTP 402 
    (Payment Required) responses with USDC on Base network.
    
    Flow:
    1. POST to service → Receive 402 with payment requirements
    2. Sign EIP-712 payment authorization with private key
    3. Re-POST with X-Payment header containing signature
    4. Service verifies signature and provides response
    
    Configuration required in .env:
    - WALLET_PRIVATE_KEY: Private key for signing payments
    
    Configuration in config.yaml:
    - x402.enabled: Enable x402 functionality
    - x402.max_agent_hire_usd: Maximum payment per hire
    - x402.max_daily_hires: Daily hire limit
    - x402.trusted_services: Whitelist of trusted service URLs
    """
    
    def __init__(self, config=None, wallet=None):
        if config is None:
            config = get_config().x402
        
        self.config = config
        self.wallet = wallet
        self.enabled = config.enabled
        self.facilitator_url = config.facilitator_url
        self.max_hire = Decimal(str(config.max_agent_hire_usd))
        self.max_daily = config.max_daily_hires
        self.trusted_services = set(config.trusted_services or [])
        
        # Wallet for signing
        self.account = None
        self._load_account()
        
        # Daily tracking
        self.daily_hires = 0
        self.daily_spend = Decimal("0")
        self.daily_reset = datetime.now()
        
        # Hire history
        self.hires: List[AgentHire] = []
        
        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None
    
    def _load_account(self) -> None:
        """Load signing account from private key"""
        if not ETH_ACCOUNT_AVAILABLE:
            logger.warning("eth_account not available - x402 signing disabled")
            return
        
        private_key = os.environ.get("WALLET_PRIVATE_KEY")
        if private_key:
            if not private_key.startswith("0x"):
                private_key = f"0x{private_key}"
            try:
                self.account = Account.from_key(private_key)
                logger.info(f"x402 signing enabled for address: {self.account.address}")
            except Exception as e:
                logger.error(f"Failed to load account: {e}")
        else:
            logger.warning(
                "WALLET_PRIVATE_KEY not set - x402 payments disabled. "
                "Generate with: python scripts/generate_wallet.py"
            )
    
    async def initialize(self) -> None:
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )
        logger.info("x402 client initialized")
    
    async def close(self) -> None:
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def hire_agent(
        self,
        service_url: str,
        task: str,
        max_payment: Decimal,
        parameters: Optional[Dict[str, Any]] = None,
        trust_override: bool = False,
    ) -> AgentHire:
        """
        Hire an external AI agent via x402 protocol.
        
        Args:
            service_url: URL of the x402-enabled service
            task: Task description for the agent
            max_payment: Maximum USD willing to pay
            parameters: Additional parameters for the service
            trust_override: Skip whitelist check (use with caution)
            
        Returns:
            AgentHire record with status and result
        """
        # Create hire record
        hire = AgentHire(
            service_url=service_url,
            task=task,
            max_payment=max_payment,
        )
        
        try:
            # Validate
            self._validate_hire(hire, trust_override)
            
            # Ensure session
            if not self.session:
                await self.initialize()
            
            # Step 1: Initial request to get payment requirements
            logger.info(f"x402: Requesting service {service_url}")
            payment_req = await self._request_service(service_url, task, parameters)
            
            if payment_req is None:
                # Service didn't require payment - free!
                hire.status = "completed"
                hire.actual_payment = Decimal("0")
                hire.completed_at = datetime.now()
                self._record_hire(hire)
                return hire
            
            # Step 2: Check if payment is acceptable
            required_usd = payment_req.amount_usd
            logger.info(f"x402: Service requires ${required_usd} USDC")
            
            if required_usd > max_payment:
                hire.status = "rejected"
                hire.error = f"Service requires ${required_usd}, max is ${max_payment}"
                logger.warning(hire.error)
                self._record_hire(hire)
                return hire
            
            # Step 3: Sign the payment
            hire.status = "paying"
            payment_header = self._sign_payment(payment_req)
            
            if not payment_header:
                hire.status = "failed"
                hire.error = "Failed to sign payment - check WALLET_PRIVATE_KEY"
                self._record_hire(hire)
                return hire
            
            # Step 4: Make the paid request
            logger.info(f"x402: Sending payment authorization to {service_url}")
            result = await self._make_paid_request(
                service_url, task, parameters, payment_header
            )
            
            # Success!
            hire.status = "completed"
            hire.actual_payment = required_usd
            hire.result = result
            hire.completed_at = datetime.now()
            
            # Update daily tracking
            self.daily_hires += 1
            self.daily_spend += required_usd
            
            logger.info(f"x402: Hire {hire.id} completed, paid ${required_usd}")
            
        except Exception as e:
            hire.status = "failed"
            hire.error = str(e)
            logger.error(f"x402 hire failed: {e}")
        
        self._record_hire(hire)
        return hire
    
    def _validate_hire(self, hire: AgentHire, trust_override: bool) -> None:
        """Validate hire request against limits"""
        if not self.enabled:
            raise ValueError("x402 is disabled in configuration")
        
        if not self.account:
            raise ValueError(
                "No signing key available. Set WALLET_PRIVATE_KEY environment variable."
            )
        
        self._check_daily_reset()
        
        if hire.max_payment > self.max_hire:
            raise ValueError(
                f"Max payment ${hire.max_payment} exceeds limit ${self.max_hire}"
            )
        
        if self.daily_hires >= self.max_daily:
            raise ValueError(f"Daily hire limit reached ({self.max_daily})")
        
        if not trust_override and self.trusted_services:
            # Check if URL is in whitelist
            if not any(hire.service_url.startswith(t) for t in self.trusted_services):
                raise ValueError(
                    f"Service not in trusted list: {hire.service_url}. "
                    "Add to x402.trusted_services or use trust_override=True"
                )
    
    async def _request_service(
        self,
        url: str,
        task: str,
        parameters: Optional[Dict[str, Any]],
    ) -> Optional[PaymentRequirement]:
        """Make initial request and parse 402 response"""
        payload = {
            "task": task,
            "parameters": parameters or {},
        }
        
        async with self.session.post(
            url,
            json=payload,
            headers={"Accept": "application/json"},
        ) as response:
            
            if response.status == 200:
                # No payment required
                return None
            
            if response.status == 402:
                # Payment required - parse requirements
                # Check header first
                header = response.headers.get("X-Payment-Required")
                if header:
                    return PaymentRequirement.from_header(header)
                
                # Fall back to body
                body = await response.json()
                return PaymentRequirement.from_json(body)
            
            # Other error
            text = await response.text()
            raise ValueError(f"Service returned {response.status}: {text[:200]}")
    
    def _sign_payment(self, payment_req: PaymentRequirement) -> Optional[str]:
        """
        Sign payment authorization using EIP-712.
        
        Returns base64-encoded X-Payment header value.
        """
        if not self.account:
            return None
        
        # Build EIP-712 typed data
        typed_data = {
            "types": X402_TYPES,
            "primaryType": "PaymentAuthorization",
            "domain": X402_DOMAIN,
            "message": {
                "recipient": payment_req.recipient,
                "amount": payment_req.amount,
                "token": payment_req.token,
                "validAfter": int(time.time()) - 60,  # Valid from 1 min ago
                "validBefore": payment_req.valid_until,
                "nonce": bytes.fromhex(payment_req.nonce.replace("0x", "")),
            },
        }
        
        try:
            # Sign using eth_account's EIP-712 support
            signable = encode_typed_data(full_message=typed_data)
            signed = self.account.sign_message(signable)
            
            # Build payment header
            payment_payload = {
                "scheme": "exact",
                "network": payment_req.network,
                "payload": {
                    "signature": signed.signature.hex(),
                    "authorization": {
                        "from": self.account.address,
                        "to": payment_req.recipient,
                        "value": str(payment_req.amount),
                        "token": payment_req.token,
                        "validAfter": typed_data["message"]["validAfter"],
                        "validBefore": payment_req.valid_until,
                        "nonce": payment_req.nonce,
                    },
                },
            }
            
            # Base64 encode
            return base64.b64encode(
                json.dumps(payment_payload).encode()
            ).decode()
            
        except Exception as e:
            logger.error(f"Failed to sign payment: {e}")
            return None
    
    async def _make_paid_request(
        self,
        url: str,
        task: str,
        parameters: Optional[Dict[str, Any]],
        payment_header: str,
    ) -> Dict[str, Any]:
        """Make the paid request with X-Payment header"""
        payload = {
            "task": task,
            "parameters": parameters or {},
        }
        
        async with self.session.post(
            url,
            json=payload,
            headers={
                "Accept": "application/json",
                "X-Payment": payment_header,
            },
        ) as response:
            
            if response.status == 200:
                return await response.json()
            
            if response.status == 402:
                raise ValueError("Payment was rejected by service")
            
            text = await response.text()
            raise ValueError(f"Paid request failed: {response.status} - {text[:200]}")
    
    def _check_daily_reset(self) -> None:
        """Reset daily counters if 24h has passed"""
        now = datetime.now()
        if now - self.daily_reset > timedelta(hours=24):
            self.daily_hires = 0
            self.daily_spend = Decimal("0")
            self.daily_reset = now
    
    def _record_hire(self, hire: AgentHire) -> None:
        """Record hire in history"""
        self.hires.append(hire)
        # Keep last 1000
        if len(self.hires) > 1000:
            self.hires = self.hires[-1000:]
    
    def get_hire_history(self, limit: int = 50) -> List[AgentHire]:
        """Get recent hire history"""
        return sorted(
            self.hires,
            key=lambda h: h.created_at,
            reverse=True
        )[:limit]
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """Get daily usage statistics"""
        self._check_daily_reset()
        return {
            "hires_today": self.daily_hires,
            "hires_limit": self.max_daily,
            "spend_today_usd": float(self.daily_spend),
            "max_per_hire_usd": float(self.max_hire),
            "signing_available": self.account is not None,
            "signer_address": self.account.address if self.account else None,
        }


# =============================================================================
# Singleton
# =============================================================================

_client: Optional[X402Client] = None


async def get_x402_client() -> X402Client:
    """Get x402 client singleton"""
    global _client
    if _client is None:
        _client = X402Client()
        await _client.initialize()
    return _client
