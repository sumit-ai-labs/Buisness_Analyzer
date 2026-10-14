import json
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger


class LLMClientError(Exception):
    """Custom exception raised when LLM extraction fails."""

    pass


SYSTEM_PROMPT = """You are an expert supply chain disruption analysis agent.
Analyze the provided news title and snippet about a business entity/location.
Extract structured details about any potential or active supply chain disruption.

CRITICAL RELEVANCE RULES:
- Set `is_relevant = true` ONLY IF there is an actual, ongoing, active, or imminent disruption (e.g., active strike, flooding, plant shutdown, bankruptcy, port blockage).
- Set `is_relevant = false` IF the strike was averted, agreement reached, threat resolved, rumor debunked, historical event (>1 year ago), or irrelevant news (e.g., normal business expansion, corporate sponsorship, marketing release).
- DO NOT reject an article if resolution phrases are negated (e.g. 'no agreement reached', 'talks failed to resolve', 'operations have not resumed').
- If an incident is resolved but explicitly states CONTINUING operational consequence, supply backlogs, or production delays persist, set `is_relevant = true`.
- If an article mentions both a resolved event and a NEW active disruption, set `is_relevant = true` based on the active disruption.
- If the text cannot confidently determine whether the event remains active, set `severity_raw = "unclear"` and `confidence = 0.4` to route to review status.

Return ONLY a valid JSON object matching this schema:
{
  "headline": string,
  "summary": string (1-2 sentences),
  "event_type": "flood" | "strike" | "closure" | "supplier_failure" | "political" | "weather" | "other",
  "location_mentioned": string,
  "severity_raw": "low" | "medium" | "high" | "unclear",
  "extracted_entities": [string],
  "confidence": float (0.0 to 1.0),
  "is_relevant": boolean
}
"""

# Ordered fallback chain for Gemini models
DEFAULT_GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


