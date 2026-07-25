"""
Lifecycle management for agents - prevent zombie processes
"""

import os
import signal
import time
import atexit
import threading
from pathlib import Path
from typing import Dict, List, Optional
import json
import psutil

class ProcessInfo:
    """Information about a running process"""
    
    def __init__(self, agent_id: str, pid: int, start_time: float, 
                 command: str, context_path: Path):
        self.agent_id = agent_id
        self.pid = pid
        self.start_time = start_time
        self.command = command
        self.context_path = context_path
        self.status = "running"
        self.last_check = time.time()
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization"""
        return {
            "agent_id": self.agent_id,
            "pid": self.pid,
            "start_time": self.start_time,
            "command": self.command,
            "context_path": str(self.context_path),
            "status": self.status,
            "last_check": self.last_check
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> 'ProcessInfo':
        """Create from dictionary"""
        proc = cls(
            agent_id=data["agent_id"],
            pid=data["pid"],
            start_time=data["start_time"],
            command=data["command"],
            context_path=Path(data["context_path"])
        )
        proc.status = data.get("status", "unknown")
        proc.last_check = data.get("last_check", time.time())
        return proc


class LifecycleManager:
    """Manage agent lifecycle and prevent zombie processes"""
    
    def __init__(self, pid_dir: Path, cleanup_interval: int = 60):
        self.pid_dir = pid_dir
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_interval = cleanup_interval
        self.processes: Dict[str, ProcessInfo] = {}
        self._load_existing_processes()
        
        # Set up cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
        
        # Register cleanup on exit
        atexit.register(self.cleanup_all)
    
    def _load_existing_processes(self):
        """Load existing process information from files"""
        for pid_file in self.pid_dir.glob("*.json"):
            try:
                with open(pid_file, 'r') as f:
                    data = json.load(f)
                
                proc = ProcessInfo.from_dict(data)
                self.processes[proc.agent_id] = proc
                
                # Check if process is still alive
                if not self._is_process_alive(proc.pid):
                    print(f"Cleaning up dead process: {proc.agent_id} (PID: {proc.pid})")
                    self._cleanup_process(proc.agent_id)
            
            except Exception as e:
                print(f"Error loading process file {pid_file}: {e}")
                # Remove corrupted file
                pid_file.unlink(missing_ok=True)
    
    def register_agent(self, agent_id: str, pid: int, 
                      command: str, context_path: Path):
        """Register a new agent process"""
        proc = ProcessInfo(
            agent_id=agent_id,
            pid=pid,
            start_time=time.time(),
            command=command,
            context_path=context_path
        )
        
        self.processes[agent_id] = proc
        self._save_process_info(proc)
        
        print(f"Registered agent: {agent_id} (PID: {pid})")
    
    def _save_process_info(self, proc: ProcessInfo):
        """Save process information to file"""
        pid_file = self.pid_dir / f"{proc.agent_id}.json"
        with open(pid_file, 'w') as f:
            json.dump(proc.to_dict(), f, indent=2)
    
    def _is_process_alive(self, pid: int) -> bool:
        """Check if process is still alive"""
        try:
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def check_agent(self, agent_id: str) -> Optional[Dict[str, any]]:
        """Check agent status"""
        if agent_id not in self.processes:
            return None
        
        proc = self.processes[agent_id]
        alive = self._is_process_alive(proc.pid)
        
        if not alive and proc.status == "running":
            proc.status = "dead"
            self._save_process_info(proc)
        
        proc.last_check = time.time()
        
        return {
            "agent_id": agent_id,
            "pid": proc.pid,
            "alive": alive,
            "status": proc.status,
            "uptime": time.time() - proc.start_time if alive else None,
            "command": proc.command
        }
    
    def terminate_agent(self, agent_id: str, force: bool = False) -> bool:
        """Terminate an agent process"""
        if agent_id not in self.processes:
            return False
        
        proc = self.processes[agent_id]
        
        if not self._is_process_alive(proc.pid):
            # Process already dead
            self._cleanup_process(agent_id)
            return True
        
        try:
            # Try graceful termination first
            os.kill(proc.pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(10):  # 10 * 0.5s = 5 seconds
                time.sleep(0.5)
                if not self._is_process_alive(proc.pid):
                    break
            
            # Force kill if still alive
            if force and self._is_process_alive(proc.pid):
                os.kill(proc.pid, signal.SIGKILL)
                time.sleep(0.5)
        
        except (OSError, ProcessLookupError):
            pass  # Process already terminated
        
        # Clean up
        self._cleanup_process(agent_id)
        return True
    
    def _cleanup_process(self, agent_id: str):
        """Clean up process resources"""
        if agent_id in self.processes:
            proc = self.processes[agent_id]
            
            # Clean up process file
            pid_file = self.pid_dir / f"{agent_id}.json"
            pid_file.unlink(missing_ok=True)
            
            # Remove from tracking
            del self.processes[agent_id]
            
            print(f"Cleaned up process: {agent_id}")
    
    def _cleanup_loop(self):
        """Background cleanup loop"""
        while True:
            time.sleep(self.cleanup_interval)
            self._cleanup_zombies()
    
    def _cleanup_zombies(self):
        """Clean up zombie processes"""
        agents_to_cleanup = []
        
        for agent_id, proc in list(self.processes.items()):
            if not self._is_process_alive(proc.pid):
                agents_to_cleanup.append(agent_id)
        
        for agent_id in agents_to_cleanup:
            print(f"Cleaning up zombie process: {agent_id}")
            self._cleanup_process(agent_id)
    
    def list_agents(self) -> List[Dict[str, any]]:
        """List all tracked agents"""
        agents = []
        
        for agent_id, proc in self.processes.items():
            alive = self._is_process_alive(proc.pid)
            
            agents.append({
                "agent_id": agent_id,
                "pid": proc.pid,
                "alive": alive,
                "status": "running" if alive else "dead",
                "uptime": time.time() - proc.start_time if alive else None,
                "command": proc.command[:100] + "..." if len(proc.command) > 100 else proc.command
            })
        
        return agents
    
    def get_system_stats(self) -> Dict[str, any]:
        """Get system statistics"""
        total = len(self.processes)
        alive = sum(1 for proc in self.processes.values() 
                   if self._is_process_alive(proc.pid))
        
        # Get system process count
        try:
            system_total = len(list(psutil.process_iter()))
        except:
            system_total = "unknown"
        
        return {
            "agents_total": total,
            "agents_alive": alive,
            "agents_dead": total - alive,
            "system_processes": system_total,
            "cleanup_interval": self.cleanup_interval,
            "pid_dir": str(self.pid_dir)
        }
    
    def cleanup_all(self):
        """Clean up all agents (called on exit)"""
        print("Cleaning up all agents...")
        
        for agent_id in list(self.processes.keys()):
            self.terminate_agent(agent_id, force=True)
        
        print("All agents cleaned up")