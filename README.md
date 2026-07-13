# aiBox

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║             █████╗ ██╗  ██████╗  █████╗  ██╗  ██╗             ║
║            ██╔══██╗██║  ██╔══██╗██╔══██╗░╚██╗██╔╝             ║
║            ███████║██║  ██████╔╝██║░░██║░░╚███╔╝░             ║
║            ██╔══██║██║  ██╔══██╗██║░░██║░░██╔██╗░             ║
║            ██║░░██║██║  ██████╔╝╚█████╔╝ ██╔╝╚██╗             ║
║            ╚═╝░░╚═╝╚═╝  ╚═════╝░░╚════╝░ ╚═╝░░╚═╝             ║
║                                                               ║
║       Container-Based Multi-AI Development Environment        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

**Container-Based Multi-AI Development Environment**

[![Tests](https://github.com/fogXploit/aibox/workflows/Tests/badge.svg)](https://github.com/fogXploit/aibox/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Multi-AI development environment with Python-based tooling, comprehensive testing, and beautiful CLI.

**[Documentation](docs/)** | **[Configuration](docs/configuration.md)** | **[Architecture](docs/ARCHITECTURE.md)** | **[Agents Guide](AGENTS.md)**

---

## Features

- 🤖 **Multi-AI Support** - Claude, Antigravity (Gemini), and OpenAI Codex
- 🐳 **Docker-Based** - Isolated, reproducible development environments
- 🔧 **Profiles** - Python, Node.js, Go, Rust, Flutter, Java, .NET, PHP, Ruby, C/C++, plus utility profiles (sudo, git)
- 🚀 **Beautiful CLI** - Rich terminal output with progress indicators and tables
- 🔌 **Parallel Slots** - Run multiple AI containers simultaneously
- ♻️ **Shared Base Images** - Reuse profile layers across providers; only provider CLIs rebuild
- 📦 **Profile System** - Declarative YAML-based language/tool configurations
- ⚙️  **Type-Safe Config** - Pydantic validation with helpful error messages
- 🔄 **Session Continuation** - Reuse the same slot container by default; optional one-off mode with
  `--auto-delete`

---

## Quick Start

```bash
# Install aibox
pip install aibox-cli
# or with uv (recommended)
uv pip install aibox-cli

# Navigate to your project
cd my-project

# Initialize the project (select profiles and versions)
aibox init

# Start AI development environment (interactive slot/provider wizard)
aibox start
```

**New to aibox?** See the **[Getting Started Guide](docs/getting-started.md)** for detailed instructions.

---

## Installation

### Prerequisites

- **Docker** - Running and accessible ([Install Docker](https://docs.docker.com/get-docker/))
- **Python 3.11+** - For the CLI tool ([Download Python](https://www.python.org/downloads/))
- **Authentication**:
  - **Claude**: OAuth authentication (authenticates in browser on first use)
  - **Antigravity (Gemini) & OpenAI**: aibox launches a short-lived login container during slot creation to capture an OAuth session

### Install via pip

```bash
# Recommended: use uv
uv pip install aibox-cli

# Or use pip
pip install aibox-cli

# Verify installation
aibox --version
```

### Install from Source

```bash
git clone https://github.com/fogXploit/aibox.git
cd aibox
uv pip install -e ".[dev]"
```

**See [Getting Started](docs/getting-started.md) for detailed installation instructions.**

---

## Shell Autocomplete

aibox supports shell autocomplete for Bash, Zsh, Fish, and PowerShell. Once enabled, you can press TAB to autocomplete.

### Install Autocomplete

```bash
# Install completion for your shell
aibox --install-completion

# Restart your terminal
# Then try it out:
aibox profile info <TAB>        # Shows: go nodejs python rust python:3.11 ...
aibox start --slot <TAB>         # Shows configured slot numbers
```

### Supported Shells

- **Bash** - Automatically detected and configured
- **Zsh** - Automatically detected and configured
- **Fish** - Automatically detected and configured
- **PowerShell** - Automatically detected and configured

**Note:** If autocomplete doesn't work after installation, ensure you've restarted your terminal or sourced your shell configuration file (e.g., `source ~/.bashrc` or `source ~/.zshrc`).

---

## Usage

### Essential Commands

```bash
# Initialize project and select profiles
aibox init

# Start AI environment (interactive provider + slot wizard)
aibox start

# Reuse a specific slot (preserves container state)
aibox start --slot 2

# One-off session (stop and remove container on exit)
aibox start --auto-delete

# Slots
aibox slot list
aibox slot add          # pick slot + provider by number
aibox slot cleanup      # remove stopped slot containers and slot configs

# Profiles
aibox profile list
aibox profile info python

# Config
aibox config show
aibox config validate
aibox config edit

# Status
aibox status
```

**See [Getting Started](docs/getting-started.md) for workflow examples.**


## Session Continuation & Reuse

- aibox reuses the same container for a slot by default. Start again with the same `--slot` to keep
  your tools and filesystem state.
- When you exit the AI CLI, the container is **stopped but preserved**. Use `--auto-delete` for a
  one-off session (container is removed when the CLI exits).
- Provider notes:
  - Claude and Antigravity (Gemini) persist auth/state via their mounted config directories
  - OpenAI Codex: container reuse preserves CLI config. To continue a Codex conversation, start
    with `aibox start --slot <n> --resume` to launch `codex resume` (slot must already have a
    Codex session); omit `--resume` to start a fresh Codex session in that slot.

---

### Profiles

Built-in profiles:
- `python:3.11|3.12|3.13` - Python with uv package manager
- `nodejs:20|22|24` - Node.js with npm global configured (default: 24)
- `go:1.24.13|1.25.12|1.26.5` - Go with modules (default: 1.25.12)
- `rust:stable|beta|nightly|1.95.0|1.96.1|1.97.0` - Rust with cargo/rustfmt/clippy (default: stable)
- `flutter:3.44.3|3.44.6` - Flutter with Dart (default: 3.44.6, Linux x64 only)
- `java:17|21|25` - Eclipse Temurin JDK (default: 21)
- `dotnet:8.0|9.0|10.0` - .NET SDK (default: 10.0)
- `php:8.2|8.3|8.4|8.5` - PHP with Composer (default: 8.4)
- `ruby:3.3.11|3.4.10|4.0.5` - Ruby built from source (default: 3.4.10)
- `cpp:system` - GCC toolchain with gdb/cmake (Debian bookworm)
- `sudo:1` - Passwordless sudo for the aibox user
- `git:latest` - Git client

Profile definitions live in `aibox/profiles/definitions/*.yml`; customize or add your own as needed.
---

## Documentation

- **[Getting Started](docs/getting-started.md)** - Installation and first project guide
- **[Configuration Reference](docs/configuration.md)** - Complete YAML configuration docs
- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture details
- **[CONTRIBUTING](CONTRIBUTING.md)** - Development and contribution guide

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/fogXploit/aibox.git
cd aibox

# Install with dev dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# With coverage
pytest --cov=aibox --cov-report=html
```

### Code Quality

```bash
# Lint and format
ruff check aibox/
ruff format aibox/

# Type checking
mypy aibox/

# Run all checks
pre-commit run --all-files
```

---

## Architecture

```
aibox/
├── cli/              # CLI commands (Typer)
├── providers/        # AI provider implementations
├── containers/       # Docker management (Docker SDK)
├── profiles/         # Profile system (YAML-based)
├── config/           # Configuration (Pydantic models)
└── utils/            # Utilities (logging, errors)
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

---

## Roadmap

### v0.1
- ✅ Claude CLI support
- ✅ Gemini CLI support
- ✅ OpenAI CLI support
- ✅ 4+ language profiles
- ✅ Slot system (parallel containers)
- ✅ YAML configuration
- ✅ Beautiful CLI with Rich

### v0.2
- ✅ Additional profiles
- ✅ AI provider integrations enhanced 
- ✅ user friendly login workflow for Gemini
- ✅ status overview added

### v0.3
- ✅ persistence & one-time container support
- ✅ cleanup workflows
- ✅ login helper for codex
- ✅ codex-cli resume support

### v0.4 (Current)
- ✅ Antigravity CLI (`agy`) replaces the retired Gemini CLI (still uses the `.gemini` config directory)
- ✅ Node.js base install defaults to 24 (Active LTS); nodejs profile offers 20/22/24

### v0.5+
- TODO

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Adding a New Profile

1. Create `aibox/profiles/definitions/myprofile.yml`
2. Add tests in `tests/unit/test_profiles.py`
3. Update documentation
4. Submit PR

---

## Troubleshooting

### Docker Not Found
```bash
# Install Docker Desktop
# https://docs.docker.com/get-docker/
```

### Antigravity (Gemini) Login Helper
```bash
# Antigravity CLI (`agy`) uses Google sign-in. When you add a Gemini slot, aibox starts
# a short-lived host-network container (so the random callback port works) and attaches
# your terminal to `agy` interactively; the first run triggers Google sign-in.
# Complete the sign-in in your browser (in headless environments, open the printed URL
# and enter the one-time code), then exit agy (type /quit or press Ctrl+C) to continue
# slot setup. The session is stored under the slot's .gemini/ directory (the Antigravity
# CLI reuses the .gemini config directory).
```

### OpenAI Login Helper
```bash
# OpenAI Codex also uses OAuth. aibox now runs a short-lived host-network container
# to execute `codex login` when a slot needs authentication, so the main container
# doesn't keep a lingering 1455 port binding. The session is stored under the slot's
# .codex/ directory.
```

### Authentication Issues (Claude/OpenAI)
```bash
# Claude and OpenAI use OAuth - no API keys needed
# If authentication fails:
# 1. Ensure Docker ports are accessible (54545 for Claude, 1455 for Codex)
# 2. Check your browser isn't blocking popups
# 3. Try running the CLI inside the container again - it will re-prompt
```

### Permission Denied
```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER
# Log out and back in
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/), [Rich](https://github.com/Textualize/rich), and [Docker SDK](https://docker-py.readthedocs.io/)
- Thanks to all [contributors](https://github.com/fogXploit/aibox/graphs/contributors)

---

## Links

- **Documentation**: https://github.com/fogXploit/aibox/tree/main/docs
- **PyPI**: https://pypi.org/project/aibox-cli/
- **GitHub**: https://github.com/fogXploit/aibox
- **Issues**: https://github.com/fogXploit/aibox/issues
- **Discussions**: https://github.com/fogXploit/aibox/discussions

---

**Built with ❤️ for AI-powered development**
