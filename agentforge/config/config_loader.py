import yaml
import os
from typing import Dict, Any

class ConfigLoader:
    _instance = None
    _config_cache = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    @classmethod
    def load_model_config(cls) -> Dict[str, Any]:
        return cls._load_yaml("agentforge/config/model_config.yaml")

    @classmethod
    def load_agent_config(cls) -> Dict[str, Any]:
        return cls._load_yaml("agentforge/config/agent_configs.yaml")

    @classmethod
    def _load_yaml(cls, path: str) -> Dict[str, Any]:
        if path in cls._config_cache:
            return cls._config_cache[path]
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")
            
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            cls._config_cache[path] = config
            return config
