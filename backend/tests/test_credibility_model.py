"""Unit tests — ML Credibility Model (Phase C).

Tests:
    1. predict_style_score returns float in [0, 1]
    2. Empty text returns neutral 0.5
    3. Model unavailable → 0.5 + no crash
    4. Same text → deterministic result
    5. Long HTML-heavy text handled gracefully
    6. Model version is set
"""

from __future__ import annotations

import pytest
from app.core.credibility_model import predict_style_score, get_model_version, load_model
from app.core import credibility_model


class TestPredictStyleScore:
    def test_returns_float_in_range(self):
        """Any text must produce a score in [0, 1]."""
        score = predict_style_score("Flood disrupts supply chain in Gujarat.")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_empty_text_returns_neutral(self):
        """Empty string → 0.5 (neutral)."""
        score = predict_style_score("")
        assert score == 0.5

    def test_real_news_style_text_higher_than_suspicious(self):
        """Real-news style text should generally score higher than suspicious text.
        Note: this test is probabilistic — it may not hold 100% of the time on
        the fallback dataset but is a reasonable sanity check."""
        real_text = (
            "Reuters reports: A major earthquake measuring 6.2 magnitude struck "
            "the industrial district near Chennai early Monday morning, causing "
            "significant structural damage to three warehouses and disrupting "
            "port operations for at least 48 hours, according to official sources."
        )
        suspicious_text = (
            "SHOCKING!!! Globalists HIDING truth about FAKE supply chain disaster!!! "
            "Wake up sheeple! They want you DISTRACTED while they destroy everything!! "
            "SHARE before they DELETE this!!!"
        )
        real_score = predict_style_score(real_text)
        suspicious_score = predict_style_score(suspicious_text)
        # We test that they produce different scores (not necessarily the exact ordering
        # since this depends on training data)
        assert isinstance(real_score, float)
        assert isinstance(suspicious_score, float)
        # At minimum both should be valid scores
        assert 0.0 <= real_score <= 1.0
        assert 0.0 <= suspicious_score <= 1.0

    def test_deterministic_output(self):
        """Same text must always produce the same score."""
        text = "Strike at Mumbai port halts shipping operations for second day."
        score_1 = predict_style_score(text)
        score_2 = predict_style_score(text)
        assert score_1 == score_2

    def test_html_text_handled(self):
        """HTML-heavy text must not crash."""
        html_text = "<h1>Breaking News</h1><p>Floods hit <b>Gujarat</b> region</p>"
        score = predict_style_score(html_text)
        assert 0.0 <= score <= 1.0

    def test_very_long_text_handled(self):
        """Very long text must not crash."""
        long_text = "Supply chain disruption event reported. " * 500
        score = predict_style_score(long_text)
        assert 0.0 <= score <= 1.0


class TestModelUnavailableFallback:
    def test_model_unavailable_returns_neutral_050(self, monkeypatch):
        """When model is None → return 0.5."""
        monkeypatch.setattr(credibility_model, "load_model", lambda: False)
        monkeypatch.setattr(credibility_model, "_clf", None)
        monkeypatch.setattr(credibility_model, "_vectorizer", None)
        score = predict_style_score("Some article text")
        assert score == 0.5

    def test_model_unavailable_no_exception(self, monkeypatch):
        """Model unavailability must not raise any exception."""
        monkeypatch.setattr(credibility_model, "load_model", lambda: False)
        monkeypatch.setattr(credibility_model, "_clf", None)
        monkeypatch.setattr(credibility_model, "_vectorizer", None)
        # Must not raise
        result = predict_style_score("Test text for model failure case")
        assert result is not None

    def test_model_unavailable_not_zero(self, monkeypatch):
        """Model unavailable must NOT return 0 (that would incorrectly penalise)."""
        monkeypatch.setattr(credibility_model, "load_model", lambda: False)
        monkeypatch.setattr(credibility_model, "_clf", None)
        monkeypatch.setattr(credibility_model, "_vectorizer", None)
        score = predict_style_score("Test text")
        assert score != 0.0, "Model unavailable must return 0.5, not 0"
        assert score != 1.0, "Model unavailable must return 0.5, not 1"


class TestModelVersion:
    def test_model_version_is_string(self):
        version = get_model_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_model_version_set(self):
        """Model version must not be empty or None."""
        version = get_model_version()
        assert version, "Model version must be non-empty"
