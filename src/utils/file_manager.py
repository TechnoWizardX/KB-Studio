import logging
from pathlib import Path

from src.utils.security import PathTraversalError, get_project_root, safe_path

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
