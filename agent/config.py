import os
from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    master_url: str = field(default_factory=lambda: os.getenv("MASTER_URL", "http://localhost:8000"))
    agent_token: str = field(default_factory=lambda: os.getenv("AGENT_AUTH_TOKEN", "change-me-agent-token"))
    heartbeat_interval: int = field(default_factory=lambda: int(os.getenv("HEARTBEAT_INTERVAL", "5")))
    health_timeout: int = field(default_factory=lambda: int(os.getenv("HEALTH_TIMEOUT", "180")))
    llama_cpp_bin_dir: str = field(default_factory=lambda: os.getenv("LLAMA_CPP_BIN_DIR", ""))


settings = AgentSettings()
