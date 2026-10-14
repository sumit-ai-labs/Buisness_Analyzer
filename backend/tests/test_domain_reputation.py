"""Unit tests — Phase A: Domain Reputation Lookup.

Tests:
    1. Known wire-service domain
    2. Known satire domain
    3. Unknown domain → 0.5 neutral (not 0)
    4. Empty string → 0.5 neutral, no crash
    5. Malformed / non-domain input → 0.5 neutral, no crash
    6. Full URL input → normalised correctly
    7. www-prefixed domain → same result as bare domain
    8. Known low-reputation domain
"""

import pytest
from app.core.domain_reputation import lookup_domain, UNKNOWN_DOMAIN_SCORE, UNKNOWN_DOMAIN_TIER


class TestKnownDomains:
    def test_wire_service_reuters(self):
        score, tier = lookup_domain("reuters.com")
        assert score >= 0.90
        assert tier == "wire_service"

    def test_wire_service_apnews(self):
        score, tier = lookup_domain("apnews.com")
        assert score >= 0.90
        assert tier == "wire_service"

    def test_established_bbc(self):
        score, tier = lookup_domain("bbc.com")
        assert score >= 0.85
        assert tier == "established_news"

    def test_known_satire_theonion(self):
        score, tier = lookup_domain("theonion.com")
        assert score < 0.20
        assert tier == "satire"

    def test_known_unreliable(self):
        score, tier = lookup_domain("infowars.com")
        assert score < 0.20
        assert tier == "known_unreliable"


class TestUnknownDomains:
    def test_unknown_domain_returns_neutral_score(self):
        """Unknown domain MUST return 0.5, never 0."""
        score, tier = lookup_domain("some-random-unregistered-domain-xyz123.com")
        assert score == UNKNOWN_DOMAIN_SCORE, "Unknown domain must return neutral 0.5, not 0"
        assert tier == UNKNOWN_DOMAIN_TIER

    def test_unknown_domain_is_not_zero(self):
        """Unknown ≠ fake. Score must be 0.5, not 0."""
        score, _ = lookup_domain("totally-unknown-site-abc987.org")
        assert score != 0.0, "Unknown domain must NOT return 0 — unknown ≠ fake"

    def test_unknown_domain_is_not_one(self):
        """Unknown domain must not be treated as fully trusted either."""
        score, _ = lookup_domain("totally-unknown-site-abc987.org")
        assert score != 1.0


class TestEdgeCases:
    def test_empty_string_does_not_crash(self):
        score, tier = lookup_domain("")
        assert score == UNKNOWN_DOMAIN_SCORE
        assert tier == UNKNOWN_DOMAIN_TIER

    def test_none_like_empty_does_not_crash(self):
        score, tier = lookup_domain("   ")
        assert score == UNKNOWN_DOMAIN_SCORE

    def test_malformed_url_does_not_crash(self):
        score, tier = lookup_domain("not://a valid::url!!!###")
        assert 0.0 <= score <= 1.0  # must not crash; must return valid float

    def test_full_url_normalised(self):
        """Full URL should produce the same result as a bare domain."""
        score_url, tier_url = lookup_domain("https://www.reuters.com/business/some-article")
        score_bare, tier_bare = lookup_domain("reuters.com")
        assert score_url == score_bare
        assert tier_url == tier_bare

    def test_www_prefix_stripped(self):
        """www.reuters.com and reuters.com must return the same entry."""
        score_www, _ = lookup_domain("www.reuters.com")
        score_bare, _ = lookup_domain("reuters.com")
        assert score_www == score_bare

    def test_score_is_always_in_range(self):
        """Every lookup must return a score in [0, 1]."""
        domains = [
            "reuters.com",
            "theonion.com",
            "unknown-xyz.com",
            "",
            "https://www.bbc.com/news/article-123",
        ]
        for d in domains:
            score, _ = lookup_domain(d)
            assert 0.0 <= score <= 1.0, f"Score out of range for '{d}': {score}"
