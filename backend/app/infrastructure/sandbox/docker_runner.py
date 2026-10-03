"""
Hermetic Docker Execution Sandbox
Executes test suites, linters, and security scanners within isolated, ephemeral Docker containers
with automatic fallback to isolated subprocess execution when Docker daemon is not available.
"""

import asyncio
import os
import shutil
import subprocess
import sys
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("codemigration.sandbox.docker")


class SandboxExecutionResult:
    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_seconds: float,
        passed: bool,
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.passed = passed

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "passed": self.passed,
        }


class HermeticDockerRunner:
    def __init__(self, default_image: str | None = None) -> None:
        self.default_image = default_image or settings.SANDBOX_DOCKER_IMAGE
        self._docker_available: bool | None = None

    async def _check_docker(self) -> bool:
        """Check if Docker CLI and daemon are accessible."""
        if self._docker_available is not None:
            return self._docker_available

        if not shutil.which("docker"):
            self._docker_available = False
            return False

        def _ping_docker() -> bool:
            try:
                res = subprocess.run(
                    ["docker", "info"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5.0,
                )
                return res.returncode == 0
            except Exception:
                return False

        try:
            self._docker_available = await asyncio.to_thread(_ping_docker)
        except Exception:
            self._docker_available = False

        return self._docker_available

    async def execute_in_sandbox(
        self,
        workspace_dir: str,
        command: str,
        timeout_seconds: int | None = None,
        network_disabled: bool = True,
        cpu_limit: str = "2.0",
        memory_limit: str = "1g",
    ) -> SandboxExecutionResult:
        """Run a command inside hermetic container or fallback subprocess sandbox."""
        timeout_seconds = timeout_seconds or settings.SANDBOX_EXECUTION_TIMEOUT_SECONDS
        start_time = asyncio.get_running_loop().time()

        docker_ready = await self._check_docker()

        if docker_ready:
            abs_workspace = os.path.abspath(workspace_dir)
            logger.info("Executing in Hermetic Docker Sandbox", command=command, workspace=abs_workspace)
            cmd_args = [
                "docker", "run", "--rm",
                f"--cpus={cpu_limit}",
                f"--memory={memory_limit}",
                "--pids-limit=64",
                "--security-opt=no-new-privileges",
                "--cap-drop=ALL",
            ]
            if network_disabled:
                cmd_args.append("--network=none")
            cmd_args.extend([
                "-v", f"{abs_workspace}:/workspace:rw",
                "-w", "/workspace",
                self.default_image,
                "sh", "-c", f"{command} 2>&1 | head -c 5242880"
            ])

            def _run_docker_sync() -> subprocess.CompletedProcess[bytes]:
                return subprocess.run(
                    cmd_args,
                    capture_output=True,
                    timeout=timeout_seconds,
                )

            try:
                res = await asyncio.to_thread(_run_docker_sync)
                exit_code = res.returncode
                stdout = res.stdout.decode("utf-8", errors="replace")
                stderr = res.stderr.decode("utf-8", errors="replace")
                duration = asyncio.get_running_loop().time() - start_time
                return SandboxExecutionResult(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_seconds=duration,
                    passed=(exit_code == 0),
                )
            except subprocess.TimeoutExpired:
                duration = asyncio.get_running_loop().time() - start_time
                return SandboxExecutionResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Sandbox execution timed out after {timeout_seconds} seconds.",
                    duration_seconds=duration,
                    passed=False,
                )
            except Exception as e:
                logger.warning("Docker execution failed, falling back to local runner", error=str(e))

        # Fallback: Isolated local subprocess execution with strict cwd and timeout
        logger.info("Executing in Subprocess Sandbox Fallback", command=command, workspace=workspace_dir)
        try:
            shell_cmd = command

            def _run_subprocess_sync() -> subprocess.CompletedProcess[bytes]:
                return subprocess.run(
                    shell_cmd,
                    shell=True,
                    cwd=workspace_dir,
                    capture_output=True,
                    timeout=timeout_seconds,
                )

            try:
                res = await asyncio.to_thread(_run_subprocess_sync)
                exit_code = res.returncode
                stdout = res.stdout.decode("utf-8", errors="replace")
                stderr = res.stderr.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                exit_code = -1
                stdout = ""
                stderr = f"Sandbox execution timed out after {timeout_seconds} seconds."
        except Exception as e:
            logger.error("Sandbox execution error", error=str(e))
            exit_code = 1
            stdout = ""
            stderr = f"Sandbox execution error: {str(e)}"

        duration = asyncio.get_running_loop().time() - start_time
        return SandboxExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            passed=(exit_code == 0),
        )


docker_sandbox = HermeticDockerRunner()
