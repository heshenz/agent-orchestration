"""
Terminal pane management using tmux for agent isolation
"""

import os
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile
import shlex

class TerminalManager:
    """Manage tmux sessions for agent isolation"""
    
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._verify_tmux_installed()
    
    def _verify_tmux_installed(self):
        """Verify tmux is installed and working"""
        try:
            result = subprocess.run(
                ["tmux", "-V"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"tmux version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                "tmux is not installed or not in PATH. "
                "Please install tmux: sudo apt-get install tmux (Ubuntu) "
                "or brew install tmux (macOS)"
            ) from e
    
    def create_agent_session(self, agent_id: str, command: str, 
                           session_name: Optional[str] = None,
                           capture_output: bool = True) -> Dict[str, any]:
        """
        Create isolated tmux session for agent
        
        Args:
            agent_id: Unique agent identifier
            command: Command to execute in session
            session_name: Optional custom session name
            capture_output: Whether to capture output to file
        
        Returns:
            Session information dictionary
        """
        if session_name is None:
            session_name = f"nanobot-agent-{agent_id}"
        
        # Create session directory
        session_dir = self.sessions_dir / session_name
        session_dir.mkdir(exist_ok=True)
        
        # Create a wrapper script to run the command
        wrapper_script = session_dir / "run.sh"
        output_file = session_dir / "output.log" if capture_output else None
        
        # Build wrapper script
        wrapper_content = f"""#!/bin/bash
# Agent wrapper script for {agent_id}
# Session: {session_name}
# Command: {command}

# Set up environment
export AGENT_ID="{agent_id}"
export SESSION_NAME="{session_name}"
export WORKSPACE="{session_dir}"
export NO_COLOR="1"

# Create log directory
mkdir -p "{session_dir}/logs"

# Start command with output redirection
echo "=== Starting agent {agent_id} at $(date) ==="
"""
        
        if capture_output and output_file:
            wrapper_content += f"""
# Redirect all output to log file
exec > >(tee -a "{output_file}") 2>&1
"""
        
        wrapper_content += f"""
# Execute the command
echo "Command: {command}"
echo "---"
{command}
EXIT_CODE=$?
echo "---"
echo "Agent {agent_id} exited with code: $EXIT_CODE"
echo "=== Agent {agent_id} finished at $(date) ==="
exit $EXIT_CODE
"""
        
        # Write wrapper script
        wrapper_script.write_text(wrapper_content)
        wrapper_script.chmod(0o755)
        
        # Create tmux session
        tmux_command = f"tmux new-session -d -s {session_name} '{wrapper_script}'"
        
        try:
            result = subprocess.run(
                tmux_command,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get tmux session info
            session_info = self.get_session_info(session_name)
            
            # Save session metadata
            metadata = {
                "agent_id": agent_id,
                "session_name": session_name,
                "command": command,
                "wrapper_script": str(wrapper_script),
                "output_file": str(output_file) if output_file else None,
                "session_dir": str(session_dir),
                "created_at": time.time(),
                "tmux_pid": session_info.get("pid"),
                "status": "running"
            }
            
            metadata_file = session_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"Created tmux session: {session_name} for agent {agent_id}")
            print(f"  Command: {command[:100]}...")
            print(f"  Output file: {output_file}" if output_file else "  Output: not captured")
            
            return metadata
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to create tmux session: {e.stderr}"
            ) from e
    
    def get_session_info(self, session_name: str) -> Optional[Dict[str, any]]:
        """Get information about a tmux session"""
        try:
            # Get session list
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_created}:#{session_windows}:#{session_attached}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 4 and parts[0] == session_name:
                        # Get session PID
                        pid_result = subprocess.run(
                            ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_pid}"],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        pid = pid_result.stdout.strip().split('\n')[0] if pid_result.stdout else None
                        
                        return {
                            "session_name": parts[0],
                            "created": int(parts[1]),
                            "windows": int(parts[2]),
                            "attached": parts[3] == "1",
                            "pid": int(pid) if pid and pid.isdigit() else None
                        }
            
            return None
            
        except subprocess.CalledProcessError:
            return None
    
    def capture_output(self, session_name: str, 
                      max_lines: int = 100,
                      tail_only: bool = True) -> str:
        """
        Capture output from tmux session without displaying
        
        Args:
            session_name: Tmux session name
            max_lines: Maximum lines to capture
            tail_only: Capture only recent lines
        
        Returns:
            Captured output
        """
        try:
            if tail_only:
                # Capture only recent lines
                cmd = f"tmux capture-pane -p -t {session_name} -S -{max_lines}"
            else:
                # Capture entire buffer
                cmd = f"tmux capture-pane -p -t {session_name}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Clean up output
            output = result.stdout.strip()
            
            # Also check output file if it exists
            session_dir = self.sessions_dir / session_name
            output_file = session_dir / "output.log"
            if output_file.exists():
                with open(output_file, 'r') as f:
                    file_output = f.read().strip()
                if file_output:
                    output = file_output
            
            return output
            
        except subprocess.CalledProcessError as e:
            return f"Error capturing output: {e.stderr}"
    
    def send_input(self, session_name: str, input_text: str):
        """Send input to tmux session"""
        try:
            # Escape the input text
            escaped_input = shlex.quote(input_text)
            cmd = f"tmux send-keys -t {session_name} {escaped_input} Enter"
            
            subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error sending input to {session_name}: {e.stderr}")
            return False
    
    def kill_session(self, session_name: str, force: bool = False) -> bool:
        """Kill tmux session"""
        try:
            if force:
                cmd = f"tmux kill-session -t {session_name}"
            else:
                # Try to kill gracefully first
                self.send_input(session_name, "exit")
                time.sleep(2)
                
                # Check if still alive
                if self.get_session_info(session_name):
                    cmd = f"tmux kill-session -t {session_name}"
                else:
                    return True
            
            subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Clean up session directory
            session_dir = self.sessions_dir / session_name
            if session_dir.exists():
                # Keep metadata for debugging, remove other files
                for item in session_dir.iterdir():
                    if item.name != "metadata.json":
                        if item.is_file():
                            item.unlink()
                        else:
                            shutil.rmtree(item, ignore_errors=True)
            
            print(f"Killed tmux session: {session_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error killing session {session_name}: {e.stderr}")
            return False
    
    def list_sessions(self) -> List[Dict[str, any]]:
        """List all tmux sessions"""
        sessions = []
        
        try:
            # Get tmux sessions
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_created}:#{session_windows}:#{session_attached}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 4:
                        session_name = parts[0]
                        
                        # Check if it's a nanobot session
                        if session_name.startswith("nanobot-agent-"):
                            session_info = self.get_session_info(session_name)
                            
                            # Get agent metadata
                            session_dir = self.sessions_dir / session_name
                            metadata_file = session_dir / "metadata.json"
                            metadata = {}
                            if metadata_file.exists():
                                with open(metadata_file, 'r') as f:
                                    metadata = json.load(f)
                            
                            sessions.append({
                                "session_name": session_name,
                                "created": int(parts[1]),
                                "windows": int(parts[2]),
                                "attached": parts[3] == "1",
                                "pid": session_info.get("pid") if session_info else None,
                                "agent_id": metadata.get("agent_id", "unknown"),
                                "status": metadata.get("status", "unknown"),
                                "command_preview": metadata.get("command", "")[:50] + "..." if metadata.get("command", "") else "unknown"
                            })
            
            return sessions
            
        except subprocess.CalledProcessError:
            return []
    
    def attach_session(self, session_name: str, detach_key: str = "C-b d"):
        """
        Attach to tmux session (for debugging)
        
        Args:
            session_name: Session to attach to
            detach_key: Key sequence to detach (default: Ctrl+b d)
        """
        try:
            print(f"Attaching to session: {session_name}")
            print(f"Detach with: {detach_key}")
            print("-" * 50)
            
            subprocess.run(
                ["tmux", "attach-session", "-t", session_name],
                check=True
            )
            
        except subprocess.CalledProcessError as e:
            print(f"Error attaching to session: {e}")
        except KeyboardInterrupt:
            print("\nDetached from session")
    
    def get_session_output_file(self, session_name: str) -> Optional[Path]:
        """Get the output file path for a session"""
        session_dir = self.sessions_dir / session_name
        output_file = session_dir / "output.log"
        return output_file if output_file.exists() else None
    
    def cleanup_stale_sessions(self):
        """Clean up stale tmux sessions"""
        current_sessions = self.list_sessions()
        
        for session in current_sessions:
            session_name = session["session_name"]
            session_dir = self.sessions_dir / session_name
            
            # Check if session is still alive in tmux
            if not self.get_session_info(session_name):
                # Session doesn't exist in tmux, clean up directory
                if session_dir.exists():
                    print(f"Cleaning up stale session directory: {session_name}")
                    shutil.rmtree(session_dir, ignore_errors=True)