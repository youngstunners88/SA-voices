"""
Environment Management System

Manages different deployment environments with proper
configuration, secrets, and resource allocation.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json
import yaml


class EnvironmentType(Enum):
    """Deployment environment types"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"


@dataclass
class EnvironmentConfig:
    """Configuration for an environment"""
    name: str
    type: EnvironmentType
    debug: bool = False
    log_level: str = "INFO"
    database_url: Optional[str] = None
    redis_url: Optional[str] = None
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    workers: int = 1
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, Union[int, float]] = field(default_factory=dict)
    secrets: Dict[str, str] = field(default_factory=dict, repr=False)
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentConfig":
        """Create config from dictionary"""
        config_data = data.copy()
        if "type" in config_data:
            config_data["type"] = EnvironmentType(config_data["type"])
        return cls(**config_data)
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "EnvironmentConfig":
        """Load config from file"""
        path = Path(path)
        
        with open(path) as f:
            if path.suffix == '.json':
                data = json.load(f)
            elif path.suffix in ['.yml', '.yaml']:
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported config format: {path.suffix}")
        
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "name": self.name,
            "type": self.type.value,
            "debug": self.debug,
            "log_level": self.log_level,
            "database_url": self.database_url,
            "redis_url": self.redis_url,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "workers": self.workers,
            "features": self.features,
            "limits": self.limits,
            "extra": self.extra,
        }
    
    def get_secret(self, key: str) -> Optional[str]:
        """Get secret value"""
        # First check environment variable
        env_key = f"SA_VOICES_{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key]
        
        # Then check secrets store
        return self.secrets.get(key)
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if feature is enabled"""
        return self.features.get(feature, False)
    
    def get_limit(self, resource: str, default: Union[int, float] = None) -> Union[int, float]:
        """Get resource limit"""
        return self.limits.get(resource, default)


class Environment:
    """
    Environment manager.
    
    Manages multiple environments and provides
    context-aware configuration access.
    """
    
    _instance: Optional["Environment"] = None
    _current: Optional[EnvironmentConfig] = None
    _configs: Dict[str, EnvironmentConfig] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._load_default_configs()
    
    def _load_default_configs(self):
        """Load default environment configurations"""
        # Development
        self.register_config(EnvironmentConfig(
            name="development",
            type=EnvironmentType.DEVELOPMENT,
            debug=True,
            log_level="DEBUG",
            api_host="127.0.0.1",
            api_port=8000,
            workers=1,
            features={
                "debug_ui": True,
                "auto_reload": True,
                "detailed_errors": True,
            },
        ))
        
        # Testing
        self.register_config(EnvironmentConfig(
            name="testing",
            type=EnvironmentType.TESTING,
            debug=False,
            log_level="WARNING",
            api_port=8001,
            workers=1,
            features={
                "mock_external": True,
                "fast_tests": True,
            },
            limits={
                "test_timeout": 30,
            },
        ))
        
        # Production
        self.register_config(EnvironmentConfig(
            name="production",
            type=EnvironmentType.PRODUCTION,
            debug=False,
            log_level="INFO",
            api_host="0.0.0.0",
            api_port=8000,
            workers=4,
            features={
                "caching": True,
                "rate_limiting": True,
                "metrics": True,
                "health_checks": True,
            },
            limits={
                "max_requests_per_minute": 100,
                "max_upload_size_mb": 100,
                "max_concurrent_tts": 10,
            },
        ))
    
    def register_config(self, config: EnvironmentConfig):
        """Register environment configuration"""
        self._configs[config.name] = config
    
    def set_current(self, name: str):
        """Set current environment"""
        if name not in self._configs:
            raise ValueError(f"Unknown environment: {name}")
        
        self._current = self._configs[name]
        
        # Set environment variables
        os.environ["SA_VOICES_ENV"] = name
        os.environ["SA_VOICES_DEBUG"] = str(self._current.debug)
        os.environ["SA_VOICES_LOG_LEVEL"] = self._current.log_level
    
    def get_current(self) -> EnvironmentConfig:
        """Get current environment config"""
        if self._current is None:
            # Auto-detect from environment
            env_name = os.environ.get("SA_VOICES_ENV", "development")
            self.set_current(env_name)
        
        return self._current
    
    def get_config(self, name: str) -> Optional[EnvironmentConfig]:
        """Get config by name"""
        return self._configs.get(name)
    
    def list_environments(self) -> List[str]:
        """List all registered environments"""
        return list(self._configs.keys())
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.get_current().type == EnvironmentType.DEVELOPMENT
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.get_current().type == EnvironmentType.PRODUCTION
    
    def load_from_directory(self, directory: Union[str, Path]):
        """Load all environment configs from directory"""
        directory = Path(directory)
        
        for config_file in directory.glob("*.yml"):
            config = EnvironmentConfig.from_file(config_file)
            self.register_config(config)


# Global environment instance
def get_environment() -> Environment:
    """Get global environment instance"""
    return Environment()


def get_config() -> EnvironmentConfig:
    """Get current environment configuration"""
    return get_environment().get_current()
