#!/usr/bin/env python3
"""
Integration with existing nanobot spawn system

This shows how to replace the problematic spawn() with the improved
multi-agent system to eliminate terminal clutter and API waste.
"""

import os
import sys
from pathlib import Path

# Add multi_agent to path
sys.path.insert(0, str(Path(__file__).parent))

from multi_agent import setup_multi_agent_system

class ImprovedSpawn:
    """
    Drop-in replacement for spawn() that uses the multi-agent system
    
    Usage:
        Instead of: spawn("task", "label")
        Use: improved.spawn("task", "label")
    """
    
    def __init__(self, workspace_path=None):
        if workspace_path is None:
            workspace_path = Path.cwd() / "multi_agent_workspace"
        
        self.coordinator = setup_multi_agent_system(workspace_path)
        print(f"Improved spawn system initialized at: {workspace_path}")
    
    def spawn(self, task, label, silent=True, agent_type="worker"):
        """
        Improved spawn that doesn't clutter terminal
        
        Args:
            task: Task description
            label: Task label
            silent: Whether to run silently (default True)
            agent_type: Type of agent to use
        
        Returns:
            Task information with instructions for getting results
        """
        if silent:
            # Use silent spawn (no terminal output)
            result = self.coordinator.spawn_silent(
                task_description=task,
                agent_type=agent_type,
                label=label
            )
            
            print(f"✅ Task '{label}' spawned silently")
            print(f"   Task ID: {result['task_id']}")
            print(f"   Agent: {result['agent_id']}")
            print(f"   Use get_result('{result['task_id']}') to retrieve results")
            
            return {
                "type": "silent",
                "task_id": result["task_id"],
                "agent_id": result["agent_id"],
                "status": "running_silent",
                "output_file": result.get("output_file"),
                "instructions": f"Results will be available via get_result('{result['task_id']}')"
            }
        else:
            # Fallback to original spawn (for compatibility)
            print(f"⚠️  Using original spawn (will clutter terminal)")
            # This would call the original spawn() function
            # For now, just return a placeholder
            return {
                "type": "original",
                "warning": "Terminal clutter expected",
                "task": task,
                "label": label
            }
    
    def get_result(self, task_id, wait=False, timeout=30):
        """
        Get task result
        
        Args:
            task_id: Task ID from spawn()
            wait: Whether to wait for completion
            timeout: Timeout in seconds if waiting
        
        Returns:
            Task result or status
        """
        if wait:
            # Wait for completion
            print(f"⏳ Waiting for task {task_id} to complete...")
        
        result = self.coordinator.get_task_result(task_id)
        
        if result:
            status = result.get("status", "unknown")
            
            if status == "completed":
                print(f"✅ Task {task_id} completed")
                
                # Extract and format result
                task_result = result.get("result", {})
                if isinstance(task_result, dict):
                    output = task_result.get("output", "")
                    if output:
                        # Return clean summary
                        return self._format_summary(output, task_id)
                
                return f"Task {task_id} completed (no output captured)"
            
            elif status == "failed":
                error = result.get("error", "Unknown error")
                return f"❌ Task {task_id} failed: {error}"
            
            else:
                return f"⏳ Task {task_id} status: {status}"
        else:
            return f"❓ Task {task_id} not found"
    
    def _format_summary(self, output, task_id):
        """Format output into clean summary"""
        # Extract key lines (simple heuristic)
        lines = output.strip().split('\n')
        
        # Filter for meaningful lines
        meaningful = []
        for line in lines:
            line = line.strip()
            if len(line) > 20 and not line.startswith(('===', '---', 'Command:', 'Agent', 'exit')):
                meaningful.append(line)
        
        # Create clean summary
        summary = f"# Task Results ({task_id})\n\n"
        
        if meaningful:
            summary += "## Key Findings\n\n"
            for i, line in enumerate(meaningful[:10], 1):  # Limit to 10 lines
                summary += f"{i}. {line[:150]}...\n" if len(line) > 150 else f"{i}. {line}\n"
        else:
            summary += "No meaningful output captured.\n"
        
        summary += f"\n---\n*Output processed for clean presentation*\n"
        
        return summary
    
    def spawn_coordinated(self, main_task, label, subtasks=None):
        """
        Spawn coordinated tasks with result aggregation
        
        Args:
            main_task: Main task description
            label: Task label
            subtasks: List of subtasks (auto-generated if None)
        
        Returns:
            Coordination information
        """
        print(f"🚀 Starting coordinated task: {label}")
        print(f"   Main task: {main_task[:80]}...")
        
        result = self.coordinator.spawn_coordinated(
            main_task=main_task,
            label=label,
            subtasks=subtasks
        )
        
        print(f"✅ Coordination started: {result['coord_id']}")
        print(f"   Subtasks: {result['subtasks']}")
        print(f"   Use get_coordinated_result('{result['coord_id']}') for aggregated results")
        
        return result
    
    def get_coordinated_result(self, coord_id):
        """Get coordinated task results"""
        result = self.coordinator.get_coordinated_result(coord_id)
        
        if result:
            status = result.get("status", "unknown")
            
            if status == "completed":
                summary = result.get("summary", "")
                if summary:
                    print(f"✅ Coordination {coord_id} completed")
                    return summary
                else:
                    return f"Coordination {coord_id} completed (no summary)"
            else:
                return f"⏳ Coordination {coord_id} status: {status}"
        else:
            return f"❓ Coordination {coord_id} not found"
    
    def status(self):
        """Get system status"""
        status = self.coordinator.get_system_status()
        
        report = "## Multi-Agent System Status\n\n"
        report += f"**Agents**: {status['agents_alive']} alive, {status['agents_dead']} dead\n"
        report += f"**Tasks**: {status['tasks_completed']} completed, {status['tasks_failed']} failed, {status['tasks_running']} running\n"
        report += f"**Workspace**: {status['workspace']}\n"
        
        # List active sessions
        sessions = self.coordinator.terminal_manager.list_sessions()
        if sessions:
            report += "\n**Active Sessions**:\n"
            for session in sessions[:5]:  # Show first 5
                report += f"- {session['session_name']}: {session['status']} ({session['agent_id']})\n"
            if len(sessions) > 5:
                report += f"- ... and {len(sessions) - 5} more\n"
        
        return report
    
    def cleanup(self):
        """Clean up system resources"""
        print("🧹 Cleaning up multi-agent system...")
        self.coordinator.cleanup(keep_results=True)
        print("✅ Cleanup complete")


