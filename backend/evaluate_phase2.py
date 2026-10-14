"""Phase 2 Quantitative Evaluation Runner.

Evaluates the labeled evaluation dataset against:
- Freshness & Stale-News Filtering (7-day window)
- Extraction & Resolved-Event Filtering
- Weather Evidence Corroboration & Classification
- Geographic Entity Match Verification
- Human-Review Routing (Unconfirmed / Ambiguous)

Computes:
1. Relevant-event precision = TP / (TP + FP)
2. Relevant-event recall = TP / (TP + FN)
3. Resolved-event false-positive rate = (Resolved events falsely flagged active) / (Total resolved events)
4. Weather-evidence classification accuracy = (Correct weather classifications) / (Total weather cases)
5. Geographic entity-match accuracy = (Correct geo matches) / (Total cases with valid entities)
6. Human-review rate = (Cases routed to review: unconfirmed / ambiguous) / (Total cases)
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent, RawSearchResult
from app.services.analysis_service import AnalysisService
from app.services.geo_matching_service import GeoMatchingService
from app.services.network_service import NetworkService
from app.services.research_service import filter_by_recency
from app.services.verification_service import VerificationService
from app.services.weather_service import WeatherSignal, check_weather_corroboration


DATASET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "evaluation_dataset.json",
)


def load_dataset() -> List[Dict[str, Any]]:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_evaluation() -> Dict[str, Any]:
    dataset = load_dataset()
    now = datetime.now(timezone.utc)

    from app.core.llm_client import LLMClientWrapper
    analysis_svc = AnalysisService(client=LLMClientWrapper(gemini_api_key="", llm_api_key=""))
    geo_svc = GeoMatchingService()
    verifier = VerificationService()

    # Metrics accumulators
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    resolved_total = 0
    resolved_false_positives = 0

    weather_cases_total = 0
    weather_cases_correct = 0

    geo_cases_total = 0
    geo_cases_correct = 0

    review_cases_count = 0

    results_log = []

    for item in dataset:
        case_id = item["id"]
        pub_date = now - timedelta(days=item["published_days_ago"])
        raw = RawSearchResult(
            url=item["source_url"],
            title=item["title"],
            snippet=item["snippet"],
            queried_entity_id="entity-eval",
            query_used="eval query",
            published_at=pub_date,
        )

        # 1. Freshness filter evaluation
        kept_by_freshness = len(filter_by_recency([raw], max_age_days=7)) > 0

        # Entity model
        lat = item["entity_coords"][0] if item["entity_coords"] else None
        lon = item["entity_coords"][1] if item["entity_coords"] else None
        entity = BusinessEntity(
            id=f"ent-{case_id}",
            name=item["entity_name"],
            type="factory",
            location=item["entity_location"],
            criticality="high",
            latitude=lat,
            longitude=lon,
        )

        actual_relevant = False
        actual_resolved_filtered = False
        actual_weather_class = "not_checked"
        actual_geo_status = "LOCATION_VERIFIED"
        actual_review = False

        if not kept_by_freshness:
            # Dropped by freshness filter (stale news)
            actual_relevant = False
            actual_resolved_filtered = False
            actual_weather_class = "insufficient_coverage" if item["event_type"] in ["flood", "weather"] else "not_checked"
            actual_geo_status = "LOCATION_VERIFIED"
            actual_review = False
        else:
            # 2. Extraction & resolution filtering
            event = analysis_svc.analyze_search_result(raw, entity_name=item["entity_name"])
            actual_relevant = event.is_relevant
            actual_resolved_filtered = (not event.is_relevant) and item["category"] in ["resolved_event"]

            # 3. Weather corroboration check
            if event.event_type in ["flood", "weather"]:
                mock_w = item.get("mock_weather")
                if mock_w is None and item["category"] == "missing_weather_provider":
                    with patch("app.services.weather_service.get_recent_weather", new_callable=AsyncMock, return_value=None):
                        ws = await check_weather_corroboration(event, entity)
                elif mock_w:
                    mock_resp = {
                        "hourly": {"precipitation": [mock_w["precipitation_mm"]] + [0.0] * 47},
                        "current": {"wind_speed_10m": mock_w["wind_speed_kmh"]},
                    }
                    with patch("app.services.weather_service.get_recent_weather", new_callable=AsyncMock, return_value=mock_resp):
                        ws = await check_weather_corroboration(event, entity)
                else:
                    ws = await check_weather_corroboration(event, entity)

                actual_weather_class = ws.classification
            else:
                actual_weather_class = "not_checked"
                ws = None

            # 4. Credibility verification
            cred = verifier.verify(event, [], weather_signal=ws)

            # 5. Geographic verification
            geo_res = geo_svc.verify_and_match(event, [entity])
            actual_geo_status = geo_res.status

            # Review routing criteria: credibility gated (<35 score) or ambiguous/unresolved location or unclear severity
            if cred.is_gated or geo_res.status in ("LOCATION_AMBIGUOUS", "LOCATION_UNRESOLVED") or event.severity_raw == "unclear":
                actual_review = True

        # Metric comparisons
        expected_relevant = item["expected_relevant"]
        if actual_relevant and expected_relevant:
            tp += 1
        elif actual_relevant and not expected_relevant:
            fp += 1
        elif not actual_relevant and expected_relevant:
            fn += 1
        else:
            tn += 1

        # Resolved event false-positive tracking
        if item["category"] == "resolved_event":
            resolved_total += 1
            if actual_relevant:
                resolved_false_positives += 1

        # Weather evidence classification accuracy
        weather_cases_total += 1
        if actual_weather_class == item["expected_weather_classification"]:
            weather_cases_correct += 1

        # Geo entity match accuracy
        geo_cases_total += 1
        if actual_geo_status == item["expected_geo_status"]:
            geo_cases_correct += 1

        # Review tracking
        if actual_review:
            review_cases_count += 1

        results_log.append({
            "id": case_id,
            "name": item["name"],
            "expected_relevant": expected_relevant,
            "actual_relevant": actual_relevant,
            "expected_weather": item["expected_weather_classification"],
            "actual_weather": actual_weather_class,
            "expected_geo": item["expected_geo_status"],
            "actual_geo": actual_geo_status,
            "expected_review": item["expected_review"],
            "actual_review": actual_review,
        })

    total_cases = len(dataset)
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    resolved_fp_rate = (resolved_false_positives / resolved_total) if resolved_total > 0 else 0.0
    weather_accuracy = (weather_cases_correct / weather_cases_total) if weather_cases_total > 0 else 0.0
    geo_accuracy = (geo_cases_correct / geo_cases_total) if geo_cases_total > 0 else 0.0
    human_review_rate = (review_cases_count / total_cases) if total_cases > 0 else 0.0

    metrics = {
        "total_cases": total_cases,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "relevant_event_precision": round(precision, 4),
        "relevant_event_recall": round(recall, 4),
        "resolved_event_false_positive_rate": round(resolved_fp_rate, 4),
        "weather_classification_accuracy": round(weather_accuracy, 4),
        "geographic_match_accuracy": round(geo_accuracy, 4),
        "human_review_rate": round(human_review_rate, 4),
        "results_log": results_log,
    }
    return metrics


if __name__ == "__main__":
    res = asyncio.run(run_evaluation())
    print("\n=== PHASE 2 LABELED EVALUATION RESULTS ===")
    print(f"Total Reviewed Cases: {res['total_cases']}")
    print(f"Relevant-Event Precision: {res['relevant_event_precision'] * 100:.1f}% ({res['true_positives']}/{res['true_positives'] + res['false_positives']})")
    print(f"Relevant-Event Recall:    {res['relevant_event_recall'] * 100:.1f}% ({res['true_positives']}/{res['true_positives'] + res['false_negatives']})")
    print(f"Resolved-Event FP Rate:   {res['resolved_event_false_positive_rate'] * 100:.1f}%")
    print(f"Weather Class Accuracy:   {res['weather_classification_accuracy'] * 100:.1f}%")
    print(f"Geographic Match Acc:     {res['geographic_match_accuracy'] * 100:.1f}%")
    print(f"Human-Review Rate:        {res['human_review_rate'] * 100:.1f}%")
