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
- Let you pick profiles (e.g., python:3.12, nodejs:24, rust, go, sudo, git)
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
- Adds provider layer (Claude / Antigravity (Gemini) / OpenAI Codex)
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
- nodejs:20|22|24 (default: 24)
- go:1.24.13|1.25.12|1.26.5 (default: 1.25.12)
- rust:stable|beta|nightly|1.95.0|1.96.1|1.97.0 (default: stable)
- flutter:3.44.3|3.44.6 (default: 3.44.6, Linux x64 only)
- java:17|21|25 (Eclipse Temurin JDK, default: 21)
- dotnet:8.0|9.0|10.0 (.NET SDK, default: 10.0)
- php:8.2|8.3|8.4|8.5 (with Composer, default: 8.4)
- ruby:3.3.11|3.4.10|4.0.5 (built from source, default: 3.4.10)
- cpp:system (GCC toolchain, Debian bookworm)
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
