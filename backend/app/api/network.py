from fastapi import APIRouter, Depends

from app.core.security import TokenData, get_current_user
from app.services.network_service import NetworkService, get_network_service

router = APIRouter(prefix="/network", tags=["Business Network Topology"])


@router.get("", response_model=dict)
def get_network_graph(
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns full network graph topology JSON formatted for React Flow visualization ({ nodes: [...], edges: [...] })."""
    return network_service.to_graph_json()
