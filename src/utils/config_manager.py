from PySide6.QtCore import QStandardPaths
from pathlib import Path
from src.resources.data import DEFAULT_CONFIG
from typing import Any
import json


class ConfigManager():

    DEFAULT_CONFIG: dict[str, Any] = DEFAULT_CONFIG

    _current_config: dict[str, Any] = {}

    @classmethod
    def get_config_path(cls):
        config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        return config_dir / "config.json"

    @classmethod
    def init_config(cls) -> None:
        """Initializes config file: if it exists - loads in class attribute, else - makes config dir and loads default config"""
        config_file = cls.get_config_path()

        if not config_file.exists():
            try:
                config_file.parent.mkdir(parents=True, exist_ok=True)
                cls._current_config = cls.DEFAULT_CONFIG.copy()
                cls.save()
            except Exception as e:
                print(f"ERROR: {e}")
                cls._current_config = cls.DEFAULT_CONFIG.copy()
                return
        else:
            cls.load()

    @classmethod
    def load(cls):
        """Loads config from a file"""
        config_file = cls.get_config_path()
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cls._current_config = json.load(f)

                for key, val in cls.DEFAULT_CONFIG.items():
                    if key not in cls._current_config:
                        cls._current_config[key] = val
        except Exception as e:
            print(f"Ошибка чтения конфига, сброс на дефолт: {e}")
            cls._current_config = cls.DEFAULT_CONFIG.copy()

    @classmethod
    def save(cls):
        """Saves current config in config file"""
        config_file = cls.get_config_path()
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(cls._current_config, f, indent=4, ensure_ascii=False)
        except:
            print("ERROR: can't save current config")

    @classmethod
    def get(cls, key):
        """Returns current config value by a key, if not available - returns default value"""
        try:
            return cls._current_config[key]
        except Exception as e:
            print(f"Unable get config value: {e}")
            return cls.DEFAULT_CONFIG[key]

    @classmethod
    def set(cls, key, value):
        """Set new value for config and automatically saves it"""
        try:
            cls._current_config[key] = value
            cls.save()
        except Exception as e:
            print(f"ERROR: Unable to set new value {value} for a key {key}")