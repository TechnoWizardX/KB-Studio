import logging
import shutil
from pathlib import Path

from src.core.signals import signals
from src.utils.config_manager import ConfigManager
from src.utils.security import (
    PathTraversalError,
    get_project_root,
    safe_path,
    validate_filename,
)

logger = logging.getLogger(__name__)


def get_file_content(file_path: str) -> str:
    """Get the content of a file, ensuring it's within the project root."""
    try:
        safe_file_path = safe_path(get_project_root(), file_path)
        with open(safe_file_path, "r", encoding="utf-8") as f:
            return f.read()
    except PathTraversalError as error:
        logger.warning("Security error reading %r: %s", file_path, error)
        return ""
    except FileNotFoundError:
        logger.debug("File not found: %s", file_path)
        return ""
    except (OSError, UnicodeError) as error:
        logger.error("Cannot read file %r: %s", file_path, error)
        return ""


def get_context_file_content(file_path: str) -> str:
    """Read a file explicitly selected by the user for AI context."""
    path = Path(file_path)
    if not path.is_absolute():
        raise ValueError("Context file path must be absolute")

    resolved_path = path.resolve(strict=True)
    if not resolved_path.is_file():
        raise ValueError(f"Context path is not a file: '{file_path}'")

    return resolved_path.read_text(encoding="utf-8-sig")


def get_file_path(file_path: str) -> str:
    """Get the absolute path of a file, ensuring it's within the project root."""
    try:
        return str(safe_path(get_project_root(), file_path))
    except PathTraversalError as error:
        logger.warning("Security error resolving %r: %s", file_path, error)
        return ""
    except (OSError, ValueError) as error:
        logger.error("Cannot resolve file %r: %s", file_path, error)
        return ""


class FileOperationError(Exception):
    """A file operation could not be completed safely."""


_creation_base_override: Path | None = None


def set_creation_base(base: Path | None) -> None:
    """Set the directory used by signal-triggered create operations."""
    global _creation_base_override
    _creation_base_override = base.resolve() if base is not None else None


def get_creation_base() -> Path:
    """Get the selected directory, falling back to the project root."""
    root = get_project_root()
    if _creation_base_override is not None:
        try:
            _creation_base_override.relative_to(root)
            if _creation_base_override.is_dir():
                return _creation_base_override
        except (OSError, ValueError):
            pass

    selected = ConfigManager.get("selected_dir")
    if isinstance(selected, str) and selected:
        try:
            selected_path = Path(selected).resolve()
            selected_path.relative_to(root)
            if selected_path.is_dir():
                return selected_path
        except (OSError, ValueError):
            pass
    return root


def create_file(name: str, base: Path | None = None) -> Path:
    """Create an empty file without embedding Qt or GUI behavior."""
    name = name.strip()
    if not validate_filename(name):
        raise FileOperationError(f"“{name}” is not a valid file name.")

    destination = safe_path(base or get_creation_base(), name)
    if destination.exists():
        raise FileOperationError(f"“{name}” already exists in this folder.")
    try:
        destination.open("x", encoding="utf-8").close()
    except (OSError, ValueError) as error:
        raise FileOperationError(f"Could not create file “{name}”: {error}") from error
    return destination


def create_directory(name: str, base: Path | None = None) -> Path:
    """Create a directory without embedding Qt or GUI behavior."""
    name = name.strip()
    if not validate_filename(name):
        raise FileOperationError(f"“{name}” is not a valid folder name.")

    destination = safe_path(base or get_creation_base(), name)
    if destination.exists():
        raise FileOperationError(f"“{name}” already exists in this folder.")
    try:
        destination.mkdir()
    except (OSError, ValueError) as error:
        raise FileOperationError(f"Could not create folder “{name}”: {error}") from error
    return destination


def delete_path(path: str | Path) -> None:
    """Delete a file or directory inside the project root."""
    root = get_project_root()
    destination = safe_path(root, str(path))
    try:
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    except (OSError, ValueError) as error:
        raise FileOperationError(f"Could not delete “{destination.name}”: {error}") from error


def rename_path(path: str | Path, new_name: str) -> Path:
    """Rename a file or directory inside the project root."""
    new_name = new_name.strip()
    if not validate_filename(new_name):
        raise FileOperationError(f"“{new_name}” is not a valid name.")

    root = get_project_root()
    source = safe_path(root, str(path))
    destination = safe_path(source.parent, new_name)
    if destination.exists():
        raise FileOperationError(f"“{new_name}” already exists in this folder.")
    try:
        source.rename(destination)
    except (OSError, ValueError) as error:
        raise FileOperationError(f"Could not rename “{source.name}”: {error}") from error
    return destination


_file_signals_bound = False


def bind_file_signals(bus=signals) -> None:
    """Bind reusable file signals to the file-manager implementation once."""
    global _file_signals_bound
    if _file_signals_bound:
        return

    def on_create_file(name: str) -> None:
        try:
            destination = create_file(name)
        except (FileOperationError, PathTraversalError, ValueError) as error:
            bus.error_occured.emit(str(error))
            return
        bus.status_message.emit(f"Created file “{destination.name}”")
        bus.project_files_changed.emit()

    def on_create_directory(name: str) -> None:
        try:
            destination = create_directory(name)
        except (FileOperationError, PathTraversalError, ValueError) as error:
            bus.error_occured.emit(str(error))
            return
        bus.status_message.emit(f"Created folder “{destination.name}”")
        bus.project_files_changed.emit()

    bus.execute_create_file.connect(on_create_file)
    bus.execute_create_dir.connect(on_create_directory)
    _file_signals_bound = True
