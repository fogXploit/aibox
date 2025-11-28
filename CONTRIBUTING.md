# Contributing to aibox

Thank you for your interest in contributing to aibox! This document provides guidelines and instructions for contributing.

Before diving in, review [`AGENTS.md`](AGENTS.md) for repository-specific TDD discipline, human-in-the-loop checkpoints, and coding rules tailored for multi-agent contributors. Treat it as the authoritative playbook whenever you add tests, refactor, or collaborate with automated agents.

---

## Code of Conduct

Be respectful, inclusive, and professional. We're all here to build something great together.

---

## Getting Started

### 1. Fork and Clone

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/fogXploit/aibox.git
cd aibox
```

### 2. Set Up Development Environment

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### 3. Create a Branch

```bash
git checkout -b feature/my-new-feature
# or
git checkout -b fix/my-bug-fix
```

---

## Development Workflow

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# With coverage
pytest --cov=aibox --cov-report=html
open htmlcov/index.html
```

### Code Quality

```bash
# Lint
ruff check aibox/

# Format
ruff format aibox/

# Type check
mypy aibox/

# Run all checks
pre-commit run --all-files
```

### Manual Testing

```bash
# Install in development mode
uv pip install -e .

# Test CLI
aibox --version
aibox --help

# Test with real project
cd /path/to/test-project
aibox init
aibox
```

---

## Adding Features

### Adding a New Profile

Profiles define language/tool environments.

**1. Create Profile YAML**

```yaml
# aibox/profiles/definitions/mylang.yml
name: mylang
description: MyLang development environment
category: languages

versions:
  - "1.0"
  - "2.0"
default_version: "2.0"

system_dependencies:
  - build-base
  - openssl-dev

docker_layers:
  - "RUN apk add build-base openssl-dev"
  - "RUN wget https://mylang.org/install.sh | bash"

verification:
  command: "mylang --version"
  expected_pattern: "${MYLANG_VERSION}"
```

**2. Add Tests**

```python
# tests/unit/test_profiles.py
def test_load_mylang_profile():
    loader = ProfileLoader()
    profile = loader.load_profile("mylang:2.0")

    assert profile.name == "mylang"
    assert "2.0" in profile.versions
```

**3. Update Documentation**

- Add to `README.md` profiles list
- Add usage example

**4. Submit PR**

---

### Adding a New AI Provider

AI providers implement the `AIProvider` interface.

**1. Create Provider Class**

```python
# aibox/providers/myai.py
from aibox.providers.base import AIProvider

class MyAIProvider(AIProvider):
    @property
    def name(self) -> str:
        return "myai"

    @property
    def display_name(self) -> str:
        return "MyAI CLI"

    @property
    def required_env_vars(self) -> List[str]:
        return ["MYAI_API_KEY"]

    # ... implement other methods
```

**2. Register Provider**

```python
# aibox/providers/registry.py
from aibox.providers.myai import MyAIProvider

class ProviderRegistry:
    _providers = {
        "claude": ClaudeProvider,
        "gemini": GeminiProvider,
        "myai": MyAIProvider,  # Add here
    }
```

**3. Add Tests**

```python
# tests/unit/test_providers.py
def test_myai_provider():
    provider = MyAIProvider({})
    assert provider.name == "myai"
    assert "MYAI_API_KEY" in provider.required_env_vars
```

**4. Update Documentation**

---

## Code Style

### Python Style

- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use `ruff` for linting and formatting

### Good Examples

```python
# ✅ Good: Type hints, docstring, clear naming
def compute_project_hash(project_path: Path) -> str:
    """Generate stable hash for project directory.

    Args:
        project_path: Path to project directory

    Returns:
        16-character hex hash
    """
    abs_path = project_path.resolve()
    hash_obj = hashlib.sha256(str(abs_path).encode())
    return hash_obj.hexdigest()[:16]

# ❌ Bad: No types, no docstring, unclear naming
def hash(p):
    return hashlib.sha256(str(p).encode()).hexdigest()[:16]
```

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Rust profile support
fix: resolve Docker volume mounting issue
docs: update installation instructions
test: add integration tests for slot system
refactor: simplify profile loader logic
chore: update dependencies
```

---

## Testing Guidelines

### Test Structure

```python
def test_feature_name():
    """Test description explaining what's being tested."""
    # Arrange: Set up test data
    config = SampleConfig()

    # Act: Execute the code being tested
    result = process_config(config)

    # Assert: Verify the result
    assert result.is_valid
    assert result.errors == []
```

### Test Coverage

- Aim for 75%+ overall coverage


### Mocking

```python
def test_with_mock(mocker):
    """Test using pytest-mock."""
    mock_docker = mocker.Mock(spec=DockerClient)
    mock_docker.containers.list.return_value = []

    manager = ContainerManager(client=mock_docker)
    containers = manager.list_containers()

    assert containers == []
    mock_docker.containers.list.assert_called_once()
```

---

## Pull Request Process

### Before Submitting

1. ✅ Run all tests: `pytest`
2. ✅ Check code quality: `pre-commit run --all-files`
3. ✅ Update documentation if needed
4. ✅ Add tests for new features

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
```

### Review Process

1. Automated checks run (tests, linting, type checking)
2. Maintainer reviews code
3. Feedback addressed
4. PR approved and merged

---

## Release Process

Releases are automated via GitHub Actions:

1. Update version in `pyproject.toml`
2. Create release notes
3. Commit: `git commit -m "chore: bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push origin main --tags`
6. GitHub Actions builds and publishes to PyPI

---

## Getting Help

- **Documentation**: https://github.com/fogXploit/aibox/tree/main/docs
- **Issues**: https://github.com/yourusername/aibox/issues
- **Discussions**: https://github.com/yourusername/aibox/discussions

---

## Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes

Thank you for contributing! 🎉
