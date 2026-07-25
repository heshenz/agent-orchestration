"""
Configuration management for multi-agent system
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

class SystemConfig:
    """Manage system configuration"""
    
    DEFAULT_CONFIG = {
        "system": {
            "max_agents": 10,
            "default_timeout": 300,
            "cleanup_interval": 60,
            "log_level": "INFO"
        },
        "paths": {
            "comms_dir": "comms",
            "pid_dir": "pid_files",
            "log_dir": "logs",
            "workspace_base": "workspaces",
            "agents_dir": "agents"
        },
        "execution": {
            "tmux_enabled": False,
            "silent_mode": True,
            "isolate_context": True,
            "store_results": True
        },
        "communication": {
            "message_ttl": 3600,  # 1 hour
            "max_message_size": 1048576,  # 1MB
            "cleanup_old_messages": True
        },
        "security": {
            "allowed_tools": ["read_file", "write_file", "exec", "list_dir", "glob", "grep"],
            "restricted_commands": ["rm -rf", "format", "dd", "shutdown", "mkfs"],
            "workspace_restricted": True
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config" / "system_config.json"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    loaded = json.load(f)
                
                # Merge with defaults
                config = self.DEFAULT_CONFIG.copy()
                self._deep_update(config, loaded)
                return config
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
                return self.DEFAULT_CONFIG.copy()
        else:
            # Create directory and save default config
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _deep_update(self, target: Dict, source: Dict):
        """Deep update dictionary"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the nested dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        
        # Save to file
        self._save_config(self.config)
    
    def get_path(self, path_key: str) -> Path:
        """Get absolute path for a configured path"""
        relative = self.get(f"paths.{path_key}")
        if relative:
            base_dir = Path(__file__).parent.parent
            return base_dir / relative
        raise ValueError(f"Path not found: {path_key}")
    
    def get_allowed_tools(self) -> list:
        """Get list of allowed tools for agents"""
        return self.get("security.allowed_tools", [])
    
    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed"""
        restricted = self.get("security.restricted_commands", [])
        return not any(pattern in command for pattern in restricted)