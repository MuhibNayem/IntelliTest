import asyncio
from pathlib import Path
from typing import Dict, List, Union, Tuple

class FileTools:
    """Tools for file operations and terminal commands."""
    
    def __init__(self, working_dir: Union[str,None] = None):
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
    
    def _resolve_path(self, file_path: Union[str, Path]) -> Path:
        path = Path(file_path)
        if not path.is_absolute():
            path = self.working_dir / path
        return path.resolve()
    
    async def read_file(self, file_path: Union[str, Path]) -> str:
        """Read the contents of a file asynchronously."""
        path = self._resolve_path(file_path)

        def _read() -> str:
            return path.read_text()

        return await asyncio.to_thread(_read)
    
    async def write_file(self, file_path: Union[str, Path], content: str) -> bool:
        """Write content to a file asynchronously."""
        path = self._resolve_path(file_path)

        def _write() -> bool:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                return True
            except Exception as exc:
                print(f"Error writing to {path}: {exc}")
                return False

        return await asyncio.to_thread(_write)
    
    async def list_files(self, directory: Union[str, Path, None] = None, pattern: str = "*") -> List[str]:
        """List files in a directory matching a pattern."""
        dir_path = self._resolve_path(directory) if directory else self.working_dir

        def _list() -> List[str]:
            return [str(p) for p in dir_path.glob(pattern) if p.is_file()]

        return await asyncio.to_thread(_list)
    
    async def list_directories(self, directory: Union[str, Path, None] = None) -> List[str]:
        """List subdirectories in a directory."""
        dir_path = self._resolve_path(directory) if directory else self.working_dir

        def _list() -> List[str]:
            return [str(p) for p in dir_path.iterdir() if p.is_dir()]

        return await asyncio.to_thread(_list)
    
    async def file_exists(self, file_path: Union[str, Path]) -> bool:
        """Check if a file exists."""
        path = self._resolve_path(file_path)

        def _exists() -> bool:
            return path.exists() and path.is_file()

        return await asyncio.to_thread(_exists)
    
    async def directory_exists(self, directory: Union[str, Path]) -> bool:
        """Check if a directory exists."""
        path = self._resolve_path(directory)

        def _exists() -> bool:
            return path.exists() and path.is_dir()

        return await asyncio.to_thread(_exists)
    
    async def create_directory(self, directory: Union[str, Path]) -> bool:
        """Create a directory if it doesn't exist."""
        path = self._resolve_path(directory)

        def _create() -> bool:
            try:
                path.mkdir(parents=True, exist_ok=True)
                return True
            except Exception as exc:
                print(f"Error creating directory {path}: {exc}")
                return False

        return await asyncio.to_thread(_create)
    
    async def delete_file(self, file_path: Union[str, Path]) -> bool:
        """Delete a file."""
        path = self._resolve_path(file_path)

        def _delete() -> bool:
            try:
                path.unlink()
                return True
            except Exception as exc:
                print(f"Error deleting file {path}: {exc}")
                return False

        return await asyncio.to_thread(_delete)
    
    async def delete_directory(self, directory: Union[str, Path], recursive: bool = False) -> bool:
        """Delete a directory."""
        path = self._resolve_path(directory)

        def _delete() -> bool:
            try:
                if recursive:
                    import shutil
                    shutil.rmtree(path)
                else:
                    path.rmdir()
                return True
            except Exception as exc:
                print(f"Error deleting directory {path}: {exc}")
                return False

        return await asyncio.to_thread(_delete)
    
    async def run_command(self, command: str, cwd: Union[str, Path, None] = None) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, and stderr."""
        working_dir = self._resolve_path(cwd) if cwd else self.working_dir
        
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
        dir_path = self._resolve_path(directory) if directory else self.working_dir
        command = f"find {dir_path} -name '{pattern}' -type f"
        exit_code, stdout, stderr = await self.run_command(command)
        
        if exit_code == 0:
            return stdout.strip().split('\n') if stdout.strip() else []
        else:
            print(f"Error finding files: {stderr}")
            return []
    
    async def grep_files(self, pattern: str, file_pattern: str = "*", directory: Union[str, Path, None] = None) -> List[Dict]:
        """Search for a pattern in files using grep."""
        dir_path = self._resolve_path(directory) if directory else self.working_dir
        command = f"grep -rn '{pattern}' {dir_path} --include='{file_pattern}'"
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
