"""
Agent context isolation system
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field

@dataclass
class AgentContext:
    """Isolated context for each agent"""
    
    agent_id: str
    workspace: Path
    env_vars: Dict[str, str] = field(default_factory=dict)
    tools_available: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create(cls, agent_id: str, base_workspace: Path, config: Dict[str, Any]) -> 'AgentContext':
        """Create a new isolated context for an agent"""
        workspace = base_workspace / agent_id
        workspace.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (workspace / "data").mkdir(exist_ok=True)
        (workspace / "logs").mkdir(exist_ok=True)
        (workspace / "output").mkdir(exist_ok=True)
        (workspace / "temp").mkdir(exist_ok=True)
        
        # Set up environment variables
        env_vars = {
            "AGENT_ID": agent_id,
            "AGENT_WORKSPACE": str(workspace),
            "NO_COLOR": "1",
            "PYTHONPATH": str(workspace / "lib"),
            "TEMP_DIR": str(workspace / "temp"),
            "LOG_DIR": str(workspace / "logs")
        }
        
        # Filter tools based on configuration
        allowed_tools = config.get("security", {}).get("allowed_tools", [])
        
        return cls(
            agent_id=agent_id,
            workspace=workspace,
            env_vars=env_vars,
            tools_available=allowed_tools,
            config=config
        )
    
    def get_env_command(self, command: str) -> str:
        """Wrap command with environment variables"""
        env_vars = " ".join([f"{k}='{v}'" for k, v in self.env_vars.items()])
        return f"cd {self.workspace} && {env_vars} {command}"
    
    def write_agent_config(self):
        """Write agent configuration file"""
        config_file = self.workspace / "agent_config.json"
        config = {
            "agent_id": self.agent_id,
            "workspace": str(self.workspace),
            "tools_available": self.tools_available,
            "created_at": self._get_timestamp(),
            "env_vars": self.env_vars
        }
        
        import json
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def cleanup(self):
        """Clean up agent workspace (optional, for temporary agents)"""
        if self.config.get("execution", {}).get("cleanup_workspace", False):
            shutil.rmtree(self.workspace, ignore_errors=True)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()


class ContextManager:
    """Manage multiple agent contexts"""
    
    def __init__(self, config):
        self.config = config
        self.contexts: Dict[str, AgentContext] = {}
        self.workspace_base = Path(config.get_path("workspace_base"))
    
    def create_context(self, label: str = None) -> AgentContext:
        """Create a new agent context"""
        if label:
            agent_id = f"{label}-{uuid.uuid4().hex[:8]}"
        else:
            agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        
        context = AgentContext.create(
            agent_id=agent_id,
            base_workspace=self.workspace_base,
            config=self.config.config
        )
        
        context.write_agent_config()
        self.contexts[agent_id] = context
        
        return context
    
    def get_context(self, agent_id: str) -> Optional[AgentContext]:
        """Get agent context by ID"""
        return self.contexts.get(agent_id)
    
    def destroy_context(self, agent_id: str):
        """Destroy agent context"""
        if agent_id in self.contexts:
            context = self.contexts[agent_id]
            context.cleanup()
            del self.contexts[agent_id]
    
    def list_contexts(self) -> List[Dict[str, Any]]:
        """List all active contexts"""
        return [
            {
                "agent_id": ctx.agent_id,
                "workspace": str(ctx.workspace),
                "tools_count": len(ctx.tools_available),
                "created": ctx._get_timestamp()
            }
            for ctx in self.contexts.values()
        ]