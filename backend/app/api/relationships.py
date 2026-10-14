from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import TokenData, get_current_user
from app.models.entity import BusinessRelationship
from app.services.network_service import NetworkService, get_network_service

router = APIRouter(prefix="/relationships", tags=["Business Relationships"])


@router.post("", response_model=BusinessRelationship, status_code=status.HTTP_201_CREATED)
def create_relationship(
    relationship: BusinessRelationship,
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Creates a new directed dependency relationship edge between two entities."""
    try:
        return network_service.add_relationship(relationship)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )


@router.get("", response_model=List[BusinessRelationship])
def list_relationships(
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Lists all configured dependency relationships."""
    return network_service.list_relationships()


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: str,
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Removes a relationship edge from the network graph by ID."""
    try:
        network_service.remove_relationship(relationship_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relationship with ID '{relationship_id}' not found.",
        )
