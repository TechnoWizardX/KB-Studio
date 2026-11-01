import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

from src.resources.data import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class ConfigManager():

    DEFAULT_CONFIG: dict[str, Any] = DEFAULT_CONFIG

    _current_config: dict[str, Any] = {}

    @classmethod
    def get_str_config_path(cls):
        return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    
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
            except OSError as error:
                logger.error("Cannot create config file: %s", error)
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

                migrated_message_count = "showed_messages_limit" in cls._current_config
                legacy_message_count = cls._current_config.pop("showed_messages_limit", None)
                if "startup_message_count" not in cls._current_config:
                    if (
                        isinstance(legacy_message_count, int)
                        and not isinstance(legacy_message_count, bool)
                        and legacy_message_count > 0
                    ):
                        cls._current_config["startup_message_count"] = (
                            legacy_message_count
                        )

                for key, val in cls.DEFAULT_CONFIG.items():
                    if key not in cls._current_config:
                        cls._current_config[key] = val
                if migrated_message_count:
                    cls.save()
        except (OSError, ValueError, TypeError) as error:
            logger.error("Cannot read config, falling back to defaults: %s", error)
            cls._current_config = cls.DEFAULT_CONFIG.copy()

    @classmethod
    def save(cls):
        """Saves current config in config file"""
        config_file = cls.get_config_path()
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(cls._current_config, f, indent=4, ensure_ascii=False)
        except (OSError, TypeError) as error:
            logger.error("Cannot save config: %s", error)

    @classmethod
    def get(cls, key):
        """Returns current config value by a key, if not available - returns default value"""
        try:
            return cls._current_config[key]
        except KeyError:
            logger.debug("Missing config key %r, using the default", key)
            return cls.DEFAULT_CONFIG[key]

    @classmethod
    def set(cls, key, value):
        """Set new value for config and automatically saves it"""
        try:
            cls._current_config[key] = value
            cls.save()
        except (KeyError, TypeError) as error:
            logger.error("Cannot set config key %r: %s", key, error)
