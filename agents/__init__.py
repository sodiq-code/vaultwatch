"""VaultWatch Agent Pipeline"""

from .ai_providers import MultiProviderClient, create_client
from .scanner_agent import ScannerAgent, RawEvent
from .anomaly_agent import AnomalyAgent, AnomalyResult
from .self_correction_agent import SelfCorrectionAgent, CorrectionResult
from .rwa_agent import RWAAgent, EnrichedFinding
from .safety_guard import SafetyGuard, SafetyResult
from .audit_agent import AuditAgent, OnChainRecord
from .intel_agent import IntelAgent, IntelResponse
from .agent_wallet import (
    AgentWallet,
    AgentWalletError,
    AgentWalletUnfunded,
    get_agent_wallet,
)

__all__ = [
    "MultiProviderClient",
    "create_client",
    "ScannerAgent",
    "RawEvent",
    "AnomalyAgent",
    "AnomalyResult",
    "SelfCorrectionAgent",
    "CorrectionResult",
    "RWAAgent",
    "EnrichedFinding",
    "SafetyGuard",
    "SafetyResult",
    "AuditAgent",
    "OnChainRecord",
    "IntelAgent",
    "IntelResponse",
    # CSPR.click AI Agent Skill — server-side agent wallet abstraction
    "AgentWallet",
    "AgentWalletError",
    "AgentWalletUnfunded",
    "get_agent_wallet",
]
