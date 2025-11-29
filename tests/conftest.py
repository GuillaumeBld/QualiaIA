"""
QualiaIA Test Configuration

Pytest fixtures and configuration.
"""

import asyncio
import os
import pytest

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["OPENROUTER_API_KEY"] = "test-key-for-mocking"
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-TEST"
os.environ["TELEGRAM_AUTHORIZED_USER_IDS"] = "123456789"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return {
        "thresholds": {
            "auto_approve_usd": 100,
            "council_review_usd": 500,
            "human_required_usd": 2000,
        },
        "wallet": {
            "limits": {
                "max_single_tx_usd": 1000,
                "max_daily_spend_usd": 5000,
            }
        }
    }
