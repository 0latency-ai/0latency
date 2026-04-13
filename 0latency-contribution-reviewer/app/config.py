"""Configuration management for contribution reviewer."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration loader with environment variable substitution."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load config file and substitute environment variables."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        return self._substitute_env_vars(config)
    
    def _substitute_env_vars(self, obj: Any) -> Any:
        """Recursively substitute ${VAR} and ${VAR:default} patterns."""
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Handle ${VAR} and ${VAR:default} patterns
            if obj.startswith('${') and obj.endswith('}'):
                var_expr = obj[2:-1]
                if ':' in var_expr:
                    var_name, default = var_expr.split(':', 1)
                    return os.getenv(var_name, default)
                else:
                    value = os.getenv(var_expr)
                    if value is None:
                        raise ValueError(f"Environment variable {var_expr} not set")
                    return value
        return obj
    
    def get(self, key_path: str, default=None) -> Any:
        """Get config value by dot-separated path (e.g., 'stripe.api_key')."""
        keys = key_path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value
    
    @property
    def all(self) -> Dict[str, Any]:
        """Return entire config dict."""
        return self._config


# Global config instance
config = None


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from file."""
    global config
    config = Config(config_path)
    return config


def get_config() -> Config:
    """Get global config instance."""
    if config is None:
        raise RuntimeError("Config not loaded. Call load_config() first.")
    return config