class LLMClientWrapper:
    """LLM API wrapper supporting Gemini (with multi-model fallback chain), OpenAI, Anthropic, or heuristic rule engine."""

    def __init__(
        self,
        provider: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        llm_api_key: Optional[str] = None,
    ):
        self.provider = provider if provider is not None else settings.LLM_PROVIDER
        self.gemini_api_key = gemini_api_key if gemini_api_key is not None else (settings.GEMINI_API_KEY or settings.LLM_API_KEY)
        self.llm_api_key = llm_api_key if llm_api_key is not None else settings.LLM_API_KEY
        self.model = settings.LLM_MODEL

    def extract_disruption_event(self, title: str, snippet: str, entity_name: str) -> Dict[str, Any]:
        """Extracts structured disruption event dictionary from news article title and snippet."""
        if self.provider == "gemini" and self.gemini_api_key and self.gemini_api_key.strip():
            return self._call_gemini_with_fallbacks(title, snippet, entity_name)
        elif self.provider == "openai" and self.llm_api_key and self.llm_api_key.strip():
            return self._call_openai(title, snippet, entity_name)
        elif self.provider == "anthropic" and self.llm_api_key and self.llm_api_key.strip():
            return self._call_anthropic(title, snippet, entity_name)
        else:
            # Try Gemini first if key available regardless of provider setting
            if self.gemini_api_key and self.gemini_api_key.strip():
                return self._call_gemini_with_fallbacks(title, snippet, entity_name)
            logger.info("No LLM API keys configured. Using heuristic rule-based extraction fallback.")
            return self._heuristic_extraction(title, snippet, entity_name)

    def _call_gemini_with_fallbacks(self, title: str, snippet: str, entity_name: str) -> Dict[str, Any]:
        """Calls Google Gemini API using structured JSON mode with automatic multi-model fallback chain."""
        # Build candidate fallback order starting with configured model
        models_to_try: List[str] = []
        if self.model and self.model.strip():
            models_to_try.append(self.model.strip())

        for default_m in DEFAULT_GEMINI_MODELS:
            if default_m not in models_to_try:
                models_to_try.append(default_m)

        user_content = f"Entity: {entity_name}\nArticle Title: {title}\nSnippet: {snippet}"

        for model_name in models_to_try:
            try:
                logger.info(f"Attempting Gemini extraction with model '{model_name}'...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
                
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": f"{SYSTEM_PROMPT}\n\nTask Content:\n{user_content}"
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.1,
                        "responseMimeType": "application/json",
                    },
                }

                with httpx.Client(timeout=20.0) as client:
                    resp = client.post(url, json=payload)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed_json = json.loads(text_content)
                        logger.info(f"Successfully extracted disruption event using Gemini model '{model_name}'")
                        return parsed_json
                    else:
                        logger.warning(
                            f"Gemini model '{model_name}' returned HTTP {resp.status_code}: {resp.text[:200]}. Trying next fallback model..."
                        )
            except Exception as exc:
                logger.warning(f"Error calling Gemini model '{model_name}': {exc}. Trying next fallback...")

        logger.error("All Gemini model fallbacks exhausted or failed. Falling back to heuristic engine.")
        return self._heuristic_extraction(title, snippet, entity_name)

    def _call_openai(self, title: str, snippet: str, entity_name: str) -> Dict[str, Any]:
        """Calls OpenAI API with JSON response format."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }
        user_content = f"Entity: {entity_name}\nArticle Title: {title}\nSnippet: {snippet}"

        payload = {
            "model": self.model or "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
        }

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as exc:
            logger.error(f"OpenAI call failed ({exc}). Falling back to heuristic rule engine.")
            return self._heuristic_extraction(title, snippet, entity_name)

    def _call_anthropic(self, title: str, snippet: str, entity_name: str) -> Dict[str, Any]:
        """Calls Anthropic Claude API."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.llm_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        user_content = f"Entity: {entity_name}\nArticle Title: {title}\nSnippet: {snippet}\n\nReturn ONLY raw JSON object."

        payload = {
            "model": self.model or "claude-3-5-haiku-20241022",
            "max_tokens": 1000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_content}],
            "temperature": 0.1,
        }

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data["content"][0]["text"]
                return json.loads(text)
        except Exception as exc:
            logger.error(f"Anthropic call failed ({exc}). Falling back to heuristic rule engine.")
            return self._heuristic_extraction(title, snippet, entity_name)

    def _heuristic_extraction(self, title: str, snippet: str, entity_name: str) -> Dict[str, Any]:
        """Rule-based heuristic fallback extraction when LLM API key is absent or unreachable."""
        text_lower = f"{title} {snippet}".lower()

        # 1. Historical reporting check (events in the past without ongoing active disruption)
        historical_phrases = [
            "historical outage",
            "historic outage",
            "past outage",
            "historical incident",
            "anniversary of",
            "commemorating",
            "years ago",
            "decade ago",
            "looking back at",
            "recalled the 20",
            "remembering the 20",
            "in 2018",
            "in 2019",
            "in 2020",
            "in 2021",
            "in 2022",
        ]
        has_historical_indicator = any(p in text_lower for p in historical_phrases)

        # 2. Continuing operational consequence indicators
        continuing_impact_phrases = [
            "continuing production impact",
            "ongoing production impact",
            "production impact persists",
            "continuing impact",
            "ongoing impact",
            "supply backlog",
            "supply backlogs",
            "backlog persists",
            "backlogs persist",
            "lingering delays",
            "delivery delays persist",
            "delays continue",
            "operations still disrupted",
            "disruption continues",
            "operational consequence",
            "ongoing operational",
        ]
        has_continuing_impact = any(p in text_lower for p in continuing_impact_phrases)

        # 3. Negated resolution phrases (e.g. "no agreement reached", "strike not resolved")
        negated_resolution_phrases = [
            "no agreement reached",
            "failed to reach agreement",
            "not reached an agreement",
            "not resolved",
            "failed to resolve",
            "remains unresolved",
            "unresolved",
            "have not resumed",
            "has not resumed",
            "operations not resumed",
            "not called off",
            "strike ongoing",
            "active strike",
            "strike continues",
            "enters fourth day",
            "enters third day",
            "enters second day",
            "enters day",
            "talks broke down",
            "negotiations broke down",
        ]
        has_negated_resolution = any(p in text_lower for p in negated_resolution_phrases)

        # 4. Standard averted/resolved keywords
        averted_keywords = [
            "averted",
            "cancelled",
            "canceled",
            "settled",
            "agreement reached",
            "tentative agreement",
            "threat passed",
            "called off",
            "calling off strike",
            "strike called off",
            "resume operations",
            "resumed operations",
            "operations resume",
            "operations resumed",
            "resumed normal",
            "temporary disruption resolved",
            "disruption resolved",
            "resolved",
            "no disruption",
            "no delays",
        ]
        raw_averted_match = any(kw in text_lower for kw in averted_keywords)

        # An event is genuinely averted ONLY IF an averted keyword is present,
        # it is NOT negated (e.g. "no agreement reached"),
        # and there is NO continuing operational impact.
        is_averted = raw_averted_match and (not has_negated_resolution) and (not has_continuing_impact)

        # 5. Disruption detection keywords
        event_type = "other"
        severity = "medium"
        has_disruption = False

        if "flood" in text_lower or "inundation" in text_lower or "heavy rain" in text_lower:
            event_type = "flood"
            severity = "high"
            has_disruption = True
        elif "strike" in text_lower or "walkout" in text_lower or "labor dispute" in text_lower or "protest" in text_lower:
            event_type = "strike"
            severity = "high"
            has_disruption = True
        elif "closure" in text_lower or "closed" in text_lower or "shut down" in text_lower or "halted" in text_lower:
            event_type = "closure"
            severity = "high"
            has_disruption = True
        elif "bankruptcy" in text_lower or "insolvent" in text_lower or "supplier failure" in text_lower:
            event_type = "supplier_failure"
            severity = "high"
            has_disruption = True
        elif "sanction" in text_lower or "embargo" in text_lower or "tariff" in text_lower:
            event_type = "political"
            severity = "medium"
            has_disruption = True
        elif "storm" in text_lower or "typhoon" in text_lower or "hurricane" in text_lower:
            event_type = "weather"
            severity = "high"
            has_disruption = True
        elif "outage" in text_lower or "blackout" in text_lower or "explosion" in text_lower or "fire" in text_lower:
            event_type = "other"
            severity = "high"
            has_disruption = True

        # 6. Check for multi-event articles: averted event mentioned alongside a new active disruption
        # E.g. "strike called off, but severe flooding has inundated the plant today"
        new_disruption_indicators = ["today", "new", "now", "emergency", "current", "latest"]
        if is_averted and any(term in text_lower for term in new_disruption_indicators):
            if any(term in text_lower for term in ["flood", "flooding", "storm", "fire", "explosion", "shutdown", "closure"]):
                is_averted = False

        # 7. Ambiguity / Review status detection
        ambiguity_indicators = [
            "unclear whether",
            "uncertain if",
            "conflicting reports",
            "status unconfirmed",
            "unverified reports",
            "reports unconfirmed",
        ]
        is_ambiguous = any(ind in text_lower for ind in ambiguity_indicators)

        active_disruption_phrases = [
            "active", "ongoing", "currently", "continues to halt", "enters day",
            "disruption today", "flood today", "strike today", "closed today",
            "closure today", "outage today", "flooding today", "fire today",
        ]
        has_current_disruption = any(t in text_lower for t in active_disruption_phrases)
        if has_historical_indicator and not has_current_disruption and not has_continuing_impact:
            is_relevant = False
        else:
            is_relevant = has_disruption and (not is_averted)

        confidence = 0.85 if is_relevant else 0.40
        if is_relevant and is_ambiguous:
            severity = "unclear"
            confidence = 0.40  # lower confidence triggers review/unconfirmed gating
        elif is_relevant and has_continuing_impact and raw_averted_match:
            severity = "medium"
            confidence = 0.70  # continuing impact after resolution

        # Location extraction
        common_locations = [
            "rotterdam", "chennai", "mumbai", "houston", "austin", "munich",
            "hamburg", "antwerp", "dresden", "tokyo", "bangkok", "santiago",
            "shanghai", "singapore", "berlin", "london", "chicago", "hsinchu",
        ]
        loc_found = next((loc.title() for loc in common_locations if loc in text_lower), None)
        location_mentioned = loc_found or entity_name

        return {
            "headline": title[:100] if title else "Supply Chain Disruption Report",
            "summary": snippet[:300] if snippet else "Potential operational impact reported in news snippet.",
            "event_type": event_type,
            "location_mentioned": location_mentioned,
            "severity_raw": severity if is_relevant else "low",
            "extracted_entities": [entity_name],
            "confidence": confidence,
            "is_relevant": is_relevant,
        }


# Module instance singleton
llm_client = LLMClientWrapper()
