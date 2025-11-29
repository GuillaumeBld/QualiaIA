"""
Tests for QualiaIA x402 Protocol

Tests for both client (hiring agents) and server (offering services).
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
import json
import base64
import time

from src.x402.client import (
    X402Client,
    AgentHire,
    PaymentRequirement,
    X402_DOMAIN,
    USDC_BASE,
)
from src.x402.server import (
    X402Server,
    ServiceDefinition,
    PaymentRecord,
)


class TestPaymentRequirement:
    """Tests for PaymentRequirement parsing"""
    
    def test_from_json(self):
        data = {
            "payment": {
                "recipient": "0x1234567890123456789012345678901234567890",
                "amount": 5000000,  # 5 USDC
                "token": USDC_BASE,
                "network": "base",
                "validUntil": int(time.time()) + 300,
                "nonce": "abc123",
            }
        }
        
        req = PaymentRequirement.from_json(data)
        
        assert req.recipient == "0x1234567890123456789012345678901234567890"
        assert req.amount == 5000000
        assert req.amount_usd == Decimal("5")
        assert req.network == "base"
    
    def test_from_header(self):
        payment_data = {
            "recipient": "0x1234567890123456789012345678901234567890",
            "amount": 2500000,  # 2.5 USDC
            "network": "base",
            "validUntil": int(time.time()) + 300,
            "nonce": "def456",
        }
        header = base64.b64encode(json.dumps(payment_data).encode()).decode()
        
        req = PaymentRequirement.from_header(header)
        
        assert req.amount_usd == Decimal("2.5")
        assert req.nonce == "def456"


class TestAgentHire:
    """Tests for AgentHire dataclass"""
    
    def test_creation(self):
        hire = AgentHire(
            service_url="https://example.com/service",
            task="Test task",
            max_payment=Decimal("10.00"),
        )
        
        assert hire.status == "pending"
        assert hire.max_payment == Decimal("10.00")
        assert hire.id is not None
    
    def test_to_dict(self):
        hire = AgentHire(
            service_url="https://example.com",
            task="Test",
            max_payment=Decimal("5.00"),
        )
        hire.actual_payment = Decimal("3.00")
        hire.status = "completed"
        
        d = hire.to_dict()
        
        assert d["max_payment"] == 5.0
        assert d["actual_payment"] == 3.0
        assert d["status"] == "completed"


class TestX402Client:
    """Tests for X402Client"""
    
    @pytest.fixture
    def client(self):
        with patch.dict('os.environ', {'WALLET_PRIVATE_KEY': ''}):
            client = X402Client()
            client.enabled = True
            client.max_hire = Decimal("100")
            client.max_daily = 10
            return client
    
    def test_daily_limit_tracking(self, client):
        client.daily_hires = 5
        stats = client.get_daily_stats()
        
        assert stats["hires_today"] == 5
        assert stats["hires_limit"] == 10
    
    def test_daily_reset(self, client):
        from datetime import datetime, timedelta
        
        client.daily_hires = 5
        client.daily_spend = Decimal("50")
        client.daily_reset = datetime.now() - timedelta(hours=25)
        
        client._check_daily_reset()
        
        assert client.daily_hires == 0
        assert client.daily_spend == Decimal("0")
    
    @pytest.mark.asyncio
    async def test_hire_validation_disabled(self, client):
        client.enabled = False
        
        hire = await client.hire_agent(
            service_url="https://example.com",
            task="Test",
            max_payment=Decimal("10"),
        )
        
        assert hire.status == "failed"
        assert "disabled" in hire.error.lower()
    
    @pytest.mark.asyncio
    async def test_hire_validation_no_key(self, client):
        client.account = None
        
        hire = await client.hire_agent(
            service_url="https://example.com",
            task="Test",
            max_payment=Decimal("10"),
        )
        
        assert hire.status == "failed"
        assert "signing key" in hire.error.lower()
    
    @pytest.mark.asyncio
    async def test_hire_exceeds_limit(self, client):
        client.account = MagicMock()  # Fake account
        
        hire = await client.hire_agent(
            service_url="https://example.com",
            task="Test",
            max_payment=Decimal("500"),  # Exceeds 100 limit
        )
        
        assert hire.status == "failed"
        assert "exceeds limit" in hire.error.lower()


class TestServiceDefinition:
    """Tests for ServiceDefinition"""
    
    def test_to_dict(self):
        service = ServiceDefinition(
            name="test_service",
            endpoint="/x402/test",
            description="Test service",
            price_usd=Decimal("5.00"),
            handler=lambda x, y: x,
        )
        
        d = service.to_dict()
        
        assert d["name"] == "test_service"
        assert d["price_usd"] == 5.0
        assert "handler" not in d  # Should not expose handler


class TestX402Server:
    """Tests for X402Server"""
    
    @pytest.fixture
    def server(self):
        return X402Server()
    
    def test_register_service(self, server):
        server.register_service(
            name="test",
            endpoint="/x402/test",
            price_usd=Decimal("10.00"),
            handler=lambda task, params: {"result": "ok"},
            description="Test service",
        )
        
        assert "/x402/test" in server.services
        assert server.services["/x402/test"].price_usd == Decimal("10.00")
    
    def test_revenue_tracking(self, server):
        payment = PaymentRecord(
            service="test",
            payer="0x123",
            amount_usd=Decimal("5.00"),
            status="executed",
        )
        
        server._record_payment(payment)
        
        assert server.total_revenue == Decimal("5.00")
        assert len(server.payments) == 1
    
    def test_daily_reset(self, server):
        from datetime import datetime, timedelta
        
        server.daily_revenue = Decimal("100")
        server.daily_reset = datetime.now() - timedelta(hours=25)
        
        server._check_daily_reset()
        
        assert server.daily_revenue == Decimal("0")
    
    def test_payment_history(self, server):
        for i in range(5):
            payment = PaymentRecord(
                service=f"test_{i}",
                payer=f"0x{i}",
                amount_usd=Decimal(str(i)),
                status="executed",
            )
            server.payments.append(payment)
        
        history = server.get_payment_history(limit=3)
        
        assert len(history) == 3
        # Should be most recent first
        assert history[0]["service"] == "test_4"
