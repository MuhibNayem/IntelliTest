import os
import asyncio
import venv
from pathlib import Path
from typing import List, Union
from ..config import Settings, settings

class TestEnvironment:
    """Setup and manage test execution environment."""
    
    def __init__(self, project_path: Union[str, Path] = None, settings_obj: Settings = settings):
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
        # Remove temporary files
        for file_path in self.created_files:
            try:
                if file_path.exists():
                    file_path.unlink()
            except:
                pass
        
        # Remove temporary directories
        for dir_path in self.created_dirs:
            try:
                if dir_path.exists():
                    # Remove directory contents
                    for file_path in dir_path.glob("*"):
                        if file_path.is_file():
                            file_path.unlink()
                        elif file_path.is_dir():
                            # Recursively remove subdirectories
                            import shutil
                            shutil.rmtree(file_path)
                    
                    # Remove the directory itself
                    dir_path.rmdir()
            except:
                pass