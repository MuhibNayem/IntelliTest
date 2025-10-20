import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, List, Union, Tuple

class FileTools:
    """Tools for file operations and terminal commands."""
    
    def __init__(self, working_dir: Union[str,None] = None):
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
    
    async def read_file(self, file_path: Union[str, Path]) -> str:
        """Read the contents of a file."""
        file_path = self.working_dir / file_path
        async with aiofiles.open(file_path, 'r') as f:
            return await f.read()
    
    async def write_file(self, file_path: Union[str, Path], content: str) -> bool:
        """Write content to a file."""
        file_path = self.working_dir / file_path
        try:
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(content)
            return True
        except Exception as e:
            print(f"Error writing to {file_path}: {e}")
            return False
    
    async def list_files(self, directory: Union[str, Path, None] = None, pattern: str = "*") -> List[str]:
        """List files in a directory matching a pattern."""
        directory = self.working_dir / directory if directory else self.working_dir
        return [str(p) for p in directory.glob(pattern) if p.is_file()]
    
    async def list_directories(self, directory: Union[str, Path, None] = None) -> List[str]:
        """List subdirectories in a directory."""
        directory = self.working_dir / directory if directory else self.working_dir
        return [str(p) for p in directory.iterdir() if p.is_dir()]
    
    async def file_exists(self, file_path: Union[str, Path]) -> bool:
        """Check if a file exists."""
        file_path = self.working_dir / file_path
        return file_path.exists() and file_path.is_file()
    
    async def directory_exists(self, directory: Union[str, Path]) -> bool:
        """Check if a directory exists."""
        directory = self.working_dir / directory
        return directory.exists() and directory.is_dir()
    
    async def create_directory(self, directory: Union[str, Path]) -> bool:
        """Create a directory if it doesn't exist."""
        directory = self.working_dir / directory
        try:
            directory.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating directory {directory}: {e}")
            return False
    
    async def delete_file(self, file_path: Union[str, Path]) -> bool:
        """Delete a file."""
        file_path = self.working_dir / file_path
        try:
            file_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    async def delete_directory(self, directory: Union[str, Path], recursive: bool = False) -> bool:
        """Delete a directory."""
        directory = self.working_dir / directory
        try:
            if recursive:
                import shutil
                shutil.rmtree(directory)
            else:
                directory.rmdir()
            return True
        except Exception as e:
            print(f"Error deleting directory {directory}: {e}")
            return False
    
    async def run_command(self, command: str, cwd: Union[str, Path, None] = None) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, and stderr."""
        working_dir = self.working_dir / cwd if cwd else self.working_dir
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            stdout, stderr = await process.communicate()
            
            return (
                process.returncode if process.returncode is not None else -1,
                stdout.decode('utf-8', errors='replace'),
                stderr.decode('utf-8', errors='replace')
            )
        except Exception as e:
            return -1, "", str(e)
    
    async def find_files(self, pattern: str, directory: Union[str, Path, None] = None) -> List[str]:
        """Find files matching a pattern using the find command."""
        directory = self.working_dir / directory if directory else self.working_dir
        command = f"find {directory} -name '{pattern}' -type f"
        exit_code, stdout, stderr = await self.run_command(command)
        
        if exit_code == 0:
            return stdout.strip().split('\n') if stdout.strip() else []
        else:
            print(f"Error finding files: {stderr}")
            return []
    
    async def grep_files(self, pattern: str, file_pattern: str = "*", directory: Union[str, Path, None] = None) -> List[Dict]:
        """Search for a pattern in files using grep."""
        directory = self.working_dir / directory if directory else self.working_dir
        command = f"grep -rn '{pattern}' {directory} --include='{file_pattern}'"
        exit_code, stdout, stderr = await self.run_command(command)
        
        if exit_code == 0:
            results = []
            for line in stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        file_path = parts[0]
                        line_number = parts[1]
                        match_text = parts[2]
                        results.append({
                            "file": file_path,
                            "line": line_number,
                            "match": match_text
                        })
            return results
        else:
            print(f"Error grepping files: {stderr}")
            return []