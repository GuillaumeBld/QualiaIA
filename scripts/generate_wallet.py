#!/usr/bin/env python3
"""
QualiaIA Wallet Generation Script

Generate a new Ethereum-compatible wallet for QualiaIA.
Outputs address and private key.

SECURITY WARNING:
- Never share your private key
- Store it securely (password manager, hardware wallet)
- Never commit private keys to git
- Consider using a hardware wallet for production

Usage:
    python scripts/generate_wallet.py
"""

import os
import sys
import json
from datetime import datetime

try:
    from eth_account import Account
    from web3 import Web3
except ImportError:
    print("Error: web3 and eth-account required")
    print("Run: pip install web3 eth-account")
    sys.exit(1)


def generate_wallet():
    """Generate a new wallet"""
    # Enable mnemonic features
    Account.enable_unaudited_hdwallet_features()
    
    # Generate account with mnemonic
    account, mnemonic = Account.create_with_mnemonic()
    
    return {
        "address": account.address,
        "private_key": account.key.hex(),
        "mnemonic": mnemonic,
    }


def main():
    print("=" * 60)
    print("QualiaIA Wallet Generator")
    print("=" * 60)
    print()
    
    # Generate wallet
    wallet = generate_wallet()
    
    print("🔐 NEW WALLET GENERATED")
    print()
    print(f"Address: {wallet['address']}")
    print()
    print("⚠️  SAVE THESE CREDENTIALS SECURELY - THEY WILL NOT BE SHOWN AGAIN ⚠️")
    print()
    print(f"Private Key: {wallet['private_key']}")
    print()
    print(f"Mnemonic (12 words):")
    print(f"  {wallet['mnemonic']}")
    print()
    print("=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print()
    print("1. Save the private key and mnemonic securely")
    print("2. Add to your .env file:")
    print(f"   WALLET_PRIVATE_KEY={wallet['private_key']}")
    print()
    print("3. Fund your wallet with USDC on Base network:")
    print(f"   - Send USDC to: {wallet['address']}")
    print("   - Base network USDC contract: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
    print()
    print("4. View your wallet:")
    print(f"   - Basescan: https://basescan.org/address/{wallet['address']}")
    print()
    
    # Optionally save to file
    save = input("Save wallet info to file? (y/N): ").strip().lower()
    if save == 'y':
        filename = f"wallet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(wallet, f, indent=2)
        print(f"\n✅ Saved to {filename}")
        print("⚠️  Keep this file secure and delete after transferring to password manager!")
    
    print()
    print("🚀 Wallet ready for QualiaIA!")


if __name__ == "__main__":
    main()
