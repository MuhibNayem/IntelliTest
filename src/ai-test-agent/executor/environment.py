import os
import asyncio
from pathlib import Path
from typing import Union
from ..config import Settings, settings

class TestEnvironment:
    """Setup and manage test execution environment."""
    
    def __init__(self, project_path: Union[str, Path] = None, settings_obj: Settings = settings):
        self.settings = settings_obj
        self.project_path = Path(project_path) if project_path else self.settings.project_root
        self.original_env = os.environ.copy()
        self.temp_env = {}
        self.created_files = []
        self.created_dirs = []
    
    async def setup(self):
        """Setup the test environment."""
        # Create temporary directories if needed
        await self._create_temp_dirs()
        
        # Setup environment variables
        await self._setup_env_vars()
        
        # Install dependencies if needed
        await self._install_dependencies()
    
    async def cleanup(self):
        """Clean up the test environment."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Remove temporary files and directories
        await self._cleanup_temp_files()
    
    async def _create_temp_dirs(self):
        """Create temporary directories needed for testing."""
        temp_dirs = [
            "temp",
            "logs",
            "reports"
        ]
        
        for dir_name in temp_dirs:
            dir_path = self.project_path / dir_name
            if not dir_path.exists():
                dir_path.mkdir(exist_ok=True)
                self.created_dirs.append(dir_path)
    
    async def _setup_env_vars(self):
        """Setup environment variables for testing."""
        # Set test environment variables
        test_env_vars = {
            "TEST_ENV": "true",
            "LOG_LEVEL": "DEBUG"
        }
        
        for key, value in test_env_vars.items():
            os.environ[key] = value
            self.temp_env[key] = value
    
    async def _install_dependencies(self):
        """Install dependencies needed for testing."""
        # Check if we need to install dependencies
        if (self.project_path / "requirements.txt").exists():
            # Install Python dependencies
            process = await asyncio.create_subprocess_exec(
                "pip", "install", "-r", "requirements.txt",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        
        if (self.project_path / "package.json").exists():
            # Install Node.js dependencies
            process = await asyncio.create_subprocess_exec(
                "npm", "install",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        
        if (self.project_path / "pom.xml").exists():
            # Install Maven dependencies
            process = await asyncio.create_subprocess_exec(
                "mvn", "dependency:resolve",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
    
    async def _cleanup_temp_files(self):
        """Clean up temporary files and directories."""
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