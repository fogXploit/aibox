# Architecture Documentation

Technical overview of aibox architecture, design decisions, and component interactions.

## Table of Contents

1. [Overview](#overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Details](#component-details)
4. [Design Patterns](#design-patterns)
5. [Data Flow](#data-flow)
6. [Extension Points](#extension-points)

---

## Overview

### Technology Stack

**Language:**
- Python 3.11+ (pattern matching, better type hints)

**Core Dependencies:**
- **Typer**: CLI framework with type hints
- **Rich**: Terminal UI and formatting
- **Docker SDK**: Container management (not subprocess!)
- **Pydantic**: Type-safe configuration validation
- **PyYAML**: Configuration file parsing

**Development:**
- **pytest**: Testing framework
- **mypy**: Static type checking
- **ruff**: Fast linting and formatting

---

## High-Level Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────┐
│              CLI Layer                      │
│  (Commands, user interaction, output)       │
│                                             │
│  Files: aibox/cli/                         │
│  - main.py (entry point)                   │
│  - commands/*.py (command modules)         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         Orchestration Layer                 │
│  (Business logic, coordination)             │
│                                             │
│  Files: aibox/containers/                  │
│  - orchestrator.py (main coordinator)      │
└──────────────────┬──────────────────────────┘
                   │
            ┌──────┴─────────┬───────────┐
            ▼                ▼           ▼
┌──────────────────┐  ┌──────────┐  ┌──────────┐
│  Service Layer   │  │ Profile  │  │Provider  │
│  (Core services) │  │ System   │  │ Registry │
│                  │  │          │  │          │
│ - manager.py     │  │ - loader │  │ - base   │
│ - slot.py        │  │ - models │  │ - claude │
│ - volumes.py     │  │ - gener. │  │ - gemini │
└──────────────────┘  └──────────┘  └──────────┘
```

---

## Component Details

### CLI Layer

**Purpose:** Handle user interaction, parse commands, format output

**Key Components:**

**1. main.py**
- Typer app entry point
- Global error handling
- Version information
- Rich console setup

**2. commands/**
- Each command in separate module
- Rich formatting (spinners, tables, panels)
- Input validation
- Error messages with suggestions

---

### Orchestration Layer

**Purpose:** Coordinate services, implement business logic

**Key Component: `ContainerOrchestrator`**

**Responsibilities:**
- Coordinate container lifecycle
- Load configuration
- Select AI provider
- Load profiles
- Build Docker image
- Manage slots
- Prepare volumes

**Methods:**
- `start_container()` - Start new container
- `stop_container()` - Stop and remove container
- `get_container_info()` - Get container details
- `list_containers()` - List all containers for project

---

### Service Layer

**Purpose:** Core functionality, Docker operations

---

### Profile System

**Purpose:** Declarative language/tool environments

---

### Provider System

**Purpose:** Abstract AI provider differences

---

## Data Flow

### Start Container Flow

```
User: aibox start
       │
       ▼
┌──────────────────┐
│ CLI: start.py    │
│ - Parse args     │
│ - Validate input │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│ Orchestrator             │
│ 1. Load config           │
│ 2. Get provider          │
│ 3. Load profiles         │
│ 4. Generate Dockerfile   │
│ 5. Build image           │
│ 6. Prepare volumes       │
│ 7. Create container      │
│ 8. Save slot metadata    │
└────────┬─────────────────┘
         │
    ┌────┴────┬──────┬──────┬──────┐
    ▼         ▼      ▼      ▼      ▼
┌────────┐ ┌────┐ ┌──────┐ ┌────┐ ┌───┐
│Manager │ │Slot│ │Volume│ │Prof│ │Prov│
│        │ │    │ │      │ │ile │ │ider│
└────────┘ └────┘ └──────┘ └────┘ └───┘
```

### Configuration Loading Flow

```
Load Config
    │
    ├─→ Load Global (~/.aibox/config.yml)
    │      │
    │      ├─→ Parse YAML
    │      ├─→ Validate (Pydantic)
    │      └─→ Return GlobalConfig
    │
    ├─→ Load Project (~/.aibox/projects/<hash>/config.yml)
    │      │
    │      ├─→ Parse YAML
    │      ├─→ Validate (Pydantic)
    │      └─→ Return ProjectConfig
    │
    └─→ Merge Configs
           │
           └─→ Return Config (project overrides global)
```

---

## Extension Points

### Adding New Providers

1. **Create provider class:**
   ```python
   # aibox/providers/custom.py
   class CustomProvider(AIProvider):
       # Implement abstract methods
   ```

2. **Register provider:**
   ```python
   # aibox/providers/registry.py
   providers["custom"] = CustomProvider
   ```

3. **Add tests:**
   ```python
   # tests/unit/test_providers.py
   def test_custom_provider():
       provider = CustomProvider()
       assert provider.name == "custom"
   ```

### Adding New Profiles

1. **Create YAML definition:**
   ```yaml
   # aibox/profiles/definitions/custom.yml
   name: custom
   description: Custom profile
   versions: ["1.0"]
   # ... rest of definition
   ```

2. **Validate schema:**
   ```bash
   aibox profile info custom
   ```

### Adding New Commands

1. **Create command module:**
   ```python
   # aibox/cli/commands/custom.py
   @app.command()
   def custom():
       """Custom command."""
   ```

2. **Register in main:**
   ```python
   # aibox/cli/main.py
   from aibox.cli.commands import custom
   app.add_typer(custom.app, name="custom")
   ```

---

## Testing Strategy

### Unit Tests

- **Mocked dependencies**
- **Fast execution** (< 5s for all 295 tests)
- **High coverage** (75%+)

**Example:**
```python
def test_orchestrator_start(mocker):
    # Mock all dependencies
    mock_manager = mocker.Mock()
    mock_slot_manager = mocker.Mock()

    orch = ContainerOrchestrator()
    orch.manager = mock_manager
    orch.slot_manager = mock_slot_manager

    result = orch.start_container(...)

    # Verify interactions
    mock_manager.create_container.assert_called_once()
```

---

## Related Documentation

- [Getting Started](getting-started.md) - Using aibox
- [Configuration](configuration.md) - Config system
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guide
