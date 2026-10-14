"""Domain Reputation Lookup — Phase A of Credibility Verification Engine.

Maintains a human-editable reputation table keyed by domain name.
This module uses NO machine learning. It is a transparent, auditable lookup.

Design notes:
- Unknown domain returns neutral 0.5 ("unverified") — NOT 0 (not fake).
- Domain normalisation strips scheme, www-prefix, and path components.
- The table can be extended without code changes by editing DOMAIN_REPUTATION_TABLE.
"""

from urllib.parse import urlparse
import logging

logger = logging.getLogger("business_disruption")

# ---------------------------------------------------------------------------
# Human-editable reputation table
# Tier vocabulary:
#   wire_service      — major international wire agencies (highest trust)
#   established_news  — well-known broadcasters / national newspapers
#   regional_news     — local / regional outlets with reasonable track record
#   trade_press       — industry-specific specialist publications
#   unverified        — unknown or insufficient information
#   satire            — known satire / parody sites
#   known_unreliable  — documented history of misinformation
# ---------------------------------------------------------------------------
DOMAIN_REPUTATION_TABLE: dict[str, dict] = {
    # Wire services
    "reuters.com": {"tier": "wire_service", "reputation_score": 0.95},
    "apnews.com": {"tier": "wire_service", "reputation_score": 0.95},
    "afp.com": {"tier": "wire_service", "reputation_score": 0.93},
    "bloomberg.com": {"tier": "wire_service", "reputation_score": 0.92},
    # Established international news
    "bbc.com": {"tier": "established_news", "reputation_score": 0.90},
    "bbc.co.uk": {"tier": "established_news", "reputation_score": 0.90},
    "theguardian.com": {"tier": "established_news", "reputation_score": 0.88},
    "nytimes.com": {"tier": "established_news", "reputation_score": 0.88},
    "washingtonpost.com": {"tier": "established_news", "reputation_score": 0.87},
    "ft.com": {"tier": "established_news", "reputation_score": 0.90},
    "economist.com": {"tier": "established_news", "reputation_score": 0.89},
    "wsj.com": {"tier": "established_news", "reputation_score": 0.88},
    "aljazeera.com": {"tier": "established_news", "reputation_score": 0.83},
    "dw.com": {"tier": "established_news", "reputation_score": 0.85},
    "france24.com": {"tier": "established_news", "reputation_score": 0.84},
    "cnn.com": {"tier": "established_news", "reputation_score": 0.80},
    "nbcnews.com": {"tier": "established_news", "reputation_score": 0.80},
    "abcnews.go.com": {"tier": "established_news", "reputation_score": 0.80},
    "cbsnews.com": {"tier": "established_news", "reputation_score": 0.80},
    "sky.com": {"tier": "established_news", "reputation_score": 0.82},
    "ndtv.com": {"tier": "established_news", "reputation_score": 0.80},
    "thehindu.com": {"tier": "established_news", "reputation_score": 0.82},
    "hindustantimes.com": {"tier": "established_news", "reputation_score": 0.78},
    "timesofindia.com": {"tier": "established_news", "reputation_score": 0.78},
    "economictimes.indiatimes.com": {"tier": "established_news", "reputation_score": 0.80},
    "livemint.com": {"tier": "established_news", "reputation_score": 0.80},
    "business-standard.com": {"tier": "established_news", "reputation_score": 0.79},
    # Regional / Local news
    "localchannel7.com": {"tier": "regional_news", "reputation_score": 0.72},
    "surat-mirror.com": {"tier": "regional_news", "reputation_score": 0.68},
    "mumbaimirror.com": {"tier": "regional_news", "reputation_score": 0.72},
    # Trade press / Industry specific
    "supplychainbrain.com": {"tier": "trade_press", "reputation_score": 0.78},
    "logisticsmgmt.com": {"tier": "trade_press", "reputation_score": 0.77},
    "freightwaves.com": {"tier": "trade_press", "reputation_score": 0.78},
    "joc.com": {"tier": "trade_press", "reputation_score": 0.76},
    # Known satire (explicit low score)
    "theonion.com": {"tier": "satire", "reputation_score": 0.05},
    "babylonbee.com": {"tier": "satire", "reputation_score": 0.05},
    "waterfordwhispersnews.com": {"tier": "satire", "reputation_score": 0.05},
    # Known unreliable
    "infowars.com": {"tier": "known_unreliable", "reputation_score": 0.05},
    "naturalnews.com": {"tier": "known_unreliable", "reputation_score": 0.08},
    "beforeitsnews.com": {"tier": "known_unreliable", "reputation_score": 0.08},
}

# Neutral score for completely unknown domains.
# Unknown ≠ fake. Unknown = insufficient information.
UNKNOWN_DOMAIN_SCORE: float = 0.5
UNKNOWN_DOMAIN_TIER: str = "unverified"


def _normalise_domain(raw: str) -> str:
    """Extract bare domain from a URL, hostname, or bare domain string.

    Examples
    --------
    >>> _normalise_domain("https://www.reuters.com/business/article-123")
    'reuters.com'
    >>> _normalise_domain("www.bbc.co.uk")
    'bbc.co.uk'
    >>> _normalise_domain("reuters.com")
    'reuters.com'
    """
    if not raw or not isinstance(raw, str):
        return ""

    raw = raw.strip().lower()

    # If there's a scheme, parse as URL
    if "://" in raw:
        try:
            parsed = urlparse(raw)
            host = parsed.hostname or ""
        except Exception:
            host = ""
    else:
        # Treat as hostname (possibly with path)
        host = raw.split("/")[0]

    # Strip leading 'www.' for normalisation
    if host.startswith("www."):
        host = host[4:]

    return host


def lookup_domain(domain: str) -> tuple[float, str]:
    """Look up a domain's reputation score and tier.

    Parameters
    ----------
    domain:
        A bare domain name, URL, or any string that contains a recognisable
        domain component.  Empty, None, or malformed inputs are handled safely.

    Returns
    -------
    (reputation_score, tier) where reputation_score is in [0.0, 1.0].

    Behaviour
    ---------
    - Known domain  → configured score and tier from DOMAIN_REPUTATION_TABLE.
    - Unknown domain → (0.5, "unverified").  Unknown ≠ fake.
    - Empty / malformed → (0.5, "unverified") — never raises, never returns 0.

    Notes
    -----
    The function also accepts full URLs (e.g. ``https://www.reuters.com/article``)
    and will normalise them before lookup.
    """
    normalised = _normalise_domain(domain)

    if not normalised:
        logger.debug("[DOMAIN_REP] Empty/malformed domain → neutral 0.5 (unverified)")
        return UNKNOWN_DOMAIN_SCORE, UNKNOWN_DOMAIN_TIER

    entry = DOMAIN_REPUTATION_TABLE.get(normalised)
    if entry:
        score = entry["reputation_score"]
        tier = entry["tier"]
        logger.debug(f"[DOMAIN_REP] {normalised} → {score} ({tier})")
        return score, tier

    logger.debug(f"[DOMAIN_REP] Unknown domain '{normalised}' → neutral 0.5 (unverified)")
    return UNKNOWN_DOMAIN_SCORE, UNKNOWN_DOMAIN_TIER
