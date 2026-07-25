"""
Nanobot Multi-Agent System

A complete multi-agent architecture with:
- Context isolation for each sub-agent
- Terminal pane management using tmux
- File-based communication system
- Proper lifecycle management
- Result aggregation for API efficiency
"""

from pathlib import Path
from typing import Dict, Any, Optional, List

from .core.coordinator import AgentCoordinator
from .core.agent_context import ContextManager, AgentContext
from .core.terminal_manager import TerminalManager
from .core.communication import FileCommunication, Message
from .core.lifecycle import LifecycleManager

__version__ = "1.0.0"
__all__ = [
    "AgentCoordinator",
    "ContextManager",
    "AgentContext",
    "TerminalManager",
    "FileCommunication",
    "Message",
    "LifecycleManager",
    "setup_multi_agent_system"
]


def setup_multi_agent_system(workspace_path: Optional[Path] = None) -> AgentCoordinator:
    """
    Set up the multi-agent system
    
    Args:
        workspace_path: Optional workspace path (defaults to current workspace)
    
    Returns:
        AgentCoordinator instance
    """
    if workspace_path is None:
        # Default to current workspace
        workspace_path = Path.cwd() / "multi_agent_workspace"
    
    # Create workspace if it doesn't exist
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize coordinator
    coordinator = AgentCoordinator(workspace_path)
    
    print(f"Multi-agent system initialized at: {workspace_path}")
    print(f"Version: {__version__}")
    
    return coordinator


# Example usage
if __name__ == "__main__":
    print("=== Nanobot Multi-Agent System ===\n")
    
    # Set up system
    coordinator = setup_multi_agent_system()
    
    # Get system status
    status = coordinator.get_system_status()
    print("System Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\nReady for multi-agent tasks!")
    print("\nExample usage:")
    print("  coordinator.spawn_silent('Research topic', 'research')")
    print("  coordinator.spawn_coordinated('Complex task', 'label')")
    print("  coordinator.get_system_status()")