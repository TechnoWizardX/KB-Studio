"""
Security utilities for path validation and safe filesystem operations.
Prevents Path Traversal attacks by ensuring all paths stay within allowed base directories.
"""
from pathlib import Path
from typing import Union


class PathTraversalError(ValueError):
    """Raised when a path traversal attempt is detected."""
    pass


def resolve_base_path(base: Union[str, Path]) -> Path:
    """Resolve base directory to absolute path."""
    return Path(base).resolve()


def safe_path(base: Union[str, Path], user_input: str) -> Path:
    """
    Validate and resolve a user-provided path relative to a base directory.
    
    Args:
        base: Base directory (project root, config dir, etc.)
        user_input: User-provided path (filename, relative path, or absolute path within base)
    
    Returns:
        Resolved absolute Path within base directory
    
    Raises:
        PathTraversalError: If the resolved path escapes the base directory
        ValueError: If input is empty or invalid
    """
    if not user_input or not user_input.strip():
        raise ValueError("Path cannot be empty")
    
    user_input = user_input.strip()
    
    base_path = resolve_base_path(base)

    input_path = Path(user_input)
    target_path = (
        input_path.resolve()
        if input_path.is_absolute()
        else (base_path / input_path).resolve()
    )
    
    # Final check: ensure target is within base
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise PathTraversalError(f"Path escapes base directory: '{user_input}'")
    
    return target_path


def is_within_base(path: Union[str, Path], base: Union[str, Path]) -> bool:
    """Check if path is within base directory (handles symlinks)."""
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except (ValueError, OSError):
        return False


def safe_join(base: Union[str, Path], *parts: str) -> Path:
    """
    Safely join multiple path components under a base directory.
    
    Args:
        base: Base directory
        *parts: Path components to join
    
    Returns:
        Resolved absolute Path within base directory
    """
    if not parts:
        return resolve_base_path(base)
    
    normalized_parts = [str(part).strip() for part in parts if str(part).strip()]
    return safe_path(base, str(Path(*normalized_parts)))


def validate_filename(name: str) -> bool:
    """
    Validate that name is a safe single filename component.

    Rejects empty names, path separators, control characters, Windows-invalid
    characters, and reserved Windows device names.
    """
    if not name or not name.strip():
        return False
    
    name = name.strip()
    
    # No path separators
    if "/" in name or "\\" in name:
        return False
    
    # A filename must be one path component, not the current/parent directory.
    if name in {".", ".."}:
        return False
    
    # No control characters
    if any(ord(c) < 32 for c in name):
        return False

    # Reject names that are invalid on Windows too, even when created on
    # another platform and later opened there.
    if any(char in name for char in '<>:"|?*') or name.endswith((".", " ")):
        return False
    
    # Windows reserved names (case-insensitive)
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    name_upper = name.upper().split(".")[0]
    if name_upper in reserved:
        return False
    
    # Reasonable length
    if len(name) > 255:
        return False
    
    return True


def get_project_root() -> Path:
    """Get the current project root from ConfigManager."""
    from src.utils.config_manager import ConfigManager
    project_dir = ConfigManager.get("project_dir")
    if not project_dir:
        raise ValueError("No project directory configured")
    return Path(project_dir).resolve()


def get_config_dir() -> Path:
    """Get the config directory."""
    from src.utils.config_manager import ConfigManager
    return Path(ConfigManager.get_str_config_path()).resolve()