import os
import shutil
import asyncio
import venv
from pathlib import Path
from typing import List, Union
from ..config import Settings, settings

class TestEnvironment:
    """Setup and manage test execution environment."""
    
    def __init__(self, project_path: Union[str, Path, None] = None, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.project_path = Path(project_path) if project_path else self.settings.project_root
        self.original_env = os.environ.copy()
        self.venv_path = self.project_path / ".venv"
        self.temp_env = {}
        self.created_files = []
        self.created_dirs = []
    
    async def setup(self):
        """Setup the test environment."""
        await self._create_virtual_env()
        await self._activate_virtual_env()
        await self._install_dependencies()
        await self._create_temp_dirs()
        await self._setup_env_vars()
    
    async def cleanup(self):
        """Clean up the test environment."""
        await self._deactivate_virtual_env()
        await self._cleanup_temp_files()

    async def _create_virtual_env(self):
        """Create a virtual environment if it doesn't exist."""
        if not self.venv_path.exists():
            print(f"Creating virtual environment at {self.venv_path}")
            venv.create(self.venv_path, with_pip=True)

    async def _activate_virtual_env(self):
        """Activate the virtual environment."""
        if self.venv_path.exists():
            # This is a simplified activation. A real implementation would be more robust.
            bin_path = self.venv_path / ("Scripts" if os.name == "nt" else "bin")
            os.environ["PATH"] = str(bin_path) + os.pathsep + os.environ["PATH"]
            os.environ["VIRTUAL_ENV"] = str(self.venv_path)

    async def _deactivate_virtual_env(self):
        """Deactivate the virtual environment."""
        os.environ.clear()
        os.environ.update(self.original_env)

    async def _install_dependencies(self):
        """Install dependencies needed for testing."""
        if (self.project_path / "poetry.lock").exists() and (self.project_path / "pyproject.toml").exists():
            print("Installing dependencies from poetry.lock")
            process = await asyncio.create_subprocess_exec(
                "poetry", "install",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        elif (self.project_path / "requirements.txt").exists():
            print("Installing dependencies from requirements.txt")
            process = await asyncio.create_subprocess_exec(
                "pip", "install", "-r", "requirements.txt",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        
        if (self.project_path / "package-lock.json").exists() or (self.project_path / "yarn.lock").exists():
            print("Installing dependencies from package-lock.json or yarn.lock")
            installer = "npm" if (self.project_path / "package-lock.json").exists() else "yarn"
            process = await asyncio.create_subprocess_exec(
                installer, "install",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        elif (self.project_path / "package.json").exists():
            print("Installing dependencies from package.json")
            process = await asyncio.create_subprocess_exec(
                "npm", "install",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        
        if (self.project_path / "pom.xml").exists():
            print("Installing dependencies from pom.xml")
            process = await asyncio.create_subprocess_exec(
                "mvn", "dependency:resolve",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
    
    async def _run_in_docker(self, command: List[str]) -> asyncio.subprocess.Process:
        """Run a command inside a Docker container."""
        image_name = f"{self.project_path.name.lower()}-test-env"
        await self._build_docker_image(image_name)

        return await asyncio.create_subprocess_exec(
            "docker", "run", "--rm",
            "-v", f"{self.project_path}:/app",
            "-w", "/app",
            image_name,
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

    async def _build_docker_image(self, image_name: str):
        """Build a Docker image for the project if it doesn't exist."""
        # Check if image exists
        process = await asyncio.create_subprocess_exec(
            "docker", "images", "-q", image_name,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        if stdout.strip():
            return

        print(f"Building Docker image {image_name}")
        dockerfile = self.project_path / "Dockerfile"
        if not dockerfile.exists():
            # Create a default Dockerfile if one doesn't exist
            # This is a simplified Dockerfile. A real implementation would be more robust.
            with open(dockerfile, "w") as f:
                f.write("""
                FROM python:3.9-slim
                WORKDIR /app
                COPY . /app
                RUN pip install -r requirements.txt
                """)

        process = await asyncio.create_subprocess_exec(
            "docker", "build", "-t", image_name, ".",
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise Exception(f"Docker image build failed: {stderr.decode()}")
    
    async def _create_temp_dirs(self):
        """Create temporary directories and files required for test execution."""
        created_dirs = set()
        # Ensure test output directory exists
        test_output_dir = self.project_path / self.settings.tests_output_dir
        if not test_output_dir.exists():
            test_output_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.add(test_output_dir)
        
        # Ensure directories for report/analysis outputs exist
        file_outputs = [
            self.settings.analysis_output_file,
            self.settings.results_output_file,
            self.settings.report_output_file,
            self.settings.xml_report_output_file,
            self.settings.coverage_output_file,
        ]

        for file_path in file_outputs:
            absolute_path = self.project_path / file_path
            parent_dir = absolute_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                created_dirs.add(parent_dir)
            if not absolute_path.exists():
                absolute_path.touch()
                self.created_files.append(absolute_path)

        self.created_dirs.extend(created_dirs)

    async def _setup_env_vars(self):
        """Configure environment variables required for running tests."""
        project_pythonpath = str(self.project_path)
        pythonpath = os.environ.get("PYTHONPATH", "")
        pythonpath_entries = [p for p in pythonpath.split(os.pathsep) if p]
        if project_pythonpath not in pythonpath_entries:
            updated_pythonpath = project_pythonpath if not pythonpath_entries else f"{project_pythonpath}{os.pathsep}{pythonpath}"
        else:
            updated_pythonpath = pythonpath

        env_updates = {
            "PROJECT_ROOT": str(self.project_path),
            "PYTHONPATH": updated_pythonpath,
            "TESTS_OUTPUT_DIR": str((self.project_path / self.settings.tests_output_dir).resolve()),
        }

        for key, value in env_updates.items():
            if key not in self.temp_env:
                self.temp_env[key] = os.environ.get(key)
            os.environ[key] = value

    async def _cleanup_temp_files(self):
        """Remove temporary files and directories created during setup."""
        # Restore environment variables modified in setup (if still present)
        for key, original_value in self.temp_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value
        self.temp_env.clear()

        # Remove files created by the environment
        for file_path in self.created_files:
            try:
                if file_path.exists():
                    file_path.unlink()
            except OSError:
                pass
        self.created_files.clear()

        # Remove directories that were created during setup
        for dir_path in sorted(self.created_dirs, key=lambda p: len(p.parts), reverse=True):
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
            except OSError:
                pass
        self.created_dirs.clear()
