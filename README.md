# Agent Orchestration Framework (outdated)

A multi-agent coordination system for managing parallel AI tasks. Solves terminal clutter, API waste, and process isolation for spawning sub-agents.

## Features

- **Context isolation** — each agent runs in an isolated workspace with restricted permissions
- **Terminal management** — agents run in tmux sessions, output captured to files instead of flooding the terminal
- **File-based communication** — message queues between agents with persistent storage
- **Lifecycle management** — proper process tracking, no zombie processes, graceful cleanup
- **Result aggregation** — single comprehensive summary instead of multiple redundant ones

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python |
| Isolation | tmux sessions |
| Communication | File-based messaging |

## Project Structure

```
├── core/                   # Core framework modules
│   ├── coordinator.py      # Agent coordinator — spawn, manage, aggregate
│   ├── communication.py    # File-based message passing
│   ├── terminal_manager.py # Tmux session management
│   ├── lifecycle.py        # Process lifecycle and cleanup
│   └── context.py          # Agent context isolation
├── demo.py                 # Demo showing silent spawn and coordination
├── integration.py          # Integration helpers
└── __init__.py             # Package entry point
```

## Dependencies

```bash
# Requires tmux
sudo pacman -S tmux        # Arch
sudo apt-get install tmux  # Ubuntu/Debian
```

## Running

```python
from multi_agent import setup_multi_agent_system

coordinator = setup_multi_agent_system("/path/to/workspace")

# Spawn a silent task
task = coordinator.spawn_silent("Research topic", "researcher", "Research")

# Get the clean summary
result = coordinator.get_task_result(task["task_id"])
```

## License

Source available for educational purposes. Contact for usage terms.