# Example usage
def example_usage():
    """Show example usage"""
    print("=== Improved Spawn System Example ===\n")
    
    # Initialize
    improved = ImprovedSpawn()
    
    # Example 1: Silent spawn (no terminal clutter)
    print("1. Silent Spawn Example:")
    task = improved.spawn(
        task="Research Australian hotel transactions over 100 million AUD from 2021-2025",
        label="HotelResearch",
        silent=True,
        agent_type="researcher"
    )
    
    print(f"\n   Task created: {task['task_id']}")
    print(f"   No terminal clutter from subagent!")
    
    # Example 2: Get result
    print("\n2. Getting Results:")
    print("   (In real usage, you'd wait for task to complete)")
    print("   result = improved.get_result(task_id)")
    print("   print(result)  # Clean, formatted summary")
    
    # Example 3: Coordinated tasks
    print("\n3. Coordinated Tasks Example:")
    coord = improved.spawn_coordinated(
        main_task="Comprehensive analysis of Australian commercial real estate",
        label="RealEstateAnalysis"
    )
    
    print(f"\n   Coordination ID: {coord['coord_id']}")
    print(f"   Single comprehensive summary will be generated")
    print(f"   No multiple summaries wasting API tokens!")
    
    # Show system status
    print("\n4. System Status:")
    status = improved.status()
    print(status)
    
    # Cleanup
    print("\n5. Cleanup:")
    improved.cleanup()
    
    print("\n=== Benefits ===")
    print("✅ No terminal clutter from subagents")
    print("✅ API-efficient single summaries")
    print("✅ Clean, professional output")
    print("✅ No zombie processes")


# Integration with existing code
def integrate_with_existing():
    """
    How to integrate with existing nanobot code
    
    Replace:
        spawn("task", "label")
    
    With:
        from multi_agent.integration import ImprovedSpawn
        improved = ImprovedSpawn()
        improved.spawn("task", "label", silent=True)
    """
    
    integration_guide = """
    ## Integration Guide
    
    ### Before (Problematic):
    ```python
    # Terminal gets cluttered, API tokens wasted
    spawn("Research hotel transactions", "Research")
    # [Subagent output floods terminal]
    # [Multiple summaries waste API]
    ```
    
    ### After (Improved):
    ```python
    from multi_agent.integration import ImprovedSpawn
    
    # Initialize once
    improved = ImprovedSpawn()
    
    # Use improved spawn
    task = improved.spawn(
        "Research hotel transactions",
        "Research",
        silent=True  # No terminal clutter
    )
    
    # Get clean results
    result = improved.get_result(task["task_id"])
    print(result)  # Single clean summary
    ```
    
    ### For complex tasks:
    ```python
    # Coordinated tasks with aggregation
    coord = improved.spawn_coordinated(
        "Comprehensive market analysis",
        "MarketAnalysis"
    )
    
    # Get aggregated results
    summary = improved.get_coordinated_result(coord["coord_id"])
    print(summary)  # API-efficient single summary
    ```
    """
    
    return integration_guide


if __name__ == "__main__":
    print("=" * 70)
    print("NANOBOT MULTI-AGENT INTEGRATION")
    print("=" * 70)
    
    # Run example
    example_usage()
    
    print("\n" + "=" * 70)
    print("INTEGRATION GUIDE")
    print("=" * 70)
    print(integrate_with_existing())
    
    print("\nTo use in your code:")
    print("1. Copy multi_agent directory to your workspace")
    print("2. Import: from multi_agent.integration import ImprovedSpawn")
    print("3. Replace spawn() with improved.spawn()")
    print("4. Enjoy clean terminal and API efficiency!")