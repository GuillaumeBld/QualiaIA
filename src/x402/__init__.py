"""
QualiaIA x402 Protocol Integration

Client for hiring external AI agents and server for offering QualiaIA services.
"""

from .client import (
    X402Client,
    AgentHire,
    PaymentRequirement,
    get_x402_client,
)
from .server import (
    X402Server,
    ServiceDefinition,
    PaymentRecord,
    create_x402_server,
)

__all__ = [
    # Client
    "X402Client",
    "AgentHire", 
    "PaymentRequirement",
    "get_x402_client",
    # Server
    "X402Server",
    "ServiceDefinition",
    "PaymentRecord",
    "create_x402_server",
]
