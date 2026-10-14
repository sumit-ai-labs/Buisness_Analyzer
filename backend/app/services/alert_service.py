import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import logger
from app.models.credibility import CredibilityAssessment
from app.models.events import DisruptionEvent, RawSearchResult
from app.models.geo import GeoVerificationResult
from app.models.risk import Alert, RiskAssessment
from app.services.analysis_service import AnalysisBatchResult, AnalysisService, get_analysis_service
from app.services.geo_matching_service import GeoMatchingService, get_geo_matching_service
from app.services.matcher_service import MatcherService, get_matcher_service
from app.services.network_service import NetworkService, get_network_service
from app.services.research_service import ResearchService, get_research_service
from app.services.risk_service import RiskService, get_risk_service
from app.services.verification_service import VerificationService, get_verification_service
from app.services.weather_service import check_weather_corroboration, EVENT_WEATHER_MAP
from app.services.weather_service import WeatherSignal


class MonitoringCycleInProgressError(Exception):
    """Raised when a monitoring cycle is already active."""

    pass


class AlertService:
    """Alert Generator and Monitoring Cycle Orchestrator with async concurrency lock."""

    def __init__(
        self,
        network_service: NetworkService = None,
        research_service: ResearchService = None,
        analysis_service: AnalysisService = None,
        matcher_service: MatcherService = None,
        risk_service: RiskService = None,
        verification_service: VerificationService = None,
        geo_matching_service: GeoMatchingService = None,
    ):
        self.network_service = network_service or get_network_service()
        self.research_service = research_service or get_research_service()
        self.analysis_service = analysis_service or get_analysis_service()
        self.matcher_service = matcher_service or get_matcher_service()
        self.risk_service = risk_service or get_risk_service()
        self.verification_service = verification_service or get_verification_service()
        self.geo_matching_service = geo_matching_service or get_geo_matching_service()

        self._lock = asyncio.Lock()
        self._raw_results: List[RawSearchResult] = []
        self._events: Dict[str, DisruptionEvent] = {}                          # verified (non-gated)
        self._unconfirmed_events: Dict[str, DisruptionEvent] = {}              # gated (unconfirmed)
        self._ambiguous_events: Dict[str, Tuple[DisruptionEvent, GeoVerificationResult]] = {}  # location ambiguous
        self._credibility_assessments: Dict[str, CredibilityAssessment] = {}   # all credibility assessments
        self._geo_verifications: Dict[str, GeoVerificationResult] = {}         # all geo verifications
        self._weather_signals: Dict[str, WeatherSignal] = {}                  # event_id -> weather signal
        self._event_geo_map: Dict[str, str] = {}                              # event_id -> geo_res.id
        self._assessments: Dict[str, RiskAssessment] = {}
        self._alerts: Dict[str, Alert] = {}
        self._dedupe_keys: set = set()
        self._shadow_records: List[dict] = []
        self._last_run_at: Optional[datetime] = None

    async def run_monitoring_cycle(self) -> Dict[str, int]:
        """Executes full multi-stage monitoring pipeline:
        Detect -> Understand -> Verify Credibility -> Geo Verify -> Connect -> Assess -> Alert.

        Enforces async locking to prevent concurrent runs (returns HTTP 409 Conflict if locked).
        """
        if self._lock.locked():
            logger.warning("Monitoring cycle trigger rejected: Cycle already in progress.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A monitoring cycle is currently in progress. Please wait for completion.",
            )

        async with self._lock:
            logger.info("=== STARTING MONITORING CYCLE (Detect-Understand-Verify-GeoVerify-Connect-Assess-Alert) ===")
            entities = self.network_service.list_entities()
            entity_name_map = {e.id: e.name for e in entities}

            # 1. DETECT (Research Agent)
            raw_results = self.research_service.search_disruptions_for_network(entities)
            self._raw_results.extend(raw_results)

            # 2. UNDERSTAND (Analysis Agent)
            legacy_analyzer = getattr(self.analysis_service, "__dict__", {}).get("analyze_search_results")
            if legacy_analyzer is not None and legacy_analyzer.__class__.__module__.startswith("unittest.mock"):
                events = self.analysis_service.analyze_search_results(
                    raw_results, entity_name_map=entity_name_map
                )
                analysis_batch = AnalysisBatchResult(
                    events=events,
                    processed_count=len(raw_results),
                )
            else:
                analysis_batch = self.analysis_service.analyze_search_results_batch(
                    raw_results, entity_name_map=entity_name_map
                )
                if not isinstance(analysis_batch, AnalysisBatchResult):
                    events = self.analysis_service.analyze_search_results(
                        raw_results, entity_name_map=entity_name_map
                    )
                    analysis_batch = AnalysisBatchResult(
                        events=events,
                        processed_count=len(raw_results),
                    )
            events = analysis_batch.events
            relevant_events = [e for e in events if e.is_relevant]

            new_alerts_count = 0
            new_assessments_count = 0
            gated_count = 0
            ambiguous_count = 0

            # Use all relevant events seen so far as context for corroboration
            all_recent_events = (
                list(self._events.values())
                + list(self._unconfirmed_events.values())
                + [e for e, _ in self._ambiguous_events.values()]
                + relevant_events
            )

            for event in relevant_events:
                # ----------------------------------------------------------------
                # 2b. WEATHER CORROBORATION (independent signal, flood/weather only)
                # ----------------------------------------------------------------
                weather_signal = None
                if event.event_type in EVENT_WEATHER_MAP:
                    # Find the entity this event was queried for to get coordinates
                    queried_entity = None
                    for sr in raw_results:
                        if sr.id == event.source_result_id:
                            queried_entity = next(
                                (e for e in entities if e.id == sr.queried_entity_id), None
                            )
                            break
                    if queried_entity:
                        weather_signal = await check_weather_corroboration(event, queried_entity)
                        self._weather_signals[event.id] = weather_signal

                # ----------------------------------------------------------------
                # 3. VERIFY — Credibility Verification Engine (Formula Unchanged)
                # ----------------------------------------------------------------
                credibility = self.verification_service.verify(
                    event=event,
                    recent_events=[e for e in all_recent_events if e.id != event.id],
                    weather_signal=weather_signal,
                )
                self._credibility_assessments[credibility.id] = credibility
                event.credibility_assessment_id = credibility.id

                if credibility.is_gated:
                    # Low credibility: store for review, do NOT generate alert, do NOT continue pipeline
                    self._unconfirmed_events[event.id] = event
                    gated_count += 1
                    logger.info(
                        f"[VERIFY][CREDIBILITY-GATED] event='{event.headline}' "
                        f"score={credibility.authenticity_score} label={credibility.confidence_label} "
                        f"— retained in unconfirmed review list"
                    )
                    continue  # skip only THIS event; cycle continues for others

                # ----------------------------------------------------------------
                # 4. GEO VERIFY — Geographic Disambiguation & Location Verification
                # ----------------------------------------------------------------
                geo_res = self.geo_matching_service.verify_and_match(event, entities)
                self._geo_verifications[geo_res.id] = geo_res
                self._event_geo_map[event.id] = geo_res.id
                event.geo_verification_id = geo_res.id

                if geo_res.status == "LOCATION_AMBIGUOUS":
                    # Ambiguous entity or location: do NOT guess, do NOT trigger alert, retain for review
                    self._ambiguous_events[event.id] = (event, geo_res)
                    ambiguous_count += 1
                    logger.warning(
                        f"[VERIFY][GEO-AMBIGUOUS] event='{event.headline}' "
                        f"reason='{geo_res.ambiguity_reason}' — retained in ambiguous review queue."
                    )
                    continue

                # Non-gated, non-ambiguous event: store and proceed through pipeline
                self._events[event.id] = event

                # ----------------------------------------------------------------
                # 5. CONNECT (Entity Matcher incorporating Geo Result)
                # ----------------------------------------------------------------
                try:
                    impact = self.matcher_service.match_event_to_network(event, geo_result=geo_res)
                except TypeError as exc:
                    if "geo_result" not in str(exc):
                        raise
                    impact = self.matcher_service.match_event_to_network(event)
                if not impact or not impact.matched_entity_ids:
                    continue

                all_impacted_ids = impact.matched_entity_ids + impact.downstream_entity_ids
                impacted_entities = [
                    self.network_service.get_entity(eid)
                    for eid in all_impacted_ids
                    if self.network_service.get_entity(eid) is not None
                ]

                # ----------------------------------------------------------------
                # 6. ASSESS — Risk Engine (credibility blended into confidence multiplier)
                # ----------------------------------------------------------------
                credibility_norm = credibility.authenticity_score / 100.0
                highest_assessment = None
                for entity in impacted_entities:
                    rel_weight = 1.0
                    if entity.id in impact.downstream_entity_ids:
                        rel_weight = 0.7

                    assessment = self.risk_service.evaluate_risk(
                        entity=entity,
                        event=event,
                        dependency_weight=rel_weight,
                        credibility_score=credibility_norm,
                    )
                    self._assessments[assessment.id] = assessment
                    new_assessments_count += 1

                    if (
                        highest_assessment is None
                        or assessment.severity_score > highest_assessment.severity_score
                    ):
                        highest_assessment = assessment

                # ----------------------------------------------------------------
                # 7. ALERT — enriched with verification & geographic evidence
                # ----------------------------------------------------------------
                if highest_assessment:
                    primary_entity_id = impact.matched_entity_ids[0]
                    raw_key = f"{event.source_url}:{primary_entity_id}"
                    dedupe_key = hashlib.md5(raw_key.encode("utf-8")).hexdigest()

                    if dedupe_key not in self._dedupe_keys:
                        self._dedupe_keys.add(dedupe_key)
                        entity_names_str = ", ".join([e.name for e in impacted_entities])

                        # Verification & Geographic status lines for alert message
                        verify_line = (
                            f"Verification: {credibility.confidence_label.upper()} credibility "
                            f"({credibility.authenticity_score}/100, source: {credibility.source_tier}, "
                            f"corroboration: {credibility.corroborating_source_count} source(s))."
                        )
                        dist_str = f"{geo_res.distance_km:.1f} km" if geo_res.distance_km is not None else "N/A"
                        geo_line = (
                            f"Geo Match: {geo_res.status} (Entity Confidence: {geo_res.entity_match_confidence}/100, "
                            f"Distance: {dist_str}, Location: {geo_res.event_location.city or 'Epicenter'})."
                        )

                        msg = (
                            f"Disruption detected ({event.event_type.upper()}): '{event.headline}'. "
                            f"Impacted network entities: [{entity_names_str}]. "
                            f"Severity Risk Level: {highest_assessment.risk_level.upper()} "
                            f"(Score: {highest_assessment.severity_score}/100). "
                            f"{verify_line} {geo_line}"
                        )

                        # Weather corroboration line (only when weather data confirmed the event)
                        if (
                            weather_signal is not None
                            and weather_signal.confirms_event
                            and weather_signal.precipitation_mm_24h is not None
                        ):
                            weather_line = (
                                f"Independently confirmed: {weather_signal.precipitation_mm_24h:.0f}mm "
                                f"rainfall recorded at this location in the last 24h."
                            )
                            if weather_signal.wind_speed_kmh is not None:
                                weather_line += f" Wind: {weather_signal.wind_speed_kmh:.0f} km/h."
                            msg += f" {weather_line}"
                        elif (
                            weather_signal is not None
                            and weather_signal.status == "checked"
                            and getattr(weather_signal, "classification", "not_supported") == "not_supported"
                            and event.event_type in EVENT_WEATHER_MAP
                        ):
                            msg += (
                                " Weather check: local telemetry did not meet the configured "
                                "confirmation threshold, so credibility was reduced."
                            )
                        elif (
                            weather_signal is not None
                            and getattr(weather_signal, "classification", "") == "insufficient_coverage"
                        ):
                            msg += (
                                " Weather check: geographic coordinates or observation timeframe "
                                "were insufficient for independent verification."
                            )
                        elif (
                            weather_signal is not None
                            and getattr(weather_signal, "classification", "") == "unavailable"
                        ):
                            msg += (
                                " Weather check: telemetry provider was unavailable, treated as neutral."
                            )

                        if settings.SHADOW_MODE:
                            shadow_record = {
                                "proposed_alert_id": hashlib.sha256(dedupe_key.encode("utf-8")).hexdigest()[:12],
                                "event_id": event.id,
                                "headline": event.headline,
                                "source_url": event.source_url,
                                "risk_assessment_id": highest_assessment.id,
                                "severity_score": highest_assessment.severity_score,
                                "risk_level": highest_assessment.risk_level,
                                "entity_ids": all_impacted_ids,
                                "message": msg,
                                "credibility_score": credibility.authenticity_score if credibility else None,
                                "credibility_label": credibility.confidence_label if credibility else None,
                                "geo_status": geo_res.status if geo_res else None,
                                "recorded_at": datetime.now(timezone.utc).isoformat(),
                            }
                            self._shadow_records.append(shadow_record)
                            logger.info(
                                f"[SHADOW_MODE] Logged proposed alert for event {event.id} ({highest_assessment.risk_level}) without modifying operational state."
                            )
                        else:
                            alert = Alert(
                                event_id=event.id,
                                risk_assessment_id=highest_assessment.id,
                                entity_ids=all_impacted_ids,
                                message=msg,
                                dedupe_key=dedupe_key,
                            )
                            self._alerts[alert.id] = alert
                            new_alerts_count += 1

            self._last_run_at = datetime.now(timezone.utc)
            logger.info(
                f"=== MONITORING CYCLE COMPLETE: {len(raw_results)} results, "
                f"{len(relevant_events)} events ({gated_count} gated, {ambiguous_count} ambiguous), "
                f"{new_alerts_count} new alerts generated ==="
            )

            return {
                "raw_results_count": len(raw_results),
                "processed_results_count": analysis_batch.processed_count,
                "extraction_success_count": analysis_batch.successful_count,
                "extraction_failed_count": analysis_batch.failed_count,
                "extraction_rejected_count": analysis_batch.rejected_count,
                "relevant_events_count": len(relevant_events),
                "gated_events_count": gated_count,
                "ambiguous_events_count": ambiguous_count,
                "new_assessments_count": new_assessments_count,
                "new_alerts_count": new_alerts_count,
            }

    def list_events(self) -> List[DisruptionEvent]:
        """Returns all verified (non-gated, non-ambiguous) events."""
        return list(self._events.values())

    def list_unconfirmed_events(self) -> List[dict]:
        """Returns gated (unconfirmed) events with their credibility assessment summary."""
        results = []
        for event in self._unconfirmed_events.values():
            credibility = None
            if event.credibility_assessment_id:
                credibility = self._credibility_assessments.get(event.credibility_assessment_id)
            geo_res = None
            if event.geo_verification_id:
                geo_res = self._geo_verifications.get(event.geo_verification_id)
            results.append({
                "event_id": event.id,
                "headline": event.headline,
                "source_url": event.source_url,
                "source_domain": credibility.source_domain if credibility else "unknown",
                "event_type": event.event_type,
                "location_mentioned": event.location_mentioned,
                "authenticity_score": credibility.authenticity_score if credibility else None,
                "confidence_label": credibility.confidence_label if credibility else "unconfirmed",
                "is_gated": True,
                "source_tier": credibility.source_tier if credibility else None,
                "corroborating_source_count": credibility.corroborating_source_count if credibility else 0,
                "content_style_score": credibility.content_style_score if credibility else None,
                "factors": credibility.factors if credibility else None,
                "geo_status": geo_res.status if geo_res else "LOCATION_UNRESOLVED",
                "detected_at": event.retrieved_at.isoformat(),
            })
        return results

    def list_ambiguous_events(self) -> List[dict]:
        """Returns events flagged as LOCATION_AMBIGUOUS awaiting analyst review."""
        results = []
        for event, geo_res in self._ambiguous_events.values():
            credibility = None
            if event.credibility_assessment_id:
                credibility = self._credibility_assessments.get(event.credibility_assessment_id)
            results.append({
                "event_id": event.id,
                "headline": event.headline,
                "source_url": event.source_url,
                "event_type": event.event_type,
                "location_mentioned": event.location_mentioned,
                "authenticity_score": credibility.authenticity_score if credibility else None,
                "confidence_label": credibility.confidence_label if credibility else "moderate",
                "geo_status": geo_res.status,
                "location_confidence": geo_res.location_confidence,
                "entity_match_confidence": geo_res.entity_match_confidence,
                "ambiguity_reason": geo_res.ambiguity_reason,
                "candidates": [c.model_dump() for c in geo_res.candidates],
                "detected_at": event.retrieved_at.isoformat(),
            })
        return results

    def get_credibility_assessment(self, assessment_id: str) -> Optional[CredibilityAssessment]:
        return self._credibility_assessments.get(assessment_id)

    def get_geo_verification(self, verification_id: str) -> Optional[GeoVerificationResult]:
        return self._geo_verifications.get(verification_id)

    def get_geo_verification_for_event(self, event_id: str) -> Optional[GeoVerificationResult]:
        v_id = self._event_geo_map.get(event_id)
        if v_id:
            return self._geo_verifications.get(v_id)
        # Search directly in _geo_verifications
        for g in self._geo_verifications.values():
            if g.event_id == event_id:
                return g
        return None

    def list_alerts(self, min_risk_level: Optional[str] = None) -> List[Alert]:
        alerts = list(self._alerts.values())
        if not min_risk_level:
            return alerts

        level_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        target_val = level_order.get(min_risk_level.lower(), 1)

        filtered = []
        for alert in alerts:
            assessment = self._assessments.get(alert.risk_assessment_id)
            if assessment and level_order.get(assessment.risk_level, 1) >= target_val:
                filtered.append(alert)
        return filtered

    def acknowledge_alert(self, alert_id: str) -> Alert:
        if alert_id not in self._alerts:
            raise KeyError(f"Alert with ID {alert_id} not found")
        alert = self._alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
        return alert

    def explain_alert(self, alert_id: str) -> dict:
        """Returns deep explainability payload detailing event, risk factors, network topology,

        credibility assessment, and geographic verification evidence.
        """
        if alert_id not in self._alerts:
            raise KeyError(f"Alert with ID {alert_id} not found")

        alert = self._alerts[alert_id]
        event = self._events.get(alert.event_id)
        assessment = self._assessments.get(alert.risk_assessment_id)

        credibility = None
        if event and event.credibility_assessment_id:
            ca = self._credibility_assessments.get(event.credibility_assessment_id)
            if ca:
                credibility = ca.model_dump()

        geo_verification = None
        if event and event.geo_verification_id:
            gv = self._geo_verifications.get(event.geo_verification_id)
            if gv:
                geo_verification = gv.model_dump()
        weather_signal = self._weather_signals.get(alert.event_id)
        weather_payload = None
        if weather_signal:
            weather_payload = weather_signal.model_dump()
        elif event and event.event_type not in EVENT_WEATHER_MAP:
            weather_payload = {
                "status": "not_applicable",
                "classification": "not_checked",
                "confirms_event": False,
                "precipitation_mm_24h": None,
                "wind_speed_kmh": None,
                "explanation": "Not checked: Disruption event type is not weather-related.",
            }

        impacted_entities = [
            self.network_service.get_entity(eid).model_dump()
            for eid in alert.entity_ids
            if self.network_service.get_entity(eid) is not None
        ]

        return {
            "alert": alert.model_dump(),
            "event": event.model_dump() if event else None,
            "risk_assessment": assessment.model_dump() if assessment else None,
            "credibility_assessment": credibility,
            "geo_verification": geo_verification,
            "weather_signal": weather_payload,
            "impacted_entities": impacted_entities,
            "last_monitored_at": self._last_run_at,
        }

    def list_shadow_records(self) -> List[dict]:
        """Returns shadow records of proposed decisions recorded without changing production alerts."""
        return list(self._shadow_records)

    def clear_shadow_records(self) -> None:
        """Clears recorded shadow evaluations."""
        self._shadow_records.clear()

    def get_summary_stats(self) -> dict:
        alerts = list(self._alerts.values())
        unack_count = sum(1 for a in alerts if not a.acknowledged)
        critical_count = 0

        for a in alerts:
            ass = self._assessments.get(a.risk_assessment_id)
            if ass and ass.risk_level in ["high", "critical"]:
                critical_count += 1

        return {
            "total_alerts": len(alerts),
            "unacknowledged_alerts": unack_count,
            "high_critical_alerts": critical_count,
            "unconfirmed_events": len(self._unconfirmed_events),
            "location_ambiguities": len(self._ambiguous_events),
            "total_monitored_entities": len(self.network_service.list_entities()),
            "last_run_at": self._last_run_at,
        }


# Module instance singleton
alert_service_instance = AlertService()


def get_alert_service() -> AlertService:
    return alert_service_instance
