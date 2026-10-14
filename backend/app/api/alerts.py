from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import TokenData, get_current_user
from app.models.events import DisruptionEvent
from app.models.risk import Alert
from app.services.alert_service import AlertService, get_alert_service

router = APIRouter(tags=["Monitoring & Alerts"])


@router.post("/monitor/run", status_code=status.HTTP_200_OK)
async def run_monitoring_cycle(
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Triggers the full 6-stage automated monitoring cycle
    (Detect -> Understand -> Verify -> Connect -> Assess -> Alert).
    """
    return await alert_service.run_monitoring_cycle()


@router.get("/events", response_model=List[DisruptionEvent])
def list_disruption_events(
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Lists all verified (non-gated) disruption events that passed credibility verification."""
    return alert_service.list_events()


@router.get("/events/unconfirmed")
def list_unconfirmed_events(
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Lists disruption events that were detected but did not pass the credibility gate.

    These events are RETAINED for review — they are NOT deleted.
    Low credibility_score (<35) means the system flagged them as 'unconfirmed',
    not as 'fake'. They may be promoted manually or re-evaluated with additional evidence.

    This endpoint demonstrates the design principle:
    'Low-confidence events are flagged, not discarded.'
    """
    return alert_service.list_unconfirmed_events()


@router.get("/events/{event_id}/credibility")
def get_event_credibility(
    event_id: str,
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns the credibility assessment for a specific event (verified or unconfirmed).

    Shows the full factor breakdown: source reputation, corroboration,
    ML content-style score, LLM extraction confidence, and final authenticity score.
    """
    # Check verified events first
    event = alert_service._events.get(event_id) or alert_service._unconfirmed_events.get(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID '{event_id}' not found.",
        )
    if not event.credibility_assessment_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credibility assessment found for event '{event_id}'.",
        )
    ca = alert_service.get_credibility_assessment(event.credibility_assessment_id)
    if not ca:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credibility assessment not found for event '{event_id}'.",
        )
    return ca.model_dump()


@router.get("/alerts", response_model=List[Alert])
def list_alerts(
    min_risk_level: Optional[str] = Query(None, description="Filter alerts by min risk level (low, medium, high, critical)"),
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Lists generated early-warning alerts (only for verified, non-gated events)."""
    return alert_service.list_alerts(min_risk_level=min_risk_level)


@router.get("/alerts/shadow")
def list_shadow_alerts(
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns proposed alert decisions recorded during shadow execution mode without affecting production."""
    return alert_service.list_shadow_records()


@router.post("/alerts/{alert_id}/acknowledge", response_model=Alert)
def acknowledge_alert(
    alert_id: str,
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Marks an alert as acknowledged by the operator."""
    try:
        return alert_service.acknowledge_alert(alert_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )


@router.get("/alerts/{alert_id}/explain")
def explain_alert(
    alert_id: str,
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns transparent explanation breakdown for an alert including event, risk factors,
    credibility assessment, and impacted network nodes.
    """
    try:
        return alert_service.explain_alert(alert_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )


@router.get("/dashboard/stats")
def get_dashboard_stats(
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns overview summary metrics for the operational dashboard,
    including count of unconfirmed (gated) events awaiting review.
    """
    return alert_service.get_summary_stats()

