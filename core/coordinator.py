"""
Coordinator for multi-agent system with result aggregation
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid

from .agent_context import ContextManager, AgentContext
from .terminal_manager import TerminalManager
from .communication import FileCommunication, Message
from .lifecycle import LifecycleManager


class Task:
    """Represents a task to be executed by agents"""
    
    def __init__(self, task_id: str, description: str, 
                 task_type: str = "general", priority: int = 1):
        self.task_id = task_id
        self.description = description
        self.task_type = task_type
        self.priority = priority
        self.created_at = time.time()
        self.status = "pending"
        self.assigned_agent: Optional[str] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.completed_at: Optional[float] = None
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "type": self.task_type,
            "priority": self.priority,
            "created_at": self.created_at,
            "status": self.status,
            "assigned_agent": self.assigned_agent,
            "result": self.result,
            "error": self.error,
            "completed_at": self.completed_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create from dictionary"""
        task = cls(
            task_id=data["task_id"],
            description=data["description"],
            task_type=data.get("type", "general"),
            priority=data.get("priority", 1)
        )
        task.status = data.get("status", "pending")
        task.assigned_agent = data.get("assigned_agent")
        task.result = data.get("result")
        task.error = data.get("error")
        task.completed_at = data.get("completed_at")
        task.metadata = data.get("metadata", {})
        return task


