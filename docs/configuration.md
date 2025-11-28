# Configuration Reference

Complete reference for aibox configuration files. aibox uses YAML configuration with Pydantic validation for type safety and helpful error messages.

## Table of Contents

1. [Configuration Layers](#configuration-layers)
2. [Global Configuration](#global-configuration)
3. [Project Configuration](#project-configuration)
4. [Configuration Merging](#configuration-merging)
5. [Environment Variables](#environment-variables)
6. [Examples](#examples)
7. [Validation](#validation)

---

## Configuration Layers

aibox uses a two-layer configuration system with centralized storage:

```
┌──────────────────────────────────────────┐
│   Project Configuration                  │  ← Highest priority
│   ~/.aibox/projects/<hash>/config.yml   │
│   (project-specific settings)            │
└──────────────────────────────────────────┘
             ↓ overrides
┌──────────────────────────────────────────┐
│   Global Configuration                   │  ← Default values
│   ~/.aibox/config.yml                    │
│   (user-wide defaults)                   │
└──────────────────────────────────────────┘
```

**Directory Structure:**
- Project directory contains only: `<project>/.aibox/.aibox-ref` (reference file)
- All configuration stored in: `~/.aibox/` (centralized, machine-specific)

**Priority:**
1. **Project config** (`~/.aibox/projects/<project-name>-<hash>/config.yml`) - Highest priority
2. **Global config** (`~/.aibox/config.yml`) - Fallback defaults

---

## Global Configuration

**Location:** `~/.aibox/config.yml`

### Full Schema

```yaml
# Configuration file version
version: "1.0"

# Docker configuration
docker:
  # Base Docker image for containers
  base_image: debian:bookworm-slim

  # Default resource limits
  default_resources:
    cpus: 2        # Number of CPU cores (1-32)
    memory: 4g     # Memory limit (e.g., "2g", "4g", "8g")
```

### Field Reference

#### `version`
- **Type:** String
- **Required:** No
- **Default:** `"1.0"`
- **Description:** Configuration file format version
- **Values:** `"1.0"`

**Example:**
```yaml
version: "1.0"
```

#### `docker.base_image`
- **Type:** String
- **Required:** No
- **Default:** `"debian:bookworm-slim"`
- **Description:** Base Docker image for containers
- **Common Values:**
  - `debian:bookworm-slim` - Debian 12 slim (default; balanced size and package availability)
  - `alpine:3.19` - Alpine Linux 3.19 (tiny, but slower package availability)
  - `ubuntu:22.04` - Ubuntu 22.04 LTS
  - `ubuntu:24.04` - Ubuntu 24.04 LTS
  - `debian:12` - Debian 12 (Bookworm)

**Example:**
```yaml
docker:
  base_image: debian:bookworm-slim
```

#### `docker.default_resources.cpus`
- **Type:** Integer
- **Required:** No
- **Default:** `2`
- **Range:** 1-32
- **Description:** Number of CPU cores allocated to containers

**Example:**
```yaml
docker:
  default_resources:
    cpus: 4  # Allocate 4 CPU cores
```

#### `docker.default_resources.memory`
- **Type:** String
- **Required:** No
- **Default:** `"4g"`
- **Format:** `{number}{unit}` where unit is `k`, `m`, or `g`
- **Description:** Memory limit for containers

**Examples:**
```yaml
docker:
  default_resources:
    memory: 2g     # 2 gigabytes
    memory: 4096m  # 4096 megabytes
    memory: 8g     # 8 gigabytes
```

---

## Project Configuration

**Location:** `~/.aibox/projects/<project-name>-<hash>/config.yml`

**Note:** The project directory contains only `.aibox/.aibox-ref` which points to the storage directory.

### Full Schema

```yaml
# Project name (required)
name: my-project

# List of profiles to enable
profiles:
  - python:3.12
  - nodejs:20
  - rust:stable

# Additional volume mounts
mounts:
  - source: ~/data
    target: /data
    mode: ro  # ro (read-only) | rw (read-write)

  - source: /shared/cache
    target: /cache
    mode: rw

# Environment variables
environment:
  DEBUG: "true"
  LOG_LEVEL: info
  CUSTOM_VAR: value
```

### Field Reference

#### `name`
- **Type:** String
- **Required:** **Yes**
- **Description:** Project name (used in container naming)
- **Constraints:**
  - Must not be empty
  - Should be filesystem-safe (no special characters)
  - Used as: `aibox-{name}-{slot}`

**Example:**
```yaml
name: my-awesome-project
```

#### `profiles`
- **Type:** List of strings
- **Required:** No
- **Default:** `[]`
- **Format:** `{profile-name}:{version}` or `{profile-name}`
- **Description:** List of language/tool profiles to enable

**Format Rules:**
- Profile names: lowercase alphanumeric, hyphens, underscores
- Versions: alphanumeric, dots, hyphens
- Examples: `python:3.12`, `nodejs:20`, `rust`, `go:1.22`

**Examples:**
```yaml
# Single profile
profiles:
  - python:3.12

# Multiple profiles
profiles:
  - python:3.12
  - nodejs:20
  - rust:stable

# Default versions (uses profile's default)
profiles:
  - python  # Uses default version
  - nodejs  # Uses default version
```

#### `mounts`
- **Type:** List of mount objects
- **Required:** No
- **Default:** `[]`
- **Description:** Additional volume mounts for the container

**Mount Object Fields:**
- `source` (string, required): Host path to mount
- `target` (string, required): Container path
- `mode` (string, optional): Mount mode - `ro` (read-only) or `rw` (read-write)

**Path Expansion:**
- `~` expands to home directory
- Relative paths are resolved from project root

**Examples:**
```yaml
# Read-only data mount
mounts:
  - source: ~/datasets
    target: /data
    mode: ro

# Read-write cache mount
mounts:
  - source: ~/.cache/project
    target: /cache
    mode: rw

# Multiple mounts
mounts:
  - source: ~/data
    target: /data
    mode: ro
  - source: /shared/models
    target: /models
    mode: ro
  - source: ./temp
    target: /tmp/workspace
    mode: rw
```

#### `environment`
- **Type:** Dictionary (string → string)
- **Required:** No
- **Default:** `{}`
- **Description:** Environment variables to set in container

**Notes:**
- Values must be strings (quote numbers: `"42"`, `"3.14"`)
- Variables are available inside container
- AI provider API keys are handled separately

**Examples:**
```yaml
# Basic environment variables
environment:
  DEBUG: "true"
  LOG_LEVEL: info
  DATABASE_URL: postgresql://localhost/db

# Development settings
environment:
  NODE_ENV: development
  RUST_BACKTRACE: "1"
  PYTHONUNBUFFERED: "1"

# Custom application config
environment:
  APP_NAME: myapp
  APP_VERSION: 1.0.0
  WORKERS: "4"
```

---

## Configuration Merging

Project configuration **overrides** global configuration:

### Example

**Global config** (`~/.aibox/config.yml`):
```yaml
version: "1.0"
docker:
  base_image: debian:bookworm-slim
  default_resources:
    cpus: 2
    memory: 4g
```

**Project config** (`~/.aibox/projects/<project-name>-<hash>/config.yml`):
```yaml
name: my-project
profiles:
  - python:3.12
```

**Merged result:**
```yaml
version: "1.0"
docker:
  base_image: debian:bookworm-slim  # ← From global
  default_resources:
    cpus: 2                 # ← From global
    memory: 4g              # ← From global
project:
  name: my-project          # ← From project
  profiles:
    - python:3.12           # ← From project
```

---

## Environment Variables

### Configuration Overrides

Environment variables do **not** override config files.
To customize, edit config files directly.

---

## Examples

### Minimal Project

```yaml
name: minimal-project
profiles:
  - python:3.12
```

Uses defaults from global config.

### Python Data Science

```yaml
name: data-science-project
profiles:
  - python:3.12
mounts:
  - source: ~/datasets
    target: /data
    mode: ro
  - source: ~/.cache/models
    target: /models
    mode: rw
environment:
  JUPYTER_ENABLE_LAB: "yes"
  PYTHONUNBUFFERED: "1"
```

### Full-Stack Development

```yaml
name: fullstack-app
profiles:
  - python:3.12
  - nodejs:20
  - postgres:15
mounts:
  - source: ./data
    target: /app/data
    mode: rw
environment:
  NODE_ENV: development
  DATABASE_URL: postgresql://localhost:5432/app
  REDIS_URL: redis://localhost:6379
  DEBUG: "true"
```

### Multi-Language Project

```yaml
name: polyglot-project
profiles:
  - python:3.12
  - nodejs:20
  - go:1.22
  - rust:stable
environment:
  CARGO_HOME: /workspace/.cargo
  GOPATH: /workspace/go
```

### Minimal Resource Usage

Global config (`~/.aibox/config.yml`):
```yaml
version: "1.0"
docker:
  base_image: debian:bookworm-slim
  default_resources:
    cpus: 1
    memory: 2g
```

Project config (`~/.aibox/projects/<project-name>-<hash>/config.yml`):
```yaml
name: lightweight-project
profiles:
  - python:3.12
```

### High-Performance Setup

Global config:
```yaml
version: "1.0"
docker:
  base_image: ubuntu:24.04
  default_resources:
    cpus: 8
    memory: 16g
```

---

## Validation

### Validate Configuration

```bash
# Validate project configuration
aibox config validate

# Show validation errors with details
aibox config validate --verbose

# View merged configuration
aibox config show
```

### Common Validation Errors

**Missing project name:**
```
❌ Error: Field 'name' is required in project configuration

Fix: Add 'name' field to .aibox/config.yml
```

**Invalid profile format:**
```
❌ Error: Profile 'Python:3.12' has invalid format

Fix: Use lowercase: 'python:3.12'
```

**Invalid memory format:**
```
❌ Error: Memory '4GB' has invalid format

Fix: Use lowercase unit: '4g' or '4096m'
```

**Invalid CPU range:**
```
❌ Error: CPUs must be between 1 and 32, got 64

Fix: Reduce CPU allocation to 32 or less
```