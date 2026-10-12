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
        user_input: User-provided path (filename, relative path, etc.)
    
    Returns:
        Resolved absolute Path within base directory
    
    Raises:
        PathTraversalError: If the resolved path escapes the base directory
        ValueError: If input is empty or invalid
    """
    if not user_input or not user_input.strip():
        raise ValueError("Path cannot be empty")
    
    user_input = user_input.strip()
    
    # Reject obvious traversal attempts early
    if ".." in user_input.split("/") or ".." in user_input.split("\\"):
        raise PathTraversalError(f"Path traversal detected: '{user_input}'")
    
    # Reject absolute paths
    if Path(user_input).is_absolute():
        raise PathTraversalError(f"Absolute paths not allowed: '{user_input}'")
    
    base_path = resolve_base_path(base)
    target_path = (base_path / user_input).resolve()
    
    # Final check: ensure target is within base
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise PathTraversalError(f"Path escapes base directory: '{user_input}'")
    
    return target_path


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
    
    # Join all parts first, then validate
    joined = "/".join(str(p).strip() for p in parts if p and str(p).strip())
    return safe_path(base, joined)


def validate_filename(name: str) -> bool:
    """
    Validate a filename for safety.
    
    Allows: alphanumeric, dash, underscore, dot
    Rejects: empty, path separators, traversal, reserved names (Windows)
    """
    if not name or not name.strip():
        return False
    
    name = name.strip()
    
    # No path separators
    if "/" in name or "\\" in name:
        return False
    
    # No traversal
    if ".." in name:
        return False
    
    # No control characters
    if any(ord(c) < 32 for c in name):
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