class AgentCoordinator:
    """Coordinates multiple agents with proper isolation"""
    
    def __init__(self, workspace_path: Path):
        self.workspace = workspace_path
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Initialize subsystems
        self.context_manager = ContextManager(self.workspace)
        self.terminal_manager = TerminalManager(self.workspace / "sessions")
        self.communication = FileCommunication(self.workspace / "comms")
        self.lifecycle_manager = LifecycleManager(self.workspace / "pids")
        
        # Task management
        self.tasks: Dict[str, Task] = {}
        self.agents: Dict[str, Dict[str, Any]] = {}
        
        # Result aggregation
        self.results_dir = self.workspace / "results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_agents,
            daemon=True
        )
        self.monitor_thread.start()
        
        print(f"Agent Coordinator initialized at: {self.workspace}")
    
    def create_agent(self, agent_type: str = "worker", 
                    capabilities: Optional[List[str]] = None,
                    parent_agent: Optional[str] = None) -> str:
        """
        Create a new agent
        
        Args:
            agent_type: Type of agent (worker, researcher, analyzer, etc.)
            capabilities: List of capabilities
            parent_agent: Parent agent ID for context inheritance
        
        Returns:
            Agent ID
        """
        agent_id = f"{agent_type}-{uuid.uuid4().hex[:8]}"
        
        # Create context
        context = self.context_manager.create_context(
            agent_id=agent_id,
            parent_id=parent_agent
        )
        
        # Determine command based on agent type
        if agent_type == "researcher":
            command = "nanobot agent --mode research"
        elif agent_type == "analyzer":
            command = "nanobot agent --mode analyze"
        elif agent_type == "developer":
            command = "nanobot agent --mode code"
        else:
            command = "nanobot agent"
        
        # Store agent information
        self.agents[agent_id] = {
            "id": agent_id,
            "type": agent_type,
            "context": context,
            "capabilities": capabilities or [],
            "parent": parent_agent,
            "created_at": time.time(),
            "status": "idle",
            "current_task": None,
            "tasks_completed": 0,
            "last_active": time.time()
        }
        
        print(f"Created agent: {agent_id} ({agent_type})")
        return agent_id
    
    def spawn_silent(self, task_description: str, 
                    agent_type: str = "worker",
                    label: Optional[str] = None) -> Dict[str, Any]:
        """
        Spawn a task silently (no terminal output)
        
        Args:
            task_description: Task to execute
            agent_type: Type of agent to use
            label: Optional task label
        
        Returns:
            Task information
        """
        # Create task
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            description=task_description,
            task_type=agent_type
        )
        
        # Create agent for this task
        agent_id = self.create_agent(agent_type=agent_type)
        
        # Assign task to agent
        task.assigned_agent = agent_id
        task.status = "assigned"
        self.tasks[task_id] = task
        
        # Update agent status
        self.agents[agent_id]["status"] = "busy"
        self.agents[agent_id]["current_task"] = task_id
        
        # Build command with context
        context = self.agents[agent_id]["context"]
        env_vars = context.get_command_env()
        
        # Create environment string
        env_str = " ".join([f'{k}="{v}"' for k, v in env_vars.items()])
        
        # Build full command
        full_command = f"{env_str} {context.get_safe_command(f'nanobot agent --task \"{task_description}\"')}"
        
        # Create tmux session for silent execution
        session_name = f"agent-{agent_id}"
        session_info = self.terminal_manager.create_agent_session(
            agent_id=agent_id,
            command=full_command,
            session_name=session_name,
            capture_output=True
        )
        
        # Register with lifecycle manager
        if session_info.get("tmux_pid"):
            self.lifecycle_manager.register_agent(
                agent_id=agent_id,
                pid=session_info["tmux_pid"],
                command=full_command,
                context_path=context.workspace
            )
        
        # Send status update
        self.communication.send_status_update(
            agent_id=agent_id,
            status="started",
            details={"task_id": task_id, "command_preview": full_command[:100]}
        )
        
        result = {
            "task_id": task_id,
            "agent_id": agent_id,
            "session_name": session_name,
            "status": "running_silent",
            "output_file": session_info.get("output_file"),
            "created_at": time.time(),
            "instructions": f"Use get_task_result('{task_id}') to retrieve results"
        }
        
        print(f"Spawned silent task: {label or task_id}")
        print(f"  Agent: {agent_id}")
        print(f"  Task: {task_description[:80]}...")
        print(f"  Output stored in: {session_info.get('output_file')}")
        
        return result
    
    def get_task_result(self, task_id: str, 
                       wait_timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Get task result
        
        Args:
            task_id: Task ID
            wait_timeout: Optional timeout to wait for completion
        
        Returns:
            Task result or None if not found
        """
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        
        # Wait for completion if requested
        if wait_timeout and task.status not in ["completed", "failed"]:
            start_time = time.time()
            while time.time() - start_time < wait_timeout:
                if task.status in ["completed", "failed"]:
                    break
                time.sleep(0.5)
        
        # Check agent output
        if task.assigned_agent and task.assigned_agent in self.agents:
            agent = self.agents[task.assigned_agent]
            session_name = f"agent-{task.assigned_agent}"
            
            # Capture output from tmux
            output = self.terminal_manager.capture_output(session_name, max_lines=200)
            
            # Check if session is still running
            session_info = self.terminal_manager.get_session_info(session_name)
            if not session_info:
                task.status = "completed"
                task.completed_at = time.time()
            
            # Update task with output
            if output and not task.result:
                task.result = {
                    "output": output,
                    "agent_id": task.assigned_agent,
                    "session": session_name,
                    "captured_at": time.time()
                }
        
        # Check for messages from agent
        messages = self.communication.receive_messages(
            agent_id="coordinator",
            message_type="task_result"
        )
        
        for message in messages:
            if message.content.get("task_id") == task_id:
                task.result = message.content.get("result")
                task.status = "completed"
                task.completed_at = time.time()
                break
        
        # Return task information
        task_dict = task.to_dict()
        
        # Add additional information
        task_dict["agent_status"] = self.agents.get(task.assigned_agent, {}).get("status") if task.assigned_agent else None
        task_dict["session_alive"] = bool(self.terminal_manager.get_session_info(f"agent-{task.assigned_agent}")) if task.assigned_agent else False
        
        return task_dict
    
    def spawn_coordinated(self, main_task: str, label: str,
                         subtasks: Optional[List[str]] = None,
                         agent_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Spawn coordinated tasks with result aggregation
        
        Args:
            main_task: Main task description
            label: Task label
            subtasks: List of subtasks (auto-generated if None)
            agent_types: List of agent types for each subtask
        
        Returns:
            Coordination information
        """
        # Generate subtasks if not provided
        if subtasks is None:
            subtasks = self._decompose_task(main_task)
        
        # Determine agent types
        if agent_types is None:
            agent_types = ["worker"] * len(subtasks)
        
        print(f"Starting coordinated task: {label}")
        print(f"  Main task: {main_task[:80]}...")
        print(f"  Subtasks: {len(subtasks)}")
        
        # Spawn subtasks silently
        task_infos = []
        for i, (subtask, agent_type) in enumerate(zip(subtasks, agent_types)):
            subtask_label = f"{label}-Subtask{i+1}"
            
            task_info = self.spawn_silent(
                task_description=subtask,
                agent_type=agent_type,
                label=subtask_label
            )
            
            task_infos.append(task_info)
        
        # Create coordination record
        coord_id = f"coord-{uuid.uuid4().hex[:8]}"
        coord_file = self.results_dir / f"{coord_id}.json"
        
        coordination = {
            "coord_id": coord_id,
            "label": label,
            "main_task": main_task,
            "subtasks": subtasks,
            "task_infos": task_infos,
            "created_at": time.time(),
            "status": "running",
            "results": []
        }
        
        with open(coord_file, 'w') as f:
            json.dump(coordination, f, indent=2)
        
        # Start result aggregation thread
        agg_thread = threading.Thread(
            target=self._aggregate_results,
            args=(coord_id, task_infos),
            daemon=True
        )
        agg_thread.start()
        
        return {
            "coord_id": coord_id,
            "label": label,
            "subtasks": len(subtasks),
            "task_ids": [ti["task_id"] for ti in task_infos],
            "coord_file": str(coord_file),
            "status": "coordinating",
            "instructions": f"Use get_coordinated_result('{coord_id}') to get aggregated results"
        }
    
    def _decompose_task(self, task: str) -> List[str]:
        """Decompose task into logical subtasks"""
        task_lower = task.lower()
        
        if any(word in task_lower for word in ["research", "find", "search"]):
            return [
                f"Search for information about: {task}",
                f"Evaluate and filter search results",
                f"Extract key facts and data points",
                f"Organize findings into structured format"
            ]
        elif any(word in task_lower for word in ["analyze", "process data", "data analysis"]):
            return [
                f"Collect relevant data for: {task}",
                f"Clean and prepare the data",
                f"Perform statistical analysis",
                f"Identify patterns and insights",
                f"Generate visualizations if applicable"
            ]
        elif any(word in task_lower for word in ["create", "build", "develop", "write code"]):
            return [
                f"Plan architecture for: {task}",
                f"Implement core functionality",
                f"Add error handling and validation",
                f"Test the implementation",
                f"Document the solution"
            ]
        else:
            return [
                f"Plan approach for: {task}",
                f"Execute the task",
                f"Review and refine results",
                f"Prepare final output"
            ]
    
    def _aggregate_results(self, coord_id: str, task_infos: List[Dict[str, Any]]):
        """Aggregate results from multiple tasks"""
        all_results = []
        
        # Wait for all tasks to complete
        for task_info in task_infos:
            task_id = task_info["task_id"]
            
            # Wait for task completion with timeout
            for _ in range(60):  # 60 * 5s = 5 minutes timeout
                task_result = self.get_task_result(task_id)
                if task_result and task_result.get("status") in ["completed", "failed"]:
                    all_results.append(task_result)
                    break
                time.sleep(5)
        
        # Generate aggregated summary
        summary = self._generate_aggregated_summary(coord_id, all_results)
        
        # Save aggregated results
        coord_file = self.results_dir / f"{coord_id}.json"
        if coord_file.exists():
            with open(coord_file, 'r') as f:
                coordination = json.load(f)
            
            coordination["status"] = "completed"
            coordination["completed_at"] = time.time()
            coordination["results"] = all_results
            coordination["summary"] = summary
            
            with open(coord_file, 'w') as f:
                json.dump(coordination, f, indent=2)
        
        print(f"Coordinated task {coord_id} completed")
        print(f"  Successful tasks: {len([r for r in all_results if r.get('status') == 'completed'])}")
        print(f"  Failed tasks: {len([r for r in all_results if r.get('status') == 'failed'])}")
        print(f"  Summary length: {len(summary)} characters")
    
    def _generate_aggregated_summary(self, coord_id: str, 
                                    results: List[Dict[str, Any]]) -> str:
        """Generate single comprehensive summary from multiple results"""
        successful = [r for r in results if r.get("status") == "completed"]
        failed = [r for r in results if r.get("status") == "failed"]
        
        # Extract outputs
        outputs = []
        for result in successful:
            if result.get("result") and isinstance(result["result"], dict):
                output = result["result"].get("output", "")
                if output:
                    outputs.append(output)
        
        # Generate summary
        summary = f"# Coordinated Task Completion\n\n"
        summary += f"**Coordination ID**: {coord_id}\n"
        summary += f"**Total Tasks**: {len(results)}\n"
        summary += f"**Successful**: {len(successful)}\n"
        summary += f"**Failed**: {len(failed)}\n\n"
        
        if outputs:
            summary += "## Combined Results\n\n"
            
            # Extract key points from each output
            for i, output in enumerate(outputs[:5], 1):  # Limit to top 5
                # Simple extraction of first few lines
                lines = output.strip().split('\n')
                key_lines = [l for l in lines if l and len(l) > 20][:3]
                
                if key_lines:
                    summary += f"**Result {i}**:\n"
                    for line in key_lines:
                        summary += f"- {line[:150]}...\n" if len(line) > 150 else f"- {line}\n"
                    summary += "\n"
        
        if failed:
            summary += "## Failed Tasks\n\n"
            for result in failed:
                summary += f"- Task {result.get('task_id', 'unknown')}: {result.get('error', 'Unknown error')}\n"
        
        summary += f"\n---\n"
        summary += f"*Aggregated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        summary += f"*API-efficient single summary (no redundant outputs)*"
        
        return summary
    
    def get_coordinated_result(self, coord_id: str) -> Optional[Dict[str, Any]]:
        """Get coordinated task results"""
        coord_file = self.results_dir / f"{coord_id}.json"
        
        if not coord_file.exists():
            return None
        
        try:
            with open(coord_file, 'r') as f:
                coordination = json.load(f)
            
            return coordination
        except Exception as e:
            print(f"Error loading coordination {coord_id}: {e}")
            return None
    
    def _monitor_agents(self):
        """Monitor agent status and clean up dead agents"""
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            # Check agent status
            for agent_id, agent_info in list(self.agents.items()):
                session_name = f"agent-{agent_id}"
                session_info = self.terminal_manager.get_session_info(session_name)
                
                if not session_info:
                    # Session is dead
                    if agent_info["status"] != "dead":
                        agent_info["status"] = "dead"
                        agent_info["last_active"] = time.time()
                        
                        # Update any assigned task
                        current_task = agent_info.get("current_task")
                        if current_task and current_task in self.tasks:
                            task = self.tasks[current_task]
                            if task.status not in ["completed", "failed"]:
                                task.status = "failed"
                                task.error = "Agent session died"
                                task.completed_at = time.time()
                        
                        print(f"Agent {agent_id} session died")
                
                elif agent_info["status"] == "busy":
                    # Check if task is complete
                    current_task = agent_info.get("current_task")
                    if current_task and current_task in self.tasks:
                        task = self.tasks[current_task]
                        if task.status in ["completed", "failed"]:
                            agent_info["status"] = "idle"
                            agent_info["current_task"] = None
                            agent_info["tasks_completed"] += 1
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        agents_alive = sum(1 for a in self.agents.values() if a["status"] != "dead")
        tasks_completed = sum(1 for t in self.tasks.values() if t.status == "completed")
        tasks_failed = sum(1 for t in self.tasks.values() if t.status == "failed")
        tasks_running = sum(1 for t in self.tasks.values() if t.status == "assigned")
        
        return {
            "total_agents": len(self.agents),
            "agents_alive": agents_alive,
            "agents_dead": len(self.agents) - agents_alive,
            "total_tasks": len(self.tasks),
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "tasks_running": tasks_running,
            "tasks_pending": len(self.tasks) - tasks_completed - tasks_failed - tasks_running,
            "workspace": str(self.workspace),
            "uptime": "monitoring"  # Would track actual uptime in real implementation
        }
    
    def cleanup(self, keep_results: bool = True):
        """Clean up all resources"""
        print("Cleaning up coordinator resources...")
        
        # Kill all tmux sessions
        sessions = self.terminal_manager.list_sessions()
        for session in sessions:
            self.terminal_manager.kill_session(session["session_name"], force=True)
        
        # Clean up lifecycle manager
        self.lifecycle_manager.cleanup_all()
        
        # Clean up contexts
        self.context_manager.cleanup_all(keep_results=keep_results)
        
        print("Coordinator cleanup complete")