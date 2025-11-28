"""Unit tests for Dockerfile generator."""

from aibox.profiles.generator import DockerfileGenerator
from aibox.profiles.models import ProfileDefinition


class TestDockerfileGenerator:
    """Tests for DockerfileGenerator class."""

    def test_init_default_base_image(self) -> None:
        """Test initialization with default base image."""
        generator = DockerfileGenerator()
        assert generator.base_image == "debian:bookworm-slim"

    def test_init_custom_base_image(self) -> None:
        """Test initialization with custom base image."""
        generator = DockerfileGenerator("debian:12")
        assert generator.base_image == "debian:12"

    def test_generate_empty_profiles(self) -> None:
        """Test generating Dockerfile with no profiles."""
        generator = DockerfileGenerator()
        dockerfile = generator.generate([])

        assert "FROM debian:bookworm-slim" in dockerfile
        assert 'RUN adduser --disabled-password --gecos "" --uid 1000 aibox' in dockerfile
        assert "USER aibox" in dockerfile
        assert "WORKDIR /workspace" in dockerfile

    def test_generate_single_profile(self) -> None:
        """Test generating Dockerfile with single profile."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.12"],
            default_version="3.12",
            system_dependencies=["python3-dev", "build-essential"],
            docker_layers=["RUN pip install uv"],
            env_vars={"PYTHON_VERSION": "${VERSION}"},
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "3.12")])

        assert "FROM debian:bookworm-slim" in dockerfile
        assert "ARG PYTHON_VERSION=3.12" in dockerfile
        assert "python3-dev" in dockerfile
        assert "build-essential" in dockerfile
        assert "RUN pip install uv" in dockerfile
        assert "ENV PYTHON_VERSION=3.12" in dockerfile

    def test_generate_multiple_profiles(self) -> None:
        """Test generating Dockerfile with multiple profiles."""
        python_profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.12"],
            default_version="3.12",
            system_dependencies=["python3-dev"],
            docker_layers=["RUN pip install uv"],
        )

        nodejs_profile = ProfileDefinition(
            name="nodejs",
            description="Node.js",
            versions=["20"],
            default_version="20",
            system_dependencies=["nodejs", "npm"],
            docker_layers=["RUN npm install -g yarn"],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(python_profile, "3.12"), (nodejs_profile, "20")])

        assert "ARG PYTHON_VERSION=3.12" in dockerfile
        assert "ARG NODEJS_VERSION=20" in dockerfile
        assert "python3-dev" in dockerfile
        assert "nodejs" in dockerfile
        assert "npm" in dockerfile
        assert "RUN pip install uv" in dockerfile
        assert "RUN npm install -g yarn" in dockerfile

    def test_deduplicate_system_dependencies(self) -> None:
        """Test that system dependencies are deduplicated."""
        profile1 = ProfileDefinition(
            name="profile1",
            description="Profile 1",
            versions=["1.0"],
            default_version="1.0",
            system_dependencies=["curl", "wget", "git"],
        )

        profile2 = ProfileDefinition(
            name="profile2",
            description="Profile 2",
            versions=["1.0"],
            default_version="1.0",
            system_dependencies=["curl", "jq", "git"],  # Duplicates: curl, git
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile1, "1.0"), (profile2, "1.0")])

        # Count occurrences - each should appear once in dependencies section
        lines = dockerfile.split("\n")
        packages: list[str] = []
        in_apt = False
        for line in lines:
            if "apt-get install" in line:
                in_apt = True
                continue
            if in_apt:
                if line.strip().startswith("rm -rf /var/lib/apt/lists") or not line.strip():
                    break
                token = line.strip().rstrip("\\").replace("&&", "").strip()
                # Only count plain package names (skip setup commands)
                if token and " " not in token and "/" not in token:
                    packages.append(token)

        counts = {pkg: packages.count(pkg) for pkg in set(packages)}
        assert counts.get("curl", 0) >= 1
        assert counts.get("git", 0) >= 1
        assert counts.get("wget", 0) >= 1
        assert counts.get("jq", 0) >= 1

    def test_version_substitution_in_env_vars(self) -> None:
        """Test version substitution in environment variables."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.11", "3.12"],
            default_version="3.12",
            env_vars={
                "PYTHON_VERSION": "${VERSION}",
                "PATH": "/opt/python/${PYTHON_VERSION}/bin:$PATH",
            },
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "3.11")])

        assert "ENV PYTHON_VERSION=3.11" in dockerfile
        assert "ENV PATH=/opt/python/3.11/bin:$PATH" in dockerfile

    def test_version_substitution_in_docker_layers(self) -> None:
        """Test version substitution in Docker layers."""
        profile = ProfileDefinition(
            name="go",
            description="Go",
            versions=["1.21", "1.22"],
            default_version="1.22",
            docker_layers=[
                "RUN wget https://go.dev/dl/go${GO_VERSION}.tar.gz",
                "RUN tar -C /usr/local -xzf go${VERSION}.tar.gz",
            ],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "1.21")])

        assert "RUN wget https://go.dev/dl/go1.21.tar.gz" in dockerfile
        assert "RUN tar -C /usr/local -xzf go1.21.tar.gz" in dockerfile

    def test_generate_build_args(self) -> None:
        """Test generating build args for docker build."""
        python_profile = ProfileDefinition(
            name="python", description="Python", versions=["3.12"], default_version="3.12"
        )

        nodejs_profile = ProfileDefinition(
            name="nodejs", description="Node.js", versions=["20"], default_version="20"
        )

        generator = DockerfileGenerator()
        build_args = generator.generate_build_args(
            [(python_profile, "3.12"), (nodejs_profile, "20")]
        )

        assert build_args == {"PYTHON_VERSION": "3.12", "NODEJS_VERSION": "20"}

    def test_generate_build_command(self) -> None:
        """Test generating docker build command."""
        profile = ProfileDefinition(
            name="python", description="Python", versions=["3.12"], default_version="3.12"
        )

        generator = DockerfileGenerator()
        cmd = generator.generate_build_command(
            dockerfile_path="/path/to/dockerfile",
            tag="aibox-test:latest",
            profiles_with_versions=[(profile, "3.12")],
        )

        assert cmd[0] == "docker"
        assert cmd[1] == "build"
        assert "--build-arg" in cmd
        assert "PYTHON_VERSION=3.12" in cmd
        assert "-t" in cmd
        assert "aibox-test:latest" in cmd
        assert "/path/to/dockerfile" in cmd

    def test_dockerfile_structure(self) -> None:
        """Test that generated Dockerfile has correct structure."""
        profile = ProfileDefinition(
            name="test",
            description="Test profile",
            versions=["1.0"],
            default_version="1.0",
            system_dependencies=["curl"],
            docker_layers=["RUN echo test"],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "1.0")])

        lines = dockerfile.split("\n")

        # Check order
        from_index = next(i for i, line in enumerate(lines) if line.startswith("FROM"))
        user_index = next(i for i, line in enumerate(lines) if "USER aibox" in line)
        workdir_index = next(i for i, line in enumerate(lines) if "WORKDIR" in line)

        assert from_index < user_index
        assert user_index < workdir_index

    def test_system_dependencies_sorted(self) -> None:
        """Test that system dependencies are sorted alphabetically."""
        profile = ProfileDefinition(
            name="test",
            description="Test",
            versions=["1.0"],
            default_version="1.0",
            system_dependencies=["wget", "curl", "git", "jq"],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "1.0")])

        # Extract apt-get install section (package names only)
        lines = dockerfile.split("\n")
        apt_section: list[str] = []
        in_apt = False
        for line in lines:
            if "apt-get install" in line:
                in_apt = True
                continue
            if in_apt:
                if not line.strip() or line.strip().startswith("rm -rf /var/lib/apt/lists"):
                    break
                pkg = line.strip().rstrip("\\").replace("&&", "").strip()
                if pkg and " " not in pkg and "/" not in pkg:
                    apt_section.append(pkg)

        # Should be alphabetically sorted
        assert apt_section == sorted(apt_section)

    def test_sudo_profile_adds_passwordless_sudo(self) -> None:
        """Test sudo profile installs sudo and configures passwordless access."""
        sudo_profile = ProfileDefinition(
            name="sudo",
            description="Passwordless sudo",
            versions=["1"],
            default_version="1",
            system_dependencies=["sudo"],
            docker_layers=[
                "RUN echo 'aibox ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/aibox && chmod 440 /etc/sudoers.d/aibox",
            ],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(sudo_profile, "1")])

        assert "sudo" in dockerfile  # installed via apt
        assert "NOPASSWD:ALL" in dockerfile  # sudoers entry configured

    def test_git_profile_installs_git(self) -> None:
        """Test git profile adds git system dependency."""
        git_profile = ProfileDefinition(
            name="git",
            description="Git client",
            versions=["latest"],
            default_version="latest",
            system_dependencies=["git"],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(git_profile, "latest")])

        assert "git" in dockerfile

    def test_nodejs_installation_in_all_dockerfiles(self) -> None:
        """Test that Node.js is installed in all Dockerfiles."""
        generator = DockerfileGenerator()

        # Test with no profiles
        dockerfile = generator.generate([])
        assert "Install Node.js 20 (required for AI CLIs)" in dockerfile
        assert "apt-get install -y --no-install-recommends" in dockerfile
        assert "nodejs" in dockerfile
        # Verify curl is installed for NodeSource setup
        assert "curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key" in dockerfile

        # Test with profiles
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.12"],
            default_version="3.12",
            system_dependencies=["python3-dev"],
        )
        dockerfile = generator.generate([(profile, "3.12")])
        assert "Install Node.js 20 (required for AI CLIs)" in dockerfile
        assert "apt-get install -y --no-install-recommends" in dockerfile
        assert "nodejs" in dockerfile
        # Verify curl is installed for NodeSource setup
        assert "curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key" in dockerfile

    def test_npm_environment_variables(self) -> None:
        """Test that npm environment variables are set correctly."""
        generator = DockerfileGenerator()
        dockerfile = generator.generate([])

        assert "# Configure npm global package installation directory" in dockerfile
        assert 'ENV NPM_CONFIG_PREFIX="/home/aibox/npm-global"' in dockerfile
        assert 'ENV PATH="/home/aibox/npm-global/bin:$PATH"' in dockerfile

    def test_nodejs_installed_before_profiles(self) -> None:
        """Test that Node.js is installed before profile-specific installations."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.12"],
            default_version="3.12",
            system_dependencies=["python3-dev"],
            docker_layers=["RUN pip install uv"],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "3.12")])

        lines = dockerfile.split("\n")

        # Find indices
        nodejs_index = next(i for i, line in enumerate(lines) if "Install Node.js" in line)
        profile_index = next(i for i, line in enumerate(lines) if "Install python" in line)

        # Node.js should be installed before profiles
        assert nodejs_index < profile_index

    def test_ai_cli_installation_claude(self) -> None:
        """Test that Claude CLI is installed at build time."""
        generator = DockerfileGenerator()
        dockerfile = generator.generate([], ai_provider="claude")

        assert "# Install Claude Code CLI at build time" in dockerfile
        assert "npm install -g @anthropic-ai/claude-code" in dockerfile

    def test_ai_cli_installation_gemini(self) -> None:
        """Test that Gemini CLI is installed at build time."""
        generator = DockerfileGenerator()
        dockerfile = generator.generate([], ai_provider="gemini")

        assert "# Install Gemini CLI at build time" in dockerfile
        assert "npm install -g @google/gemini-cli" in dockerfile

    def test_ai_cli_installation_openai(self) -> None:
        """Test that OpenAI CLI is installed at build time."""
        generator = DockerfileGenerator()
        dockerfile = generator.generate([], ai_provider="openai")

        assert "# Install OpenAI Codex CLI at build time" in dockerfile
        assert "npm install -g @openai/codex" in dockerfile

    def test_no_ai_cli_installation_without_provider(self) -> None:
        """Test that no AI CLI is installed when provider is None."""
        generator = DockerfileGenerator()
        dockerfile = generator.generate([], ai_provider=None)

        assert "Install Claude Code CLI" not in dockerfile
        assert "Install Gemini CLI" not in dockerfile
        assert "Install OpenAI Codex CLI" not in dockerfile
        assert "npm install -g @anthropic-ai/claude-code" not in dockerfile

    def test_ai_cli_installed_after_nodejs(self) -> None:
        """Test that AI CLI is installed after Node.js."""
        generator = DockerfileGenerator()
        dockerfile = generator.generate([], ai_provider="claude")

        lines = dockerfile.split("\n")

        # Find indices
        nodejs_index = next(i for i, line in enumerate(lines) if "Install Node.js" in line)
        claude_index = next(i for i, line in enumerate(lines) if "Install Claude Code CLI" in line)

        # AI CLI should be installed after Node.js
        assert nodejs_index < claude_index

    def test_ai_cli_installed_after_profiles(self) -> None:
        """Test that AI CLI is installed after profile installations."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.12"],
            default_version="3.12",
            docker_layers=["RUN pip install uv"],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "3.12")], ai_provider="claude")

        lines = dockerfile.split("\n")

        # Find indices
        profile_index = next(i for i, line in enumerate(lines) if "Install python" in line)
        claude_index = next(i for i, line in enumerate(lines) if "Install Claude Code CLI" in line)

        # AI CLI should be installed after profiles
        assert profile_index < claude_index

    def test_post_install_commands_executed(self) -> None:
        """Test that post_install commands are executed in the Dockerfile."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.12"],
            default_version="3.12",
            env_vars={
                "PYTHON_VERSION": "${VERSION}",
                "VIRTUAL_ENV": "/home/aibox/.venv",
            },
            post_install=[
                "uv python install ${PYTHON_VERSION}",
                "uv venv ${VIRTUAL_ENV}",
            ],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "3.12")])

        # Check that post_install commands are in the Dockerfile
        assert "RUN uv python install 3.12" in dockerfile
        assert "RUN uv venv ${VIRTUAL_ENV}" in dockerfile
        assert "# Run profile post-install commands" in dockerfile

    def test_post_install_commands_run_as_aibox_user(self) -> None:
        """Test that post_install commands run after switching to aibox user."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.12"],
            default_version="3.12",
            post_install=["uv python install ${VERSION}"],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "3.12")])

        lines = dockerfile.split("\n")

        # Find indices
        user_index = next(i for i, line in enumerate(lines) if "USER aibox" in line)
        post_install_index = next(
            i for i, line in enumerate(lines) if "RUN uv python install 3.12" in line
        )

        # Post-install should run after USER aibox
        assert user_index < post_install_index

    def test_post_install_version_substitution(self) -> None:
        """Test version substitution in post_install commands."""
        profile = ProfileDefinition(
            name="go",
            description="Go",
            versions=["1.21", "1.22"],
            default_version="1.22",
            post_install=[
                "go install golang.org/x/tools/gopls@${VERSION}",
                "export GOVERSION=${GO_VERSION}",
            ],
        )

        generator = DockerfileGenerator()
        dockerfile = generator.generate([(profile, "1.21")])

        # ${VERSION} and ${GO_VERSION} should be replaced with 1.21
        assert "RUN go install golang.org/x/tools/gopls@1.21" in dockerfile
        assert "RUN export GOVERSION=1.21" in dockerfile
