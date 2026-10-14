"""Cross-Source Corroboration Service — Phase B of Credibility Verification Engine.

Counts independent sources that appear to report the same disruption event.

Design notes / MVP limitations:
- "Independence" is approximated by different source domains. In production this
  should be extended to detect syndicated content (e.g. same wire copy republished
  on many sites), but that requires fingerprinting beyond today's scope.
- Location matching uses normalised token overlap — not geographic NLP. A future
  iteration should resolve place-name aliases and administrative boundaries.
- Time windowing defaults to 48 hours to accommodate both breaking news and
  slower regional reporting cycles.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from app.models.events import DisruptionEvent

logger = logging.getLogger("business_disruption")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    """Extract bare domain from a URL for domain-comparison purposes."""
    from urllib.parse import urlparse
    if not url:
        return ""
    url = url.strip().lower()
    if "://" in url:
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            host = ""
    else:
        host = url.split("/")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalise_location(location: str) -> str:
    """Lowercase and strip a location string for comparison."""
    if not location:
        return ""
    return location.strip().lower()


def _locations_overlap(loc_a: str, loc_b: str) -> bool:
    """Return True if two location strings share at least one meaningful token.

    Approach:
    1. Exact (normalised) match.
    2. Substring containment in either direction.
    3. Token set intersection — any shared token of ≥3 chars counts.

    This is an MVP approximation. It intentionally errs slightly toward
    finding overlap rather than missing genuine corroboration.
    """
    a = _normalise_location(loc_a)
    b = _normalise_location(loc_b)

    if not a or not b:
        return False

    # Exact match
    if a == b:
        return True

    # Substring containment
    if a in b or b in a:
        return True

    # Token overlap (words ≥ 3 chars)
    tokens_a = {t for t in a.replace(",", " ").split() if len(t) >= 3}
    tokens_b = {t for t in b.replace(",", " ").split() if len(t) >= 3}
    return bool(tokens_a & tokens_b)


def _get_event_time(event: DisruptionEvent) -> datetime | None:
    """Return the most appropriate timestamp for windowing purposes.

    Prefers ``published_at`` (actual article publication date) over
    ``retrieved_at`` because two articles retrieved on the same day could
    be reporting events weeks apart.
    """
    ts = getattr(event, "published_at", None) or getattr(event, "retrieved_at", None) or getattr(event, "analyzed_at", None)
    if ts is None:
        return None
    # Ensure timezone-aware
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_corroborating_sources(
    event: DisruptionEvent,
    recent_events: list[DisruptionEvent],
    time_window_hours: int = 48,
) -> int:
    """Count independent sources that corroborate *event* within the time window.

    An event in ``recent_events`` qualifies as a corroborating source when ALL
    of the following hold:

    1. It is not the *same* object (different ``id``).
    2. It comes from a **different** source domain (domain independence proxy).
    3. Its ``event_type`` matches *event*'s ``event_type``.
    4. Its ``location_mentioned`` overlaps with *event*'s ``location_mentioned``.
    5. Its timestamp falls within ``time_window_hours`` of *event*'s timestamp.

    Parameters
    ----------
    event:
        The target DisruptionEvent to corroborate.
    recent_events:
        Collection of other events to check for corroboration.
    time_window_hours:
        Maximum age difference (in hours) between events to count as
        corroborating.  Default 48 h.  Pass 0 to disable time filtering.

    Returns
    -------
    int — number of unique corroborating domains.

    Safety
    ------
    Missing location, timestamp, or domain on *either* event never crashes this
    function; the candidate is simply not counted.
    """
    if not recent_events:
        return 0

    target_domain = _extract_domain(event.source_url)
    target_type = event.event_type
    target_location = _normalise_location(event.location_mentioned)
    target_time = _get_event_time(event)

    window = timedelta(hours=time_window_hours) if time_window_hours > 0 else None

    seen_corroborating_domains: set[str] = set()

    for candidate in recent_events:
        # Rule 1: Must be a different event
        if candidate.id == event.id:
            continue

        # Rule 2: Must be a different domain
        cand_domain = _extract_domain(candidate.source_url)
        if not cand_domain or cand_domain == target_domain:
            continue

        # Rule 3: event_type must match
        if candidate.event_type != target_type:
            continue

        # Rule 4: location must overlap
        cand_location = _normalise_location(candidate.location_mentioned)
        if not _locations_overlap(target_location, cand_location):
            continue

        # Rule 5: time window check
        if window is not None:
            cand_time = _get_event_time(candidate)
            if cand_time is None or target_time is None:
                # If timestamps are unavailable, skip time check
                pass
            else:
                if abs((cand_time - target_time).total_seconds()) > window.total_seconds():
                    continue

        # Passed all checks — count each domain once
        seen_corroborating_domains.add(cand_domain)

    count = len(seen_corroborating_domains)
    logger.debug(
        f"[CORROBORATE] event={event.id} type={target_type} location='{event.location_mentioned}' "
        f"→ {count} corroborating domain(s)"
    )
    return count
