"""
Dockerfile generator from profile definitions.

Combines multiple profiles into a single Dockerfile with:
- Optimized layer caching
- Deduplicated dependencies
- Version-specific build args
"""

from aibox.profiles.models import ProfileDefinition


class DockerfileGenerator:
    """Generates Dockerfiles from profile definitions."""

    def __init__(self, base_image: str = "debian:bookworm-slim") -> None:
        """
        Initialize Dockerfile generator.

        Args:
            base_image: Base Docker image to use
        """
        self.base_image = base_image

    def generate(
        self,
        profiles_with_versions: list[tuple[ProfileDefinition, str]],
        ai_provider: str | None = None,
    ) -> str:
        """
        Generate complete Dockerfile from profiles.

        Args:
            profiles_with_versions: List of (ProfileDefinition, version) tuples
            ai_provider: Optional AI provider name for additional setup

        Returns:
            Complete Dockerfile as string
        """
        lines: list[str] = [
            f"FROM {self.base_image}",
            "",
            "# Base setup",
        ]

        # Build args for versions
        lines.append("")
        for profile, version in profiles_with_versions:
            version_arg = f"{profile.name.upper()}_VERSION"
            lines.append(f"ARG {version_arg}={version}")

        # Create aibox user
        lines.extend(
            [
                "",
                "# Create aibox user with UID 1000 for volume mount compatibility",
                'RUN adduser --disabled-password --gecos "" --uid 1000 aibox',
                "",
            ]
        )

        # Install Node.js 20 and system packages
        lines.extend(
            [
                "# Install Node.js 20 (required for AI CLIs) and system packages",
                "RUN apt-get update && \\",
                "    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \\",
                "    mkdir -p /etc/apt/keyrings && \\",
                "    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | \\",
                "    gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \\",
                '    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \\',
                "    apt-get update && \\",
                "    apt-get install -y --no-install-recommends \\",
            ]
        )

        # Collect and deduplicate system dependencies
        all_deps = self._collect_system_dependencies(profiles_with_versions)
        # Add bash as base dependency
        all_deps.add("bash")

        # TODO: in case additional dependencies should be added to the image do it here.

        sorted_deps = sorted(all_deps)
        install_packages = sorted(["nodejs"] + sorted_deps)

        for i, dep in enumerate(install_packages):
            if i < len(install_packages) - 1:
                lines.append(f"    {dep} \\")
            else:
                lines.append(f"    {dep} && \\")

        lines.extend(
            [
                "    rm -rf /var/lib/apt/lists/*",
                "",
            ]
        )

        # Configure npm global package installation directory
        # Note: Must NOT be under /home/aibox/.aibox since that gets mounted at runtime
        lines.extend(
            [
                "# Configure npm global package installation directory",
                'ENV NPM_CONFIG_PREFIX="/home/aibox/npm-global"',
                'ENV PATH="/home/aibox/npm-global/bin:$PATH"',
                "",
            ]
        )

        # Install profiles
        for profile, version in profiles_with_versions:
            lines.extend(self._generate_profile_section(profile, version))

        # Install AI CLI if provider specified
        if ai_provider:
            lines.extend(self._generate_ai_cli_section(ai_provider))

        # Set up working directory and user
        lines.extend(
            [
                "# Set up working environment",
                "RUN chown -R aibox:aibox /home/aibox",
                "USER aibox",
                "",
            ]
        )

        # Run post-install commands as aibox user
        post_install_commands = self._collect_post_install_commands(profiles_with_versions)
        if post_install_commands:
            lines.extend(
                [
                    "# Run profile post-install commands",
                ]
            )
            for cmd in post_install_commands:
                lines.append(f"RUN {cmd}")
            lines.append("")

        # Set working directory
        lines.extend(
            [
                "WORKDIR /workspace",
                "",
            ]
        )

        # Default command
        lines.extend(
            [
                "# Default command",
                'CMD ["/bin/bash"]',
            ]
        )

        return "\n".join(lines)

    def generate_build_args(
        self, profiles_with_versions: list[tuple[ProfileDefinition, str]]
    ) -> dict[str, str]:
        """
        Generate build args for docker build command.

        Args:
            profiles_with_versions: List of (ProfileDefinition, version) tuples

        Returns:
            Dictionary of build arg names to values
        """
        build_args = {}
        for profile, version in profiles_with_versions:
            arg_name = f"{profile.name.upper()}_VERSION"
            build_args[arg_name] = version

        return build_args

    def _collect_system_dependencies(
        self, profiles_with_versions: list[tuple[ProfileDefinition, str]]
    ) -> set[str]:
        """
        Collect and deduplicate system dependencies from all profiles.

        Args:
            profiles_with_versions: List of (ProfileDefinition, version) tuples

        Returns:
            Set of unique dependency package names
        """
        deps: set[str] = set()

        for profile, _ in profiles_with_versions:
            deps.update(profile.system_dependencies)

        return deps

    def _collect_post_install_commands(
        self, profiles_with_versions: list[tuple[ProfileDefinition, str]]
    ) -> list[str]:
        """
        Collect post-install commands from all profiles with version substitution.

        Args:
            profiles_with_versions: List of (ProfileDefinition, version) tuples

        Returns:
            List of post-install commands with versions substituted
        """
        commands: list[str] = []

        for profile, version in profiles_with_versions:
            commands.extend(profile.get_post_install_with_version(version))

        return commands

    def _get_provider_packages(self, ai_provider: str) -> list[str]:
        """
        Provider-specific apt packages.
        """
        if ai_provider == "openai":
            return ["socat"]
        return []

    def _generate_profile_section(self, profile: ProfileDefinition, version: str) -> list[str]:
        """
        Generate Dockerfile section for a single profile.

        Args:
            profile: Profile definition
            version: Version to install

        Returns:
            List of Dockerfile lines
        """
        lines: list[str] = []

        # Section header
        lines.extend(
            [
                f"# Install {profile.name} {version}",
            ]
        )

        # Environment variables
        env_vars = profile.get_env_vars_with_version(version)
        if env_vars:
            for key, value in env_vars.items():
                lines.append(f"ENV {key}={value}")

        # Docker layers (RUN commands)
        docker_layers = profile.get_docker_layers_with_version(version)
        for layer in docker_layers:
            lines.append(layer)

        lines.append("")

        return lines

    def generate_build_command(
        self,
        dockerfile_path: str,
        tag: str,
        profiles_with_versions: list[tuple[ProfileDefinition, str]],
    ) -> list[str]:
        """
        Generate docker build command with all build args.

        Args:
            dockerfile_path: Path to Dockerfile or directory
            tag: Image tag
            profiles_with_versions: List of (ProfileDefinition, version) tuples

        Returns:
            Command as list of strings (for subprocess.run)
        """
        cmd = ["docker", "build"]

        # Add build args
        build_args = self.generate_build_args(profiles_with_versions)
        for name, value in build_args.items():
            cmd.extend(["--build-arg", f"{name}={value}"])

        # Add tag and path
        cmd.extend(["-t", tag, dockerfile_path])

        return cmd

    def generate_provider_layer(self, base_tag: str, ai_provider: str) -> str:
        """
        Generate a Dockerfile that layers provider-specific setup on a base image.

        Args:
            base_tag: Tag of the prebuilt base image (profiles only)
            ai_provider: Provider name to install

        Returns:
            Dockerfile content for provider layer
        """
        lines: list[str] = [f"FROM {base_tag}", "", "USER root", ""]

        provider_packages = self._get_provider_packages(ai_provider)
        if provider_packages:
            lines.extend(
                [
                    "# Provider-specific system packages",
                    "RUN apt-get update && \\",
                    "    apt-get install -y --no-install-recommends \\",
                ]
            )
            for idx, pkg in enumerate(provider_packages):
                if idx < len(provider_packages) - 1:
                    lines.append(f"    {pkg} \\")
                else:
                    lines.append(f"    {pkg} && \\")
            lines.extend(
                [
                    "    rm -rf /var/lib/apt/lists/*",
                    "",
                ]
            )

        lines.extend(self._generate_ai_cli_section(ai_provider))

        # Ensure we return to aibox user to match base image defaults
        lines.extend(
            [
                "USER aibox",
                "",
            ]
        )

        return "\n".join(lines)

    def _generate_ai_cli_section(self, ai_provider: str) -> list[str]:
        """
        Generate Dockerfile section for AI CLI installation.

        Installs the AI CLI at build time to ensure it's available in the PATH
        and avoid runtime installation issues.

        Args:
            ai_provider: AI provider name (e.g., "claude", "gemini", "openai")

        Returns:
            List of Dockerfile lines for AI CLI installation
        """
        lines: list[str] = []

        # Create npm-global directory with proper ownership before installing
        lines.extend(
            [
                "# Prepare npm-global directory for AI CLI installation",
                "RUN mkdir -p /home/aibox/npm-global && \\",
                "    chown -R aibox:aibox /home/aibox/npm-global",
                "",
            ]
        )

        if ai_provider == "claude":
            lines.extend(
                [
                    "# Install Claude Code CLI at build time (as aibox user)",
                    "USER aibox",
                    "RUN npm install -g @anthropic-ai/claude-code",
                    "USER root",
                    "",
                ]
            )
        elif ai_provider == "gemini":
            lines.extend(
                [
                    "# Install Gemini CLI at build time (as aibox user)",
                    "USER aibox",
                    "RUN npm install -g @google/gemini-cli",
                    "USER root",
                    "",
                ]
            )
        elif ai_provider == "openai":
            lines.extend(
                [
                    "# Install OpenAI Codex CLI at build time (as aibox user)",
                    "USER aibox",
                    "RUN npm install -g @openai/codex",
                    "USER root",
                    "",
                    "# Create OAuth port forwarder script for Codex CLI",
                    "# Codex binds OAuth server to 127.0.0.1:1455 inside container",
                    "# This script forwards container_ip:1455 -> 127.0.0.1:1455",
                    "# Allows host browser to reach OAuth callback via Docker port mapping",
                    r"RUN printf '#!/bin/bash\nset -e\n\n# Ensure npm global bin is on PATH for codex/claude/gemini\nexport PATH=\"/home/aibox/npm-global/bin:$PATH\"\n\n# Get container IP (not 127.0.0.1)\nCONTAINER_IP=$(hostname -i | awk '\''{print $1}'\'')\n\n# Start socat in background to forward from container IP to localhost\n# socat will listen for connections and forward them to 127.0.0.1:1455\n# where codex will bind its OAuth server\nsocat TCP-LISTEN:1455,fork,reuseaddr,bind=\"$CONTAINER_IP\" TCP:127.0.0.1:1455 &\nSOCAT_PID=$!\n\n# Function to cleanup on exit\ncleanup() {\n    kill $SOCAT_PID 2>/dev/null || true\n}\ntrap cleanup EXIT INT TERM\n\n# Run codex in foreground so it has access to stdin/stdout/stderr\n# This is critical for interactive use - backgrounding breaks terminal I/O\ncodex \"$@\"\n' > /usr/local/bin/codex-wrapper && chmod +x /usr/local/bin/codex-wrapper",
                    "",
                ]
            )

        return lines
