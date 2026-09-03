from PySide6.QtCore import QStandardPaths
from pathlib import Path
from src.resources.data import DEFAULT_CONFIG
class ConfigManager():

    def create_config_dir():
        app_data_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        config_dir = Path(app_data_path) / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def init_config():
