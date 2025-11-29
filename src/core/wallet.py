"""
QualiaIA Wallet Manager

Crypto treasury management with spending controls.
Supports USDC on Base L2 network.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
import logging
import uuid

from ..config import get_config

logger = logging.getLogger(__name__)

# Web3 is optional
try:
    from web3 import AsyncWeb3
    from eth_account import Account
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.warning("web3 not installed. Run: pip install web3 eth-account")


# ERC20 ABI for balanceOf and transfer
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]


@dataclass
class Transaction:
    """A wallet transaction"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "send"  # send, receive, hire_agent
    amount: Decimal = Decimal("0")
    currency: str = "USDC"
    to_address: str = ""
    from_address: str = ""
    status: str = "pending"  # pending, submitted, confirmed, failed
    timestamp: datetime = field(default_factory=datetime.now)
    tx_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "amount": float(self.amount),
            "currency": self.currency,
            "to_address": self.to_address,
            "from_address": self.from_address,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash,
        }


class WalletManager:
    """
    Crypto wallet management for QualiaIA.
    
    Features:
    - USDC on Base L2 (low fees)
    - Spending limits and controls
    - Transaction simulation
    - Address whitelist
    - Audit logging
    
    Configuration:
    - WALLET_PRIVATE_KEY: Wallet private key (keep secure!)
    - Network: Base mainnet by default
    
    Generate new wallet: python scripts/generate_wallet.py
    """
    
    def __init__(self, config=None):
        if config is None:
            config = get_config().wallet
        
        self.config = config
        self.network = config.network
        
        # RPC URLs
        self.rpc_urls = config.rpc_urls or {
            "base": "https://mainnet.base.org",
            "ethereum": "https://eth.llamarpc.com",
            "polygon": "https://polygon.llamarpc.com",
        }
        
        # USDC contracts
        self.usdc_contracts = config.usdc_contracts or {
            "base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "polygon": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        }
        
        # Spending limits
        self.max_single_tx = Decimal(str(config.limits.max_single_tx_usd))
        self.max_daily = Decimal(str(config.limits.max_daily_spend_usd))
        self.multisig_threshold = Decimal(str(config.multisig_threshold_usd))
        
        # Daily tracking
        self.daily_spent = Decimal("0")
        self.daily_reset_time = datetime.now()
        
        # Approved addresses
        self.approved_addresses = set(
            addr.lower() for addr in (config.approved_addresses or [])
        )
        
        # Transaction history
        self.transactions: List[Transaction] = []
        
        # Web3 connection
        self.w3: Optional[Any] = None
        self.account: Optional[Any] = None
        self.address: Optional[str] = None
    
    async def initialize(self) -> None:
        """Initialize wallet connection"""
        if not WEB3_AVAILABLE:
            logger.warning("Web3 not available - wallet in simulation mode")
            return
        
        rpc_url = self.rpc_urls.get(self.network)
        if not rpc_url:
            raise ValueError(f"Unknown network: {self.network}")
        
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        
        # Load account from private key
        import os
        private_key = os.environ.get("WALLET_PRIVATE_KEY")
        
        if private_key:
            if not private_key.startswith("0x"):
                private_key = f"0x{private_key}"
            
            self.account = Account.from_key(private_key)
            self.address = self.account.address
            logger.info(f"Wallet initialized: {self.address}")
        else:
            logger.warning(
                "WALLET_PRIVATE_KEY not configured. "
                "Generate a wallet with: python scripts/generate_wallet.py"
            )
    
    async def get_balances(self) -> Dict[str, float]:
        """Get wallet balances"""
        if not self.address:
            return {"USDC": 0.0}
        
        balances = {}
        
        try:
            usdc_address = self.usdc_contracts.get(self.network)
            if usdc_address and self.w3:
                contract = self.w3.eth.contract(
                    address=self.w3.to_checksum_address(usdc_address),
                    abi=ERC20_ABI
                )
                
                balance_wei = await contract.functions.balanceOf(
                    self.address
                ).call()
                
                # USDC has 6 decimals
                balances["USDC"] = float(balance_wei) / 1_000_000
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            balances["USDC"] = 0.0
        
        return balances
    
    async def send_payment(
        self,
        to_address: str,
        amount: Decimal,
        currency: str = "USDC",
        metadata: Optional[Dict[str, Any]] = None,
        skip_whitelist: bool = False,
    ) -> Optional[Transaction]:
        """
        Send payment with spending controls.
        
        Args:
            to_address: Recipient address
            amount: Amount in USD
            currency: Currency (USDC)
            metadata: Optional transaction metadata
            skip_whitelist: Skip whitelist check (dangerous!)
            
        Returns:
            Transaction if successful, None if blocked
        """
        # Reset daily limit if needed
        self._check_daily_reset()
        
        # Validate limits
        if amount > self.max_single_tx:
            logger.warning(f"Transaction exceeds single tx limit: ${amount}")
            return None
        
        if self.daily_spent + amount > self.max_daily:
            logger.warning(f"Transaction would exceed daily limit")
            return None
        
        # Check whitelist
        if not skip_whitelist and self.approved_addresses:
            if to_address.lower() not in self.approved_addresses:
                logger.warning(f"Address not in whitelist: {to_address}")
                return None
        
        # Check multisig threshold
        if amount > self.multisig_threshold:
            logger.info(f"Amount ${amount} exceeds multisig threshold - requires approval")
            return None
        
        # Create transaction record
        tx = Transaction(
            type="send",
            amount=amount,
            currency=currency,
            to_address=to_address,
            from_address=self.address or "",
            metadata=metadata,
        )
        
        # Execute if wallet is configured
        if self.w3 and self.account:
            tx = await self._execute_transaction(tx)
        else:
            # Simulation mode
            tx.status = "simulated"
            logger.info(f"[SIMULATION] Would send ${amount} to {to_address}")
        
        if tx.status in ("confirmed", "simulated"):
            self.daily_spent += amount
        
        self.transactions.append(tx)
        return tx
    
    async def _execute_transaction(self, tx: Transaction) -> Transaction:
        """Execute actual blockchain transaction"""
        try:
            usdc_address = self.usdc_contracts.get(self.network)
            contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(usdc_address),
                abi=ERC20_ABI
            )
            
            # Amount in USDC units (6 decimals)
            amount_wei = int(tx.amount * 1_000_000)
            
            # Build transaction
            nonce = await self.w3.eth.get_transaction_count(self.address)
            gas_price = await self.w3.eth.gas_price
            
            tx_data = contract.functions.transfer(
                self.w3.to_checksum_address(tx.to_address),
                amount_wei
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'gasPrice': min(gas_price, self.config.max_gas_price_gwei * 10**9),
                'gas': 100000,
            })
            
            # Sign
            signed = self.account.sign_transaction(tx_data)
            
            # Send
            tx_hash = await self.w3.eth.send_raw_transaction(signed.rawTransaction)
            tx.tx_hash = tx_hash.hex()
            tx.status = "submitted"
            
            # Wait for confirmation
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            tx.status = "confirmed" if receipt.status == 1 else "failed"
            logger.info(f"Transaction {tx.status}: {tx.tx_hash}")
            
        except Exception as e:
            logger.error(f"Transaction error: {e}")
            tx.status = "failed"
        
        return tx
    
    def _check_daily_reset(self) -> None:
        """Reset daily spending if 24h passed"""
        now = datetime.now()
        if now - self.daily_reset_time > timedelta(hours=24):
            self.daily_spent = Decimal("0")
            self.daily_reset_time = now
    
    def add_approved_address(self, address: str) -> None:
        """Add address to whitelist"""
        self.approved_addresses.add(address.lower())
    
    def remove_approved_address(self, address: str) -> None:
        """Remove address from whitelist"""
        self.approved_addresses.discard(address.lower())
    
    def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Get recent transactions"""
        return sorted(
            self.transactions,
            key=lambda t: t.timestamp,
            reverse=True
        )[:limit]


# Singleton
_wallet: Optional[WalletManager] = None


async def get_wallet() -> WalletManager:
    """Get wallet singleton"""
    global _wallet
    if _wallet is None:
        _wallet = WalletManager()
        await _wallet.initialize()
    return _wallet
