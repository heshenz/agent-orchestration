"""
Context isolation for each sub-agent
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
import uuid

class AgentContext:
    """Isolated context for each sub-agent"""
    
    def __init__(self, agent_id: str, base_workspace: Path, 
                 parent_context: Optional['AgentContext'] = None):
        self.agent_id = agent_id
        self.base_workspace = base_workspace
        self.parent_context = parent_context
        
        # Create agent workspace
        self.workspace = base_workspace / "agents" / agent_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.workspace / "logs").mkdir(exist_ok=True)
        (self.workspace / "data").mkdir(exist_ok=True)
        (self.workspace / "tmp").mkdir(exist_ok=True)
        (self.workspace / "results").mkdir(exist_ok=True)
        
        # Initialize environment
        self.env_vars = self._create_isolated_env()
        self.tools_available = self._determine_available_tools()
        self.permissions = self._create_permissions()
        
        # Save context metadata
        self._save_metadata()
    
    def _create_isolated_env(self) -> Dict[str, str]:
        """Create isolated environment variables"""
        env = {
            "AGENT_ID": self.agent_id,
            "AGENT_WORKSPACE": str(self.workspace),
            "NO_COLOR": "1",
            "PYTHONPATH": str(self.workspace / "lib"),
            "TMPDIR": str(self.workspace / "tmp"),
            "NANOBOT_AGENT_MODE": "1",
            "NANOBOT_AGENT_ID": self.agent_id
        }
        
        # Inherit some safe environment variables from parent
        safe_vars = [
            "HOME", "USER", "LANG", "PATH", "SHELL",
            "TERM", "EDITOR", "PAGER", "TZ"
        ]
        
        for var in safe_vars:
            if var in os.environ:
                env[var] = os.environ[var]
        
        # Add workspace-specific Python path
        python_paths = []
        if "PYTHONPATH" in os.environ:
            python_paths.append(os.environ["PYTHONPATH"])
        python_paths.append(str(self.workspace / "lib"))
        env["PYTHONPATH"] = ":".join(python_paths)
        
        return env
    
    def _determine_available_tools(self) -> Set[str]:
        """Determine which tools are available to this agent"""
        # Base tools available to all agents
        base_tools = {
            "read_file", "list_dir", "glob", "grep",
            "write_file", "edit_file", "exec"
        }
        
        # If parent context exists, inherit its tools with restrictions
        if self.parent_context:
            parent_tools = self.parent_context.tools_available
            # Remove potentially dangerous tools
            dangerous_tools = {"cron", "spawn", "web_fetch", "web_search"}
            return parent_tools - dangerous_tools
        
        return base_tools
    
    def _create_permissions(self) -> Dict[str, Any]:
        """Create permission settings for this agent"""
        return {
            "file_access": {
                "read": [str(self.workspace), str(self.base_workspace)],
                "write": [str(self.workspace)],
                "execute": [str(self.workspace)]
            },
            "network_access": False,
            "system_access": False,
            "max_execution_time": 300,  # 5 minutes
            "max_memory_mb": 512,
            "max_processes": 5
        }
    
    def _save_metadata(self):
        """Save context metadata to file"""
        metadata = {
            "agent_id": self.agent_id,
            "created_at": self._get_timestamp(),
            "workspace": str(self.workspace),
            "environment": self.env_vars,
            "tools_available": list(self.tools_available),
            "permissions": self.permissions,
            "parent_context": self.parent_context.agent_id if self.parent_context else None
        }
        
        metadata_file = self.workspace / "context.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def get_command_env(self) -> Dict[str, str]:
        """Get environment for command execution"""
        return self.env_vars.copy()
    
    def get_safe_command(self, original_command: str) -> str:
        """Create a safe version of the command with context restrictions"""
        # For now, just return the original command
        # In a real implementation, this would:
        # 1. Validate command against permissions
        # 2. Add resource limits
        # 3. Sandbox if necessary
        return original_command
    
    def create_workspace_snapshot(self, snapshot_name: str) -> Path:
        """Create a snapshot of the workspace"""
        snapshot_dir = self.workspace / "snapshots" / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy workspace contents (excluding large files)
        for item in self.workspace.iterdir():
            if item.name in ["snapshots", "tmp", "logs"]:
                continue
            
            if item.is_file():
                # Skip large files
                if item.stat().st_size < 10 * 1024 * 1024:  # 10MB
                    shutil.copy2(item, snapshot_dir / item.name)
            elif item.is_dir():
                shutil.copytree(item, snapshot_dir / item.name, 
                              ignore=shutil.ignore_patterns('*.log', '*.tmp', '__pycache__'))
        
        # Save snapshot metadata
        snapshot_meta = {
            "snapshot_name": snapshot_name,
            "created_at": self._get_timestamp(),
            "agent_id": self.agent_id,
            "workspace_size": self._get_directory_size(snapshot_dir)
        }
        
        meta_file = snapshot_dir / "snapshot.json"
        with open(meta_file, 'w') as f:
            json.dump(snapshot_meta, f, indent=2)
        
        return snapshot_dir
    
    def cleanup(self, keep_results: bool = True):
        """Clean up agent context"""
        if keep_results:
            # Keep results directory, clean everything else
            for item in self.workspace.iterdir():
                if item.name != "results":
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
        else:
            # Clean everything
            if self.workspace.exists():
                shutil.rmtree(self.workspace, ignore_errors=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get context status"""
        workspace_size = self._get_directory_size(self.workspace)
        
        return {
            "agent_id": self.agent_id,
            "workspace": str(self.workspace),
            "workspace_size_mb": workspace_size / (1024 * 1024),
            "tools_available": len(self.tools_available),
            "permissions": self.permissions,
            "environment_keys": list(self.env_vars.keys()),
            "exists": self.workspace.exists()
        }
    
    def _get_directory_size(self, directory: Path) -> int:
        """Calculate directory size in bytes"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def create_child_context(self, child_id: Optional[str] = None) -> 'AgentContext':
        """Create a child context with restricted permissions"""
        if child_id is None:
            child_id = f"{self.agent_id}-child-{uuid.uuid4().hex[:8]}"
        
        return AgentContext(
            agent_id=child_id,
            base_workspace=self.base_workspace,
            parent_context=self
        )


class ContextManager:
    """Manage multiple agent contexts"""
    
    def __init__(self, base_workspace: Path):
        self.base_workspace = base_workspace
        self.contexts: Dict[str, AgentContext] = {}
        self.contexts_dir = base_workspace / "contexts"
        self.contexts_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing contexts
        self._load_existing_contexts()
    
    def _load_existing_contexts(self):
        """Load existing contexts from disk"""
        for context_dir in (self.base_workspace / "agents").glob("*"):
            if context_dir.is_dir():
                context_file = context_dir / "context.json"
                if context_file.exists():
                    try:
                        with open(context_file, 'r') as f:
                            metadata = json.load(f)
                        
                        agent_id = metadata["agent_id"]
                        # Recreate context (simplified - in real impl would restore state)
                        context = AgentContext(
                            agent_id=agent_id,
                            base_workspace=self.base_workspace,
                            parent_context=None  # Would need to restore parent relationship
                        )
                        self.contexts[agent_id] = context
                        
                    except Exception as e:
                        print(f"Error loading context {context_dir}: {e}")
    
    def create_context(self, agent_id: Optional[str] = None, 
                      parent_id: Optional[str] = None) -> AgentContext:
        """Create a new agent context"""
        if agent_id is None:
            agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        
        parent_context = None
        if parent_id and parent_id in self.contexts:
            parent_context = self.contexts[parent_id]
        
        context = AgentContext(
            agent_id=agent_id,
            base_workspace=self.base_workspace,
            parent_context=parent_context
        )
        
        self.contexts[agent_id] = context
        return context
    
    def get_context(self, agent_id: str) -> Optional[AgentContext]:
        """Get agent context by ID"""
        return self.contexts.get(agent_id)
    
    def delete_context(self, agent_id: str, keep_results: bool = True):
        """Delete agent context"""
        if agent_id in self.contexts:
            context = self.contexts[agent_id]
            context.cleanup(keep_results=keep_results)
            del self.contexts[agent_id]
    
    def list_contexts(self) -> List[Dict[str, Any]]:
        """List all contexts"""
        contexts = []
        
        for agent_id, context in self.contexts.items():
            status = context.get_status()
            contexts.append({
                "agent_id": agent_id,
                "workspace": status["workspace"],
                "workspace_size_mb": status["workspace_size_mb"],
                "tools_available": status["tools_available"],
                "has_parent": context.parent_context is not None
            })
        
        return contexts
    
    def cleanup_all(self, keep_results: bool = True):
        """Clean up all contexts"""
        for agent_id in list(self.contexts.keys()):
            self.delete_context(agent_id, keep_results=keep_results)