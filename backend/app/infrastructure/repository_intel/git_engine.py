"""
Git Engine & Repository Synchronizer
Handles repository cloning, incremental syncs (via git fetch/pull),
and initial heuristics for language and framework detection.
"""
import json
import os
from pathlib import Path

import git

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("codemigration.git_engine")

class GitEngine:
    def __init__(self, storage_dir: str | None = None):
        self.storage_dir = Path(storage_dir or settings.WORKSPACE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, org_id: str, repo_id: str) -> str:
        """Get the local filesystem path for a cloned repository."""
        safe_org = os.path.basename(str(org_id))
        safe_repo = os.path.basename(str(repo_id))
        if not safe_org or not safe_repo or safe_org in ['.', '..'] or safe_repo in ['.', '..']:
            raise ValueError("Invalid org_id or repo_id")
        return str(self.storage_dir / safe_org / safe_repo)

    def validate_repository(self, repo_url: str, auth_token: str | None = None) -> bool:
        """Validates if a remote repository exists and is accessible using git ls-remote."""
        import subprocess

        # Inject token into URL if provided
        url_to_check = repo_url
        if auth_token:
            if "://" in repo_url:
                parts = repo_url.split("://")
                url_to_check = f"{parts[0]}://oauth2:{auth_token}@{parts[1]}" if "gitlab" in repo_url else f"{parts[0]}://{auth_token}@{parts[1]}"
            else:
                url_to_check = f"https://{auth_token}@{repo_url}"

        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", url_to_check],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("git ls-remote timed out", url=repo_url)
            return False
        except Exception as e:
            logger.error("Error validating repository", error=str(e))
            return False

    def clone_repository(self, org_id: str, repo_url: str, repo_id: str) -> str:
        """Clones a remote repository for analysis."""
        target_path = Path(self.get_repo_path(org_id, repo_id))
        if target_path.exists():
            logger.info("Repository exists, performing incremental sync", repo_id=repo_id)
            return self.sync_incremental(target_path)

        logger.info("Cloning repository", url=repo_url, target=str(target_path))
        git.Repo.clone_from(repo_url, target_path)
        return str(target_path)

    def sync_incremental(self, target_path: Path) -> str:
        """Performs incremental pull on an existing clone."""
        repo = git.Repo(target_path)
        origin = repo.remotes.origin
        origin.pull()
        logger.info("Incremental sync complete", path=str(target_path))
        return str(target_path)

    def detect_languages(self, repo_path: str) -> list[str]:
        """Heuristic language detection based on file extensions."""
        languages = set()
        for root, _, files in os.walk(repo_path):
            if '.git' in root:
                continue
            for file in files:
                if file.endswith('.py'): languages.add('python')
                elif file.endswith(('.js', '.jsx')): languages.add('javascript')
                elif file.endswith(('.ts', '.tsx')): languages.add('typescript')
                elif file.endswith('.java'): languages.add('java')
                elif file.endswith('.go'): languages.add('golang')
        return list(languages)

    def detect_frameworks(self, repo_path: str) -> list[str]:
        """Heuristic framework detection via manifest files."""
        frameworks = set()
        p = Path(repo_path)

        # Python
        req_txt = p / 'requirements.txt'
        if req_txt.exists():
            content = req_txt.read_text().lower()
            if 'fastapi' in content:
                frameworks.add('fastapi')
            if 'flask' in content:
                frameworks.add('flask')
            if 'django' in content:
                frameworks.add('django')

        # JS / TS
        pkg_json = p / 'package.json'
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                if 'react' in deps:
                    frameworks.add('react')
                if 'next' in deps:
                    frameworks.add('nextjs')
                if 'express' in deps:
                    frameworks.add('express')
            except json.JSONDecodeError:
                pass

        # Java
        pom = p / 'pom.xml'
        if pom.exists():
            content = pom.read_text().lower()
            if 'spring-boot' in content:
                frameworks.add('spring-boot')

        return list(frameworks)

    def list_repository_files(self, repo_path: str) -> list[str]:
        """List all non-ignored, processable source code files in the repository."""
        ignored_dirs = {
            '.git', '.yarn', 'node_modules', '.docusaurus', 'dist', 'build',
            'coverage', '.next', 'vendor', '.cache', 'target', 'bin', 'obj',
            '__pycache__', '.venv', 'venv', '.turbo', '.output'
        }
        ignored_exts = (
            '.lock', '.zip', '.tar', '.gz', '.min.js', '.map', '.bin', '.exe',
            '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff',
            '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.cjs'
        )
        file_list = []
        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories in-place for high traversal performance
            dirs[:] = [d for d in dirs if d.lower() not in ignored_dirs and not d.startswith('.')]

            for file in files:
                if file.lower().endswith(ignored_exts):
                    continue
                full_path = os.path.join(root, file)
                try:
                    # Skip files larger than 100 KB from AST transformation to prevent LLM context overflow
                    if os.path.getsize(full_path) > 100 * 1024:
                        continue
                except Exception:
                    pass
                rel_path = os.path.relpath(full_path, repo_path).replace('\\', '/')
                file_list.append(rel_path)
        return file_list

    def read_file_content(self, repo_path: str, rel_file_path: str) -> str:
        """Read the string content of a file in the repository."""
        target = (Path(repo_path) / rel_file_path).resolve()
        base = Path(repo_path).resolve()
        if not str(target).startswith(str(base)):
            raise ValueError(f"Path traversal security violation: {rel_file_path}")
        return target.read_text(encoding='utf-8', errors='replace')

    def write_file_content(self, repo_path: str, rel_file_path: str, content: str) -> None:
        """Write string content to a file in the repository."""
        target = (Path(repo_path) / rel_file_path).resolve()
        base = Path(repo_path).resolve()
        if not str(target).startswith(str(base)):
            raise ValueError(f"Path traversal security violation: {rel_file_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')

    def delete_repository(self, org_id: str, repo_id: str) -> None:
        """Delete the cloned repository directory from the local filesystem."""
        import shutil
        target_path = Path(self.get_repo_path(org_id, repo_id))
        if target_path.exists():
            try:
                # Resolve permissions issues on windows during rmtree
                def on_rm_error(func, path, exc_info):
                    import stat
                    os.chmod(path, stat.S_IWRITE)
                    func(path)

                shutil.rmtree(target_path, onerror=on_rm_error)
                logger.info("Deleted repository from disk", repo_id=repo_id, path=str(target_path))
            except Exception as e:
                logger.error("Failed to delete repository from disk", repo_id=repo_id, error=str(e))
                # Fallback non-blocking ignore errors
                shutil.rmtree(target_path, ignore_errors=True)

git_engine = GitEngine()
