import json
import os
from typing import Dict
from pydantic import BaseModel, Field

from app.core.logging import logger

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "config.json")


class RiskWeightsConfig(BaseModel):
    dependency: float = Field(default=0.30, ge=0.0, le=1.0)
    criticality: float = Field(default=0.25, ge=0.0, le=1.0)
    lead_time: float = Field(default=0.20, ge=0.0, le=1.0)
    single_source: float = Field(default=0.15, ge=0.0, le=1.0)
    confidence: float = Field(default=0.10, ge=0.0, le=1.0)


class RiskThresholdsConfig(BaseModel):
    low: float = Field(default=25.0, ge=0.0, le=100.0)
    medium: float = Field(default=50.0, ge=0.0, le=100.0)
    high: float = Field(default=75.0, ge=0.0, le=100.0)


class SystemConfig(BaseModel):
    """Dynamic configuration model persisted in backend/data/config.json."""

    weights: RiskWeightsConfig = Field(default_factory=RiskWeightsConfig)
    thresholds: RiskThresholdsConfig = Field(default_factory=RiskThresholdsConfig)


class DynamicConfigStore:
    """Manages persistent loading and updating of runtime risk weights and thresholds."""

    def __init__(self, file_path: str = CONFIG_FILE_PATH):
        self.file_path = file_path
        self._config = self.load_config()

    def load_config(self) -> SystemConfig:
        """Loads configuration from JSON file or initializes default config."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return SystemConfig(**data)
            except Exception as err:
                logger.error(f"Failed to load dynamic config file from {self.file_path}: {err}")

        default_config = SystemConfig()
        self.save_config(default_config)
        return default_config

    def get_config(self) -> SystemConfig:
        return self._config

    def save_config(self, config: SystemConfig) -> SystemConfig:
        """Persists system configuration to JSON file."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2)
        self._config = config
        logger.info(f"Updated dynamic risk configuration saved to {self.file_path}")
        return config


# Singleton store instance
config_store = DynamicConfigStore()


def get_config_store() -> DynamicConfigStore:
    return config_store
