from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import TokenData, get_current_user
from app.models.entity import BusinessEntity
from app.services.network_service import NetworkService, get_network_service

router = APIRouter(prefix="/entities", tags=["Business Entities"])


@router.post("", response_model=BusinessEntity, status_code=status.HTTP_201_CREATED)
def create_entity(
    entity: BusinessEntity,
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Creates a new BusinessEntity in the business network graph."""
    return network_service.add_entity(entity)


@router.get("", response_model=List[BusinessEntity])
def list_entities(
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Lists all configured business entities."""
    return network_service.list_entities()


@router.get("/{entity_id}", response_model=BusinessEntity)
def get_entity(
    entity_id: str,
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Retrieves a single business entity by ID."""
    entity = network_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business entity with ID '{entity_id}' not found.",
        )
    return entity


@router.put("/{entity_id}", response_model=BusinessEntity)
def update_entity(
    entity_id: str,
    patch: dict,
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Updates fields of an existing business entity."""
    try:
        return network_service.update_entity(entity_id, patch)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business entity with ID '{entity_id}' not found.",
        )


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(
    entity_id: str,
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Deletes an entity and its associated relationship edges from the network graph."""
    try:
        network_service.remove_entity(entity_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business entity with ID '{entity_id}' not found.",
        )


@router.get("/{entity_id}/downstream", response_model=List[BusinessEntity])
def get_downstream_entities(
    entity_id: str,
    max_depth: int = Query(default=3, ge=1, le=10),
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns all downstream entities dependent on entity_id up to max_depth traversal."""
    entity = network_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business entity with ID '{entity_id}' not found.",
        )
    return network_service.get_downstream(entity_id, max_depth=max_depth)


@router.get("/{entity_id}/location")
def get_entity_location(
    entity_id: str,
    network_service: NetworkService = Depends(get_network_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Retrieves structured geographic location and GPS coordinates for an entity."""
    entity = network_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business entity with ID '{entity_id}' not found.",
        )
    return {
        "entity_id": entity.id,
        "entity_name": entity.name,
        "entity_type": entity.type,
        "location": entity.location,
        "address": entity.address,
        "city": entity.city,
        "district": entity.district,
        "state": entity.state,
        "country": entity.country,
        "postal_code": entity.postal_code,
        "latitude": entity.latitude,
        "longitude": entity.longitude,
        "location_source": entity.location_source,
        "location_confidence": entity.location_confidence,
    }
