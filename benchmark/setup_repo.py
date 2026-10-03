import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import select
from app.infrastructure.database.postgres.session import get_task_scoped_session
from app.infrastructure.database.postgres.models import User, Organization, Project, Repository
from app.infrastructure.repository_intel.git_engine import git_engine

async def main():
    fixture_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixture_repo"))
    print(f"Fixture repo path: {fixture_path}")

    async with get_task_scoped_session() as session:
        # Check user
        res = await session.execute(select(User).where(User.email == "benchmark_runner@testcorp.io"))
        user = res.scalar_one_or_none()
        if not user:
            print("Creating benchmark user...")
            org = Organization(name="Benchmark Corp", slug="benchmark-corp")
            session.add(org)
            await session.flush()
            user = User(
                email="benchmark_runner@testcorp.io",
                hashed_password="hashed_pw_test_12345",
                full_name="Benchmark Runner",
                organization_id=org.id,
                role="admin",
                is_active=True,
            )
            session.add(user)
            await session.flush()
        else:
            print(f"Found user: {user.email}, org: {user.organization_id}")

        # Check project
        res_p = await session.execute(select(Project).where(Project.organization_id == user.organization_id))
        proj = res_p.scalars().first()
        if not proj:
            print("Creating benchmark project...")
            proj = Project(
                organization_id=user.organization_id,
                name="Benchmark Migration Project",
                description="Automated benchmark target project",
            )
            session.add(proj)
            await session.flush()
        else:
            print(f"Found project: {proj.name} ({proj.id})")

        # Check repository
        res_r = await session.execute(select(Repository).where(Repository.project_id == proj.id))
        repo = res_r.scalars().first()
        if not repo:
            print("Creating benchmark repository record...")
            repo = Repository(
                project_id=proj.id,
                name="fixture-order-service",
                default_branch="main",
                sync_status="ready",
                git_url=fixture_path,
            )
            session.add(repo)
            await session.flush()
        else:
            print(f"Found repository: {repo.name} ({repo.id})")
            repo.git_url = fixture_path
            repo.sync_status = "ready"

        user_org_id = str(user.organization_id)
        repo_id = str(repo.id)
        await session.commit()
        
        # Ensure git_engine repo path points to fixture_path
        managed_path = git_engine.get_repo_path(user_org_id, repo_id)
        print(f"Managed repo path: {managed_path}")
        if not os.path.exists(managed_path):
            os.makedirs(os.path.dirname(managed_path), exist_ok=True)
            import shutil
            shutil.copytree(fixture_path, managed_path, dirs_exist_ok=True)
            print(f"Copied fixture repo to managed repo path: {managed_path}")
        else:
            print(f"Managed repo path already exists: {managed_path}")

        print(f"SETUP_SUCCESS repository_id={repo_id} org_id={user_org_id}")

if __name__ == "__main__":
    asyncio.run(main())
