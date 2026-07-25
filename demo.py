#!/usr/bin/env python3
"""
Demo of the multi-agent system
"""

import time
from pathlib import Path
from multi_agent import setup_multi_agent_system

def demo_silent_spawn():
    """Demo silent spawn without terminal clutter"""
    print("\n=== Demo 1: Silent Spawn (No Terminal Clutter) ===\n")
    
    # Set up system
    coordinator = setup_multi_agent_system(Path("/tmp/nanobot_demo"))
    
    # Spawn a silent task
    print("Spawning silent research task...")
    task_info = coordinator.spawn_silent(
        task_description="Research Australian hotel transactions over 100 million AUD from 2021-2025",
        agent_type="researcher",
        label="HotelResearch"
    )
    
    print(f"\nTask spawned silently:")
    print(f"  Task ID: {task_info['task_id']}")
    print(f"  Agent ID: {task_info['agent_id']}")
    print(f"  Session: {task_info['session_name']}")
    print(f"  Output file: {task_info.get('output_file', 'Not captured')}")
    print(f"  Status: {task_info['status']}")
    
    # Check status after a moment
    print("\nWaiting 5 seconds for task to start...")
    time.sleep(5)
    
    # Get task result (non-blocking check)
    task_result = coordinator.get_task_result(task_info['task_id'])
    print(f"\nTask status check:")
    print(f"  Status: {task_result.get('status', 'unknown')}")
    print(f"  Agent status: {task_result.get('agent_status', 'unknown')}")
    print(f"  Session alive: {task_result.get('session_alive', False)}")
    
    # Show system status
    status = coordinator.get_system_status()
    print(f"\nSystem status:")
    print(f"  Agents: {status['agents_alive']} alive, {status['agents_dead']} dead")
    print(f"  Tasks: {status['tasks_running']} running, {status['tasks_completed']} completed")
    
    return coordinator, task_info

def demo_coordinated_tasks():
    """Demo coordinated tasks with result aggregation"""
    print("\n\n=== Demo 2: Coordinated Tasks (API Efficient) ===\n")
    
    # Set up new system for demo
    coordinator = setup_multi_agent_system(Path("/tmp/nanobot_coord_demo"))
    
    # Spawn coordinated task
    print("Spawning coordinated research task...")
    coord_info = coordinator.spawn_coordinated(
        main_task="Comprehensive analysis of Australian commercial real estate market 2021-2025",
        label="RealEstateAnalysis",
        subtasks=[
            "Research hotel transactions over 100 million AUD",
            "Analyze office building sales trends",
            "Investigate retail property market changes",
            "Compile overall market insights"
        ],
        agent_types=["researcher", "analyzer", "researcher", "analyzer"]
    )
    
    print(f"\nCoordinated task started:")
    print(f"  Coordination ID: {coord_info['coord_id']}")
    print(f"  Label: {coord_info['label']}")
    print(f"  Subtasks: {coord_info['subtasks']}")
    print(f"  Task IDs: {coord_info['task_ids'][:3]}...")
    print(f"  Coordination file: {coord_info['coord_file']}")
    
    # Monitor progress
    print("\nMonitoring progress (waiting 10 seconds)...")
    for i in range(10):
        time.sleep(1)
        status = coordinator.get_system_status()
        completed = status['tasks_completed']
        total = status['total_tasks']
        print(f"  Progress: {completed}/{total} tasks completed", end='\r')
    print()
    
    # Try to get coordinated results
    print("\nChecking for aggregated results...")
    coord_result = coordinator.get_coordinated_result(coord_info['coord_id'])
    
    if coord_result:
        print(f"Coordination status: {coord_result.get('status', 'unknown')}")
        
        if coord_result.get('status') == 'completed':
            print(f"\n✅ Coordination completed!")
            print(f"   Summary length: {len(coord_result.get('summary', ''))} characters")
            print(f"   Results: {len(coord_result.get('results', []))}")
            
            # Show summary preview
            summary = coord_result.get('summary', '')
            if summary:
                preview = summary[:300] + "..." if len(summary) > 300 else summary
                print(f"\nSummary preview:\n{preview}")
        else:
            print(f"⏳ Coordination still in progress: {coord_result.get('status')}")
    else:
        print("❌ Coordination results not available yet")
    
    return coordinator, coord_info

def demo_system_management():
    """Demo system management features"""
    print("\n\n=== Demo 3: System Management ===\n")
    
    # Set up system
    coordinator = setup_multi_agent_system(Path("/tmp/nanobot_mgmt_demo"))
    
    # Create multiple agents
    print("Creating multiple agents...")
    agent_ids = []
    for i in range(3):
        agent_id = coordinator.create_agent(
            agent_type=["researcher", "analyzer", "developer"][i % 3],
            capabilities=[f"capability_{i}_{j}" for j in range(3)]
        )
        agent_ids.append(agent_id)
        print(f"  Created agent {i+1}: {agent_id}")
    
    # Spawn some tasks
    print("\nSpawning tasks...")
    task_infos = []
    for i, agent_id in enumerate(agent_ids):
        task_info = coordinator.spawn_silent(
            task_description=f"Test task {i+1}: Demonstrate agent capabilities",
            agent_type=coordinator.agents[agent_id]["type"],
            label=f"TestTask{i+1}"
        )
        task_infos.append(task_info)
        print(f"  Spawned task for {agent_id}")
    
    # Show system status
    print("\nSystem status:")
    status = coordinator.get_system_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # List tmux sessions
    print("\nTmux sessions:")
    terminal_mgr = coordinator.terminal_manager
    sessions = terminal_mgr.list_sessions()
    for session in sessions:
        print(f"  {session['session_name']}: {session['status']} (agent: {session['agent_id']})")
    
    # Clean up
    print("\nCleaning up...")
    coordinator.cleanup(keep_results=True)
    print("✅ Cleanup complete")
    
    return coordinator

def main():
    """Run all demos"""
    print("=" * 70)
    print("NANOBOT MULTI-AGENT SYSTEM DEMO")
    print("=" * 70)
    print("\nThis demo shows:")
    print("1. Silent spawn (no terminal clutter)")
    print("2. Coordinated tasks (API efficient)")
    print("3. System management features")
    print("=" * 70)
    
    try:
        # Demo 1
        coord1, task1 = demo_silent_spawn()
        coord1.cleanup()
        
        # Demo 2  
        coord2, task2 = demo_coordinated_tasks()
        coord2.cleanup()
        
        # Demo 3
        coord3 = demo_system_management()
        
        print("\n" + "=" * 70)
        print("DEMO COMPLETE")
        print("=" * 70)
        print("\nKey improvements demonstrated:")
        print("✅ No terminal clutter from subagents")
        print("✅ API-efficient single summaries")
        print("✅ Proper agent isolation with tmux")
        print("✅ File-based communication")
        print("✅ Lifecycle management (no zombies)")
        print("✅ Result aggregation")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()