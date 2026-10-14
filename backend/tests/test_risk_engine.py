import pytest
from app.core.dynamic_config import DynamicConfigStore, SystemConfig, RiskThresholdsConfig
from app.models.entity import BusinessEntity, EntityMetadata
from app.models.events import DisruptionEvent
from app.services.risk_service import RiskService


@pytest.fixture
def temp_config_store(tmp_path):
    config_file = tmp_path / "config.json"
    return DynamicConfigStore(file_path=str(config_file))


def test_risk_engine_critical_worked_example(temp_config_store):
    service = RiskService(config_store=temp_config_store)

    entity = BusinessEntity(
        id="ent-critical",
        name="Key Lithium Mine",
        type="supplier",
        location="Atacama, Chile",
        criticality="high",  # 100
        metadata=EntityMetadata(
            lead_time_days=60,  # 100
            alternative_supplier_available=False,  # 100
        ),
    )

    event = DisruptionEvent(
        source_url="https://example.com/strike",
        source_result_id="res-1",
        headline="Mine strike halts production completely",
        summary="Labor union strike shuts down mining operations.",
        event_type="strike",
        location_mentioned="Atacama, Chile",
        severity_raw="high",
        confidence=1.0,  # 100
        is_relevant=True,
    )

    assessment = service.evaluate_risk(entity=entity, event=event, dependency_weight=1.0)
    assert assessment.severity_score == 100.0
    assert assessment.risk_level == "critical"
    assert assessment.factors["single_source_vulnerability"] == 100.0


def test_risk_engine_low_vulnerability_example(temp_config_store):
    service = RiskService(config_store=temp_config_store)

    entity = BusinessEntity(
        id="ent-low",
        name="Packaging Supplier",
        type="supplier",
        location="Berlin, Germany",
        criticality="low",  # 25
        metadata=EntityMetadata(
            lead_time_days=0,  # 0
            alternative_supplier_available=True,  # 0
        ),
    )

    event = DisruptionEvent(
        source_url="https://example.com/minor",
        source_result_id="res-2",
        headline="Minor weather delay",
        summary="Slight delay due to rain.",
        event_type="weather",
        location_mentioned="Berlin",
        severity_raw="low",
        confidence=0.5,  # 50
        is_relevant=True,
    )

    assessment = service.evaluate_risk(entity=entity, event=event, dependency_weight=0.1)
    # (0.30*10) + (0.25*25) + (0.20*0) + (0.15*0) + (0.10*50) = 3 + 6.25 + 0 + 0 + 5 = 14.25
    assert assessment.severity_score == 14.25
    assert assessment.risk_level == "low"


def test_risk_engine_dynamic_threshold_customization(temp_config_store):
    service = RiskService(config_store=temp_config_store)

    # Lower high threshold to 10.0
    new_cfg = SystemConfig(thresholds=RiskThresholdsConfig(low=5.0, medium=8.0, high=10.0))
    temp_config_store.save_config(new_cfg)

    entity = BusinessEntity(
        id="ent-low",
        name="Packaging Supplier",
        type="supplier",
        location="Berlin, Germany",
        criticality="low",
        metadata=EntityMetadata(lead_time_days=0, alternative_supplier_available=True),
    )

    event = DisruptionEvent(
        source_url="https://example.com/minor",
        source_result_id="res-2",
        headline="Minor weather delay",
        summary="Slight delay due to rain.",
        event_type="weather",
        location_mentioned="Berlin",
        severity_raw="low",
        confidence=0.5,
        is_relevant=True,
    )

    assessment = service.evaluate_risk(entity=entity, event=event, dependency_weight=0.1)
    # Score is 14.25, which is > new high threshold of 10.0 -> critical!
    assert assessment.risk_level == "critical"
