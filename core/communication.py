"""
File-based communication system between agents
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import threading
from queue import Queue, Empty
import uuid

class Message:
    """Message between agents"""
    
    def __init__(self, message_type: str, content: Any, 
                 sender: str, recipient: str,
                 message_id: Optional[str] = None,
                 timestamp: Optional[float] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.message_type = message_type
        self.content = content
        self.sender = sender
        self.recipient = recipient
        self.message_id = message_id or self._generate_id()
        self.timestamp = timestamp or time.time()
        self.metadata = metadata or {}
        self.status = "pending"
        self.delivery_attempts = 0
    
    def _generate_id(self) -> str:
        """Generate unique message ID"""
        unique_str = f"{self.sender}{self.recipient}{self.message_type}{time.time()}{uuid.uuid4()}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "message_id": self.message_id,
            "type": self.message_type,
            "content": self.content,
            "sender": self.sender,
            "recipient": self.recipient,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "status": self.status,
            "delivery_attempts": self.delivery_attempts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create from dictionary"""
        message = cls(
            message_type=data["type"],
            content=data["content"],
            sender=data["sender"],
            recipient=data["recipient"],
            message_id=data.get("message_id"),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {})
        )
        message.status = data.get("status", "pending")
        message.delivery_attempts = data.get("delivery_attempts", 0)
        return message
    
    def mark_delivered(self):
        """Mark message as delivered"""
        self.status = "delivered"
        self.metadata["delivered_at"] = time.time()
    
    def mark_failed(self, error: str):
        """Mark message as failed"""
        self.status = "failed"
        self.metadata["error"] = error
        self.metadata["failed_at"] = time.time()
    
    def increment_attempts(self):
        """Increment delivery attempts"""
        self.delivery_attempts += 1


class MessageQueue:
    """In-memory message queue for real-time communication"""
    
    def __init__(self):
        self.queues: Dict[str, Queue] = {}
        self.lock = threading.Lock()
    
    def create_queue(self, agent_id: str):
        """Create message queue for agent"""
        with self.lock:
            if agent_id not in self.queues:
                self.queues[agent_id] = Queue()
    
    def send(self, message: Message, timeout: Optional[float] = None):
        """Send message to recipient's queue"""
        with self.lock:
            if message.recipient not in self.queues:
                self.create_queue(message.recipient)
            
            try:
                self.queues[message.recipient].put(message, timeout=timeout)
                message.mark_delivered()
                return True
            except Exception as e:
                message.mark_failed(str(e))
                return False
    
    def receive(self, agent_id: str, timeout: Optional[float] = None) -> Optional[Message]:
        """Receive message from agent's queue"""
        with self.lock:
            if agent_id not in self.queues:
                self.create_queue(agent_id)
            
            try:
                return self.queues[agent_id].get(timeout=timeout)
            except Empty:
                return None
    
    def peek(self, agent_id: str) -> Optional[Message]:
        """Peek at next message without removing it"""
        with self.lock:
            if agent_id not in self.queues:
                return None
            
            queue = self.queues[agent_id]
            if queue.empty():
                return None
            
            # Get and re-add message
            try:
                message = queue.get_nowait()
                queue.put_nowait(message)
                return message
            except Exception:
                return None
    
    def clear_queue(self, agent_id: str):
        """Clear agent's message queue"""
        with self.lock:
            if agent_id in self.queues:
                while not self.queues[agent_id].empty():
                    try:
                        self.queues[agent_id].get_nowait()
                    except Empty:
                        break


class FileCommunication:
    """File-based communication between agents"""
    
    def __init__(self, comms_dir: Path):
        self.comms_dir = comms_dir
        self.comms_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.comms_dir / "pending").mkdir(exist_ok=True)
        (self.comms_dir / "delivered").mkdir(exist_ok=True)
        (self.comms_dir / "failed").mkdir(exist_ok=True)
        (self.comms_dir / "archived").mkdir(exist_ok=True)
        
        # In-memory queue for real-time communication
        self.message_queue = MessageQueue()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
    
    def send_message(self, message: Message, 
                    store_to_file: bool = True,
                    use_queue: bool = True) -> bool:
        """
        Send message to recipient
        
        Args:
            message: Message to send
            store_to_file: Whether to store to file (persistent)
            use_queue: Whether to use in-memory queue (real-time)
        
        Returns:
            True if sent successfully
        """
        success = True
        
        # Store to file for persistence
        if store_to_file:
            file_success = self._store_message_to_file(message)
            success = success and file_success
        
        # Use in-memory queue for real-time
        if use_queue:
            queue_success = self.message_queue.send(message)
            success = success and queue_success
        
        return success
    
    def _store_message_to_file(self, message: Message) -> bool:
        """Store message to file"""
        try:
            # Create message file
            timestamp = datetime.fromtimestamp(message.timestamp).strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{message.message_id}.json"
            
            if message.status == "pending":
                file_path = self.comms_dir / "pending" / filename
            elif message.status == "delivered":
                file_path = self.comms_dir / "delivered" / filename
            else:
                file_path = self.comms_dir / "failed" / filename
            
            # Write message to file
            with open(file_path, 'w') as f:
                json.dump(message.to_dict(), f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error storing message to file: {e}")
            return False
    
    def receive_messages(self, agent_id: str, 
                        message_type: Optional[str] = None,
                        use_queue: bool = True,
                        check_files: bool = True) -> List[Message]:
        """
        Receive messages for an agent
        
        Args:
            agent_id: Agent ID to receive messages for
            message_type: Filter by message type
            use_queue: Check in-memory queue
            check_files: Check file-based messages
        
        Returns:
            List of messages
        """
        messages = []
        
        # Check in-memory queue
        if use_queue:
            while True:
                message = self.message_queue.receive(agent_id, timeout=0.1)
                if message is None:
                    break
                
                if message_type is None or message.message_type == message_type:
                    messages.append(message)
        
        # Check file-based messages
        if check_files:
            file_messages = self._load_messages_from_files(agent_id, message_type)
            messages.extend(file_messages)
        
        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp)
        
        return messages
    
    def _load_messages_from_files(self, agent_id: str, 
                                 message_type: Optional[str] = None) -> List[Message]:
        """Load messages from files"""
        messages = []
        
        # Check pending messages
        pending_dir = self.comms_dir / "pending"
        for msg_file in pending_dir.glob("*.json"):
            try:
                with open(msg_file, 'r') as f:
                    data = json.load(f)
                
                if data["recipient"] == agent_id:
                    if message_type is None or data["type"] == message_type:
                        message = Message.from_dict(data)
                        messages.append(message)
                        
                        # Move to delivered directory
                        delivered_file = self.comms_dir / "delivered" / msg_file.name
                        msg_file.rename(delivered_file)
                        
                        # Update status
                        message.mark_delivered()
                        with open(delivered_file, 'w') as f:
                            json.dump(message.to_dict(), f, indent=2)
            
            except Exception as e:
                print(f"Error loading message file {msg_file}: {e}")
        
        return messages
    
    def send_task_result(self, task_id: str, result: Any, 
                        sender: str, recipient: str) -> str:
        """
        Send task result message
        
        Args:
            task_id: Task identifier
            result: Task result
            sender: Sender agent ID
            recipient: Recipient agent ID
        
        Returns:
            Message ID
        """
        message = Message(
            message_type="task_result",
            content={
                "task_id": task_id,
                "result": result,
                "timestamp": time.time()
            },
            sender=sender,
            recipient=recipient,
            metadata={
                "task_id": task_id,
                "result_type": type(result).__name__
            }
        )
        
        self.send_message(message, store_to_file=True, use_queue=True)
        return message.message_id
    
    def send_status_update(self, agent_id: str, status: str, 
                          details: Optional[Dict[str, Any]] = None,
                          recipient: str = "coordinator") -> str:
        """
        Send status update
        
        Args:
            agent_id: Agent ID
            status: Status string
            details: Additional details
            recipient: Recipient agent ID
        
        Returns:
            Message ID
        """
        message = Message(
            message_type="status_update",
            content={
                "agent_id": agent_id,
                "status": status,
                "details": details or {},
                "timestamp": time.time()
            },
            sender=agent_id,
            recipient=recipient,
            metadata={
                "update_type": "status"
            }
        )
        
        self.send_message(message, store_to_file=True, use_queue=True)
        return message.message_id
    
    def broadcast(self, message_type: str, content: Any,
                 sender: str, exclude: Optional[List[str]] = None) -> List[str]:
        """
        Broadcast message to all agents
        
        Args:
            message_type: Message type
            content: Message content
            sender: Sender agent ID
            exclude: List of agent IDs to exclude
        
        Returns:
            List of message IDs
        """
        message_ids = []
        exclude = exclude or []
        
        # Get all agent directories
        agents_dir = self.comms_dir.parent / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    agent_id = agent_dir.name
                    
                    if agent_id not in exclude and agent_id != sender:
                        message = Message(
                            message_type=message_type,
                            content=content,
                            sender=sender,
                            recipient=agent_id
                        )
                        
                        if self.send_message(message, store_to_file=True, use_queue=True):
                            message_ids.append(message.message_id)
        
        return message_ids
    
    def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get message status by ID"""
        # Check all directories
        for status_dir in ["pending", "delivered", "failed", "archived"]:
            dir_path = self.comms_dir / status_dir
            for msg_file in dir_path.glob("*.json"):
                if message_id in msg_file.name:
                    try:
                        with open(msg_file, 'r') as f:
                            data = json.load(f)
                        
                        if data.get("message_id") == message_id:
                            return {
                                "message_id": message_id,
                                "status": status_dir,
                                "file_path": str(msg_file),
                                "data": data
                            }
                    except Exception:
                        continue
        
        return None
    
    def _cleanup_loop(self):
        """Background cleanup loop"""
        while True:
            time.sleep(300)  # Clean up every 5 minutes
            self._cleanup_old_messages()
    
    def _cleanup_old_messages(self, max_age_hours: int = 24):
        """Clean up old messages"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for status_dir in ["delivered", "failed"]:
            dir_path = self.comms_dir / status_dir
            if dir_path.exists():
                for msg_file in dir_path.iterdir():
                    if msg_file.is_file() and msg_file.suffix == ".json":
                        try:
                            with open(msg_file, 'r') as f:
                                data = json.load(f)
                            
                            timestamp = data.get("timestamp", 0)
                            if timestamp < cutoff_time:
                                # Move to archived
                                archived_file = self.comms_dir / "archived" / msg_file.name
                                msg_file.rename(archived_file)
                                
                        except Exception:
                            continue