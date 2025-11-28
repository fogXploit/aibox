# Getting Started

This guide walks you through installing aibox, initializing a project, selecting profiles, starting AI
containers, and reusing sessions.

## Prerequisites

- Docker running and accessible (`docker ps` should work)
- Python 3.11+
- Credentials for ai provider

## Install

```bash
# Recommended: uv
uv pip install aibox-cli

# Or pip
pip install aibox-cli

aibox --version
```

## Initialize a Project

```bash
cd /path/to/your/repo
aibox init
```

The wizard will:
- Create project config under `~/.aibox/projects/<hash>/config.yml`
- Let you pick profiles (e.g., python:3.12, nodejs:20, rust, go, sudo, git)
- Write `.aibox/.aibox-ref` in your repo to point to the config

You can rerun `aibox init` safely to adjust profiles; or edit with `aibox config edit`.

## Start a Container

```bash
# Interactive provider + slot wizard
aibox start

# Reuse a specific slot (keeps state)
aibox start --slot 2

# One-off session (remove container on exit)
aibox start --auto-delete
```

What happens:
- Builds a base image for selected profiles (cached)
- Adds provider layer (Claude/Gemini/OpenAI Codex)
- Creates/starts a container for the chosen slot
- Attaches you to the AI CLI inside the container

Exit behavior:
- Default: container is stopped but preserved for reuse (`aibox start --slot N` picks it up again)
- `--auto-delete`: container is removed on exit

## Slots

Slots let you keep multiple provider setups side-by-side.

```bash
aibox slot list           # view slots
aibox slot add            # preconfigure a slot (choose slot + provider by number)
aibox slot cleanup        # removes all configurations of a used slot & removes stopped slot containers
```

## Profiles

Built-in profiles:
- python:3.11|3.12|3.13
- nodejs:20
- go:1.21|1.22|1.23
- rust:stable|beta|nightly|1.75|1.76|1.77
- sudo:1 (passwordless sudo)
- git:latest (git client)

List and inspect:
```bash
aibox profile list
aibox profile info python
```

## Session Continuation

- aibox reuses the same container for a slot by default. Start again with `--slot` to keep installed
  tools and workspace changes. Containers are stopped (not removed) on exit unless `--auto-delete` is set.
- Provider notes:
  - OpenAI Codex: container reuse preserves CLI config; to continue a Codex chat thread, run
    `codex reuse --last` (or `codex reuse <id>`) inside the reused container.
