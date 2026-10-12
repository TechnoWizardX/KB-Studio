from src.utils.security import safe_path, get_project_root, PathTraversalError

def get_file_content(file_path: str) -> str:
    """Get the content of a file, ensuring it's within the project root."""
    try:
        safe_file_path = safe_path(get_project_root(), file_path)
        with open(safe_file_path, "r", encoding="utf-8") as f:
            return f.read()
    except PathTraversalError as e:
        print(f"Security Error: {e}")
        return ""
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return ""
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}")
        return ""

def get_file_path(file_path: str) -> str:
    """Get the absolute path of a file, ensuring it's within the project root."""
    try:
        return str(safe_path(get_project_root(), file_path))
    except PathTraversalError as e:
        print(f"Security Error: {e}")
        return ""
    except Exception as e:
        print(f"Error getting file path '{file_path}': {e}")
        return ""