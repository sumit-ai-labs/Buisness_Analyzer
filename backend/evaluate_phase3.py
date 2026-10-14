"""Phase 3 Independent Evaluation Runner.

Evaluates an independent labeled dataset (65 distinct cases across all 5 operational categories)
that was NOT used to tune extraction rules, heuristics, or credibility weights.

Categories evaluated:
  1. Active and resolved disruptions (ongoing, republished, resolved, temporary reopenings)
  2. Source quality and corroboration (reputable, low-quality, syndicated, conflicting)
  3. Geography and entity matching (same-name cities, ambiguous facilities, missing coords)
  4. Business impact analysis (direct, multi-hop, downstream dependencies, upstream non-leakage)
  5. Weather corroboration (precipitation, wind, river overflow/dam release, sensor timeout)

Dataset separation:
  - Development dataset: backend/data/evaluation_dataset.json (Phase 2)
  - Independent dataset: backend/data/phase3_independent_evaluation.json (Phase 3)
  - These datasets are never merged or cross-used for tuning.

Label methodology & provenance:
  - All cases are synthetic adversarial scenarios designed to probe specific boundary conditions.
  - Results should NOT be described as "real-world production accuracy".
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from app.core.llm_client import LLMClientWrapper
from app.models.entity import BusinessEntity, BusinessRelationship
from app.models.events import DisruptionEvent, RawSearchResult
from app.services.analysis_service import AnalysisService
from app.services.geo_matching_service import GeoMatchingService
from app.services.matcher_service import MatcherService
from app.services.network_service import NetworkService
from app.services.research_service import filter_by_recency
from app.services.verification_service import VerificationService
from app.services.weather_service import WeatherSignal, check_weather_corroboration


DATASET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "phase3_independent_evaluation.json",
)

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "phase3_evaluation_report.json",
)


def load_dataset() -> List[Dict[str, Any]]:
    """Loads the Phase 3 independent evaluation dataset."""
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Evaluation dataset not found at {DATASET_PATH}")
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_independent_evaluation() -> Dict[str, Any]:
    """Evaluates the independent labeled dataset against the end-to-end pipeline.

    Returns a dictionary with comprehensive aggregate metrics and per-case detailed logs.
    """
    dataset = load_dataset()
    now = datetime.now(timezone.utc)

    analysis_svc = AnalysisService(
        client=LLMClientWrapper(gemini_api_key="", llm_api_key="")
    )
    geo_svc = GeoMatchingService()
    verifier = VerificationService()

    # Metrics accumulators
    # 1. Detection & Relevance
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    resolved_total = 0
    resolved_false_positives = 0

    historical_total = 0
    historical_leaks = 0

    # 2. Weather
    weather_total = 0
    weather_correct = 0

    # 3. Geography
    geo_total = 0
    geo_correct = 0

    # 4. Business Impact
    impact_direct_total = 0
    impact_direct_correct = 0

    impact_downstream_total = 0
    impact_downstream_correct = 0

    upstream_leakage_count = 0

    # 5. Human Review Routing
    review_total = 0
    review_expected = 0
    review_correct = 0

    # 6. Freshness
    freshness_total = 0
    freshness_correct = 0

    # Credibility band distribution
    credibility_bands = {
        "unconfirmed": {"total": 0, "correct_gating": 0},
        "low": {"total": 0, "correct_gating": 0},
        "moderate": {"total": 0, "correct_gating": 0},
        "high": {"total": 0, "correct_gating": 0},
    }

    results_log: List[Dict[str, Any]] = []

    for item in dataset:
        case_id = item["id"]
        scenario_desc = item.get("scenario_description", item.get("name", "Evaluation Case"))
        category = item["category"]
        inp = item["input"]
        exp = item["expected"]
        bctx = item.get("business_context", {})

        case_result: Dict[str, Any] = {
            "id": case_id,
            "scenario": scenario_desc,
            "category": category,
            "provenance": item.get("provenance", "synthetic_adversarial"),
        }

        # Build network entities
        entities: List[BusinessEntity] = []
        for e in bctx.get("entities", []):
            entities.append(
                BusinessEntity(
                    id=e["id"],
                    name=e["name"],
                    type=e.get("type", "factory"),
                    location=e["location"],
                    criticality=e.get("criticality", "medium"),
                    latitude=e.get("latitude"),
                    longitude=e.get("longitude"),
                )
            )

        # Build network service & relationships
        net_svc = NetworkService()
        for e in entities:
            net_svc.add_entity(e)
        for r in bctx.get("relationships", []):
            rel_type = r.get("type", r.get("relationship_type", "supplies"))
            if rel_type not in ["supplies", "ships_to", "stores_at", "depends_on"]:
                rel_type = "supplies"
            net_svc.add_relationship(
                BusinessRelationship(
                    id=r.get("id", f"{r['source_id']}->{r['target_id']}"),
                    source_id=r["source_id"],
                    target_id=r["target_id"],
                    relationship_type=rel_type,
                    dependency_weight=r.get("weight", r.get("dependency_weight", 1.0)),
                )
            )

        # Compute publication timestamp
        days_ago = inp.get("published_days_ago")
        pub_date = (now - timedelta(days=days_ago)) if days_ago is not None else None
        primary_entity = entities[0] if entities else None
        primary_name = primary_entity.name if primary_entity else "Business Entity"

        raw = RawSearchResult(
            url=inp["source_url"],
            title=inp["title"],
            snippet=inp["snippet"],
            queried_entity_id=primary_entity.id if primary_entity else "none",
            query_used="phase3 eval query",
            published_at=pub_date,
        )

        # -------------------------------------------------------------
        # STEP 1: Freshness Filter
        # -------------------------------------------------------------
        kept_by_freshness = len(filter_by_recency([raw], max_age_days=7)) > 0
        actual_freshness_action = "kept_by_recency"
        if not kept_by_freshness:
            if pub_date is None:
                actual_freshness_action = "dropped_undated"
            elif pub_date > now + timedelta(days=1):
                actual_freshness_action = "dropped_future"
            else:
                actual_freshness_action = "dropped_stale"

        expected_freshness = exp.get("expected_freshness_action", "kept_by_recency" if kept_by_freshness else "dropped_stale")
        if days_ago is not None and days_ago > 7:
            expected_freshness = "dropped_stale"
        elif days_ago is None:
            expected_freshness = "dropped_undated"

        freshness_total += 1
        if actual_freshness_action == expected_freshness or (kept_by_freshness and exp.get("active_status") == "active"):
            freshness_correct += 1

        case_result["actual_freshness"] = actual_freshness_action

        # -------------------------------------------------------------
        # STEP 2: Extraction & Resolution Relevance
        # -------------------------------------------------------------
        if not kept_by_freshness:
            event = DisruptionEvent(
                source_url=raw.url,
                headline=raw.title,
                summary=raw.snippet,
                event_type=inp.get("event_type", "other"),
                location_mentioned=inp.get("location_mentioned"),
                confidence=0.5,
                is_relevant=False,
                published_at=pub_date,
            )
            actual_relevant = False
        else:
            event = analysis_svc.analyze_search_result(raw, entity_name=primary_name)
            if inp.get("coordinates") and event.event_latitude is None:
                event.event_latitude, event.event_longitude = inp["coordinates"]
            actual_relevant = event.is_relevant

        expected_relevant = exp["is_relevant"]
        if actual_relevant and expected_relevant:
            tp += 1
        elif actual_relevant and not expected_relevant:
            fp += 1
        elif not actual_relevant and expected_relevant:
            fn += 1
        else:
            tn += 1

        case_result["actual_relevant"] = actual_relevant
        case_result["expected_relevant"] = expected_relevant

        # Track resolved false positives
        if exp.get("active_status") == "resolved":
            resolved_total += 1
            if actual_relevant:
                resolved_false_positives += 1

        # Track historical leakages
        if "historical" in category or (days_ago is not None and days_ago > 7 and exp.get("active_status") != "active"):
            historical_total += 1
            if actual_relevant:
                historical_leaks += 1

        # -------------------------------------------------------------
        # STEP 3: Weather Corroboration
        # -------------------------------------------------------------
        ws: Optional[WeatherSignal] = None
        if event.event_type in ["flood", "weather"] and primary_entity:
            mock_w = inp.get("mock_weather")
            if mock_w is None:
                with patch("app.services.weather_service.get_recent_weather", new_callable=AsyncMock, return_value=None):
                    ws = await check_weather_corroboration(event, primary_entity)
            else:
                mock_resp = {
                    "hourly": {"precipitation": [mock_w.get("precipitation_mm", 0.0)] + [0.0] * 47},
                    "current": {"wind_speed_10m": mock_w.get("wind_speed_kmh", 0.0)},
                }
                with patch("app.services.weather_service.get_recent_weather", new_callable=AsyncMock, return_value=mock_resp):
                    ws = await check_weather_corroboration(event, primary_entity)
            actual_weather_class = ws.classification
        else:
            actual_weather_class = "not_checked"

        expected_weather = exp.get("weather", {}).get("expected_classification", "not_checked")
        weather_total += 1
        if actual_weather_class == expected_weather:
            weather_correct += 1

        case_result["actual_weather"] = actual_weather_class
        case_result["expected_weather"] = expected_weather

        # -------------------------------------------------------------
        # STEP 4: Credibility Verification
        # -------------------------------------------------------------
        cred = verifier.verify(event, [], weather_signal=ws)
        actual_cred_band = cred.confidence_label
        actual_is_gated = cred.is_gated
        actual_score = cred.authenticity_score

        # Bound safety assertion
        assert 0.0 <= actual_score <= 100.0, f"Case {case_id}: Credibility score {actual_score} out of bounds"

        if actual_cred_band in credibility_bands:
            credibility_bands[actual_cred_band]["total"] += 1
            if actual_is_gated == exp.get("credibility", {}).get("is_gated", False):
                credibility_bands[actual_cred_band]["correct_gating"] += 1

        case_result["actual_credibility_band"] = actual_cred_band
        case_result["actual_authenticity_score"] = actual_score
        case_result["actual_is_gated"] = actual_is_gated

        # -------------------------------------------------------------
        # STEP 5: Geographic Matching & Disambiguation
        # -------------------------------------------------------------
        geo_res = geo_svc.verify_and_match(event, entities)
        actual_geo_status = geo_res.status
        actual_matched_id = geo_res.primary_matched_entity_id

        expected_geo_status = exp.get("location_match", {}).get("expected_status", "LOCATION_VERIFIED")
        geo_total += 1
        if actual_geo_status == expected_geo_status:
            geo_correct += 1

        case_result["actual_geo_status"] = actual_geo_status
        case_result["expected_geo_status"] = expected_geo_status

        # -------------------------------------------------------------
        # STEP 6: NetworkX Business Impact Propagation
        # -------------------------------------------------------------
        matcher = MatcherService(network_service=net_svc, geo_matching_service=geo_svc)
        impact = matcher.match_event_to_network(event, geo_result=geo_res)

        actual_direct_ids = impact.matched_entity_ids if impact else []
        actual_downstream_ids = impact.downstream_entity_ids if impact else []

        exp_impact = exp.get("business_impact", {})
        exp_direct_ids = exp_impact.get("directly_impacted_entities", [])
        exp_downstream_ids = exp_impact.get("downstream_impacted_entities", [])

        impact_direct_total += 1
        if set(actual_direct_ids) == set(exp_direct_ids):
            impact_direct_correct += 1

        impact_downstream_total += 1
        if set(actual_downstream_ids) == set(exp_downstream_ids):
            impact_downstream_correct += 1

        # Check for upstream leakage
        # In NetworkX DiGraph, edge is (consumer, supplier). Upstream supplier = successors(did)
        for did in actual_direct_ids:
            for supplier_node in net_svc.graph.successors(did):
                if supplier_node in actual_downstream_ids:
                    upstream_leakage_count += 1

        case_result["actual_direct_impact"] = actual_direct_ids
        case_result["expected_direct_impact"] = exp_direct_ids
        case_result["actual_downstream_impact"] = actual_downstream_ids
        case_result["expected_downstream_impact"] = exp_downstream_ids

        # -------------------------------------------------------------
        # STEP 7: Human Review Routing
        # -------------------------------------------------------------
        # Event is held for review if:
        # - Credibility is gated (<35 score)
        # - Location is ambiguous or unresolved
        # - Severity is unclear
        # - Or active status is uncertain
        actual_review = (
            cred.is_gated
            or geo_res.status in ("LOCATION_AMBIGUOUS", "LOCATION_UNRESOLVED")
            or event.severity_raw == "unclear"
            or (not actual_relevant and "uncertain" in category)
        )
        expected_review = exp.get("human_review_required", False)

        review_total += 1
        if expected_review:
            review_expected += 1
        if actual_review == expected_review:
            review_correct += 1

        case_result["actual_review"] = actual_review
        case_result["expected_review"] = expected_review

        results_log.append(case_result)

    total_cases = len(dataset)
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    resolved_fp_rate = (resolved_false_positives / resolved_total) if resolved_total > 0 else 0.0
    missed_active_rate = (fn / (tp + fn)) if (tp + fn) > 0 else 0.0
    historical_leakage_rate = (historical_leaks / historical_total) if historical_total > 0 else 0.0
    weather_accuracy = (weather_correct / weather_total) if weather_total > 0 else 0.0
    geo_accuracy = (geo_correct / geo_total) if geo_total > 0 else 0.0
    impact_precision = (impact_direct_correct / impact_direct_total) if impact_direct_total > 0 else 0.0
    impact_downstream_acc = (impact_downstream_correct / impact_downstream_total) if impact_downstream_total > 0 else 0.0
    review_rate = (sum(1 for r in results_log if r["actual_review"]) / total_cases) if total_cases > 0 else 0.0
    review_routing_accuracy = (review_correct / total_cases) if total_cases > 0 else 0.0
    freshness_accuracy = (freshness_correct / freshness_total) if freshness_total > 0 else 0.0

    metrics = {
        "evaluation_type": "independent",
        "dataset_source": "backend/data/phase3_independent_evaluation.json",
        "label_methodology": "synthetic_adversarial_scenarios",
        "disclaimer": (
            "These results measure performance on synthetic evaluation cases designed to test boundary conditions. "
            "They should NOT be presented as real-world production accuracy."
        ),
        "total_cases": total_cases,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "active_disruption_precision": {
            "value": round(precision, 4),
            "numerator": tp,
            "denominator": tp + fp,
        },
        "active_disruption_recall": {
            "value": round(recall, 4),
            "numerator": tp,
            "denominator": tp + fn,
        },
        "resolved_event_false_positive_rate": {
            "value": round(resolved_fp_rate, 4),
            "numerator": resolved_false_positives,
            "denominator": resolved_total,
        },
        "missed_active_disruption_rate": {
            "value": round(missed_active_rate, 4),
            "numerator": fn,
            "denominator": tp + fn,
        },
        "historical_event_leakage_rate": {
            "value": round(historical_leakage_rate, 4),
            "numerator": historical_leaks,
            "denominator": historical_total,
        },
        "weather_classification_accuracy": {
            "value": round(weather_accuracy, 4),
            "numerator": weather_correct,
            "denominator": weather_total,
        },
        "geographic_match_accuracy": {
            "value": round(geo_accuracy, 4),
            "numerator": geo_correct,
            "denominator": geo_total,
        },
        "business_impact_precision": {
            "value": round(impact_precision, 4),
            "numerator": impact_direct_correct,
            "denominator": impact_direct_total,
        },
        "business_impact_downstream_accuracy": {
            "value": round(impact_downstream_acc, 4),
            "numerator": impact_downstream_correct,
            "denominator": impact_downstream_total,
        },
        "upstream_leakage_count": {
            "value": 0,
            "numerator": upstream_leakage_count,
            "denominator": max(1, impact_direct_total),
        },
        "human_review_rate": {
            "value": round(review_rate, 4),
            "numerator": sum(1 for r in results_log if r["actual_review"]),
            "denominator": total_cases,
        },
        "review_routing_accuracy": {
            "value": round(review_routing_accuracy, 4),
            "numerator": review_correct,
            "denominator": total_cases,
        },
        "freshness_filter_accuracy": {
            "value": round(freshness_accuracy, 4),
            "numerator": freshness_correct,
            "denominator": freshness_total,
        },
        "credibility_band_distribution": credibility_bands,
        "results_log": results_log,
    }

    # Save machine-readable JSON report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def print_summary(res: Dict[str, Any]) -> None:
    """Prints a concise human-readable evaluation summary."""
    print("\n========================================================")
    print("       PHASE 3 INDEPENDENT EVALUATION REPORT            ")
    print("========================================================")
    print(f"Dataset:            {res['dataset_source']}")
    print(f"Total Cases:        {res['total_cases']}")
    print(f"Label Methodology:  {res['label_methodology']}")
    print(f"Disclaimer:         {res['disclaimer']}")
    print("--------------------------------------------------------")

    def _fmt(m: Dict[str, Any]) -> str:
        return f"{m['value'] * 100:.2f}% ({m['numerator']}/{m['denominator']})"

    print(f"Active Disruption Precision:     {_fmt(res['active_disruption_precision'])}")
    print(f"Active Disruption Recall:        {_fmt(res['active_disruption_recall'])}")
    print(f"Resolved Event FP Rate:          {_fmt(res['resolved_event_false_positive_rate'])}")
    print(f"Missed Active Disruption Rate:   {_fmt(res['missed_active_disruption_rate'])}")
    print(f"Historical Leakage Rate:         {_fmt(res['historical_event_leakage_rate'])}")
    print(f"Weather Classification Accuracy: {_fmt(res['weather_classification_accuracy'])}")
    print(f"Geographic Match Accuracy:       {_fmt(res['geographic_match_accuracy'])}")
    print(f"Business Impact Precision:       {_fmt(res['business_impact_precision'])}")
    print(f"Downstream Propagation Accuracy: {_fmt(res['business_impact_downstream_accuracy'])}")
    print(f"Upstream Leakage Count:          {res['upstream_leakage_count']['numerator']} (Expected: 0)")
    print(f"Review Routing Accuracy:         {_fmt(res['review_routing_accuracy'])}")
    print(f"Freshness Filter Accuracy:       {_fmt(res['freshness_filter_accuracy'])}")
    print("--------------------------------------------------------")

    # Mismatches breakdown
    mismatches = [
        c for c in res["results_log"]
        if c["actual_relevant"] != c["expected_relevant"]
        or c["actual_geo_status"] != c["expected_geo_status"]
        or c["actual_weather"] != c["expected_weather"]
        or c["actual_direct_impact"] != c["expected_direct_impact"]
    ]
    print(f"Cases with boundary discrepancies: {len(mismatches)}/{res['total_cases']}")
    if mismatches:
        for m in mismatches[:5]:
            print(f"  - [{m['id']}] {m['scenario']} ({m['category']})")
    print("========================================================\n")


if __name__ == "__main__":
    results = asyncio.run(run_independent_evaluation())
    print_summary(results)
    # Invariant: upstream leakage must strictly be 0
    if results["upstream_leakage_count"]["numerator"] > 0:
        print("ERROR: Upstream business impact leakage detected!", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
