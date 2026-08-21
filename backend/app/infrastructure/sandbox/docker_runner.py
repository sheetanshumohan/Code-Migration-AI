"""
Hermetic Docker Execution Sandbox
Executes test suites, linters, and security scanners within isolated, ephemeral Docker containers
with automatic fallback to isolated subprocess execution when Docker daemon is not available.
"""

import asyncio
import os
import shutil
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

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(proc.communicate(), timeout=3.0)
            self._docker_available = (proc.returncode == 0)
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
            logger.info("Executing in Hermetic Docker Sandbox", command=command, workspace=workspace_dir)
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
                "-v", f"{workspace_dir}:/workspace:rw",
                "-w", "/workspace",
                self.default_image,
                "sh", "-c", f"{command} 2>&1 | head -c 5242880"
            ])

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(), timeout=timeout_seconds
                    )
                    exit_code = process.returncode or 0
                    stdout = stdout_bytes.decode("utf-8", errors="replace")
                    stderr = stderr_bytes.decode("utf-8", errors="replace")
                except TimeoutError:
                    try:
                        process.kill()
                    except Exception:
                        pass
                    exit_code = -1
                    stdout = ""
                    stderr = f"Sandbox execution timed out after {timeout_seconds} seconds."

                duration = asyncio.get_running_loop().time() - start_time
                return SandboxExecutionResult(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_seconds=duration,
                    passed=(exit_code == 0),
                )
            except Exception as e:
                logger.warning("Docker execution failed, falling back to local runner", error=str(e))

        # Fallback: Isolated local subprocess execution with strict cwd and timeout
        logger.info("Executing in Subprocess Sandbox Fallback", command=command, workspace=workspace_dir)
        try:
            is_win = sys.platform.startswith("win")
            shell_cmd = command

            if is_win:
                process = await asyncio.create_subprocess_shell(
                    shell_cmd,
                    cwd=workspace_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    "sh", "-c", shell_cmd,
                    cwd=workspace_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout_seconds
                )
                exit_code = process.returncode or 0
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
            except TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
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
