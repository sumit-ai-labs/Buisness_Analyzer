from fastapi import APIRouter, Depends
from app.core.dynamic_config import DynamicConfigStore, SystemConfig, get_config_store
from app.core.security import TokenData, get_current_user

router = APIRouter(prefix="/config", tags=["Dynamic Risk Configuration"])


@router.get("", response_model=SystemConfig)
def get_system_config(
    config_store: DynamicConfigStore = Depends(get_config_store),
    current_user: TokenData = Depends(get_current_user),
):
    """Retrieves active risk scoring weights and classification thresholds."""
    return config_store.get_config()


@router.put("", response_model=SystemConfig)
def update_system_config(
    new_config: SystemConfig,
    config_store: DynamicConfigStore = Depends(get_config_store),
    current_user: TokenData = Depends(get_current_user),
):
    """Updates and persists risk scoring weights and thresholds in backend/data/config.json."""
    return config_store.save_config(new_config)
