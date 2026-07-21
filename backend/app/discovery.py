"""Reference-artist venue discovery via the Claude API.

Given one or two reference artists from the manouche/swing scene, ask
Claude (with the server-side web search tool) where they have played in
Europe and return structured venue suggestions for human review. Nothing
is written to the pipeline here — accepting a suggestion happens in the
discovery router, one suggestion at a time.
"""

import difflib
import json
import re
import unicodedata

import anthropic

from app.config import anthropic_api_key
from app.models import VenueType

DISCOVERY_MODEL = "claude-opus-4-8"
MAX_WEB_SEARCHES = 12
# Server-side tool loops can stop with stop_reason "pause_turn"; the request
# must be re-sent to let the search continue. Bounded to avoid infinite loops.
MAX_CONTINUATIONS = 5

_PROMPT = """\
We are a gypsy jazz (jazz manouche) quartet booking our 2027 season in
Europe. Find European venues, festivals, jazz clubs, bars, and cultural
centers where the following reference artist(s) have played, focusing on
the manouche/swing circuit: {artists}.

Use web search to find real, verifiable appearances — concert listings,
festival line-ups, venue programmes, tour date pages. Prefer places that
regularly programme gypsy jazz or swing. Only include venues in Europe.

Return 8 to 15 suggestions. End your reply with ONLY a JSON array inside a
```json code fence, one object per venue, with exactly these keys:
- "name": the venue or festival name
- "type": one of "festival", "venue", "jazz_club", "bar", "cultural_center"
- "city": city, or null
- "country": country name in English, or null
- "website": the venue's own website URL, or null
- "artist": which of the given artist(s) played there
- "source_url": URL of the page documenting the appearance, or null

Do not invent venues; only include places you found evidence for.
"""


class DiscoveryError(Exception):
    """Claude replied, but not with a usable suggestion list."""


def _create_message(client: anthropic.Anthropic, messages: list) -> anthropic.types.Message:
    return client.messages.create(
        model=DISCOVERY_MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        tools=[
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": MAX_WEB_SEARCHES,
            }
        ],
        messages=messages,
    )


def run_discovery(artist_names: list[str]) -> list[dict]:
    client = anthropic.Anthropic(api_key=anthropic_api_key())
    if len(artist_names) > 1:
        joined = ", ".join(artist_names[:-1]) + " and " + artist_names[-1]
    else:
        joined = artist_names[0]
    prompt = _PROMPT.format(artists=joined)
    messages: list = [{"role": "user", "content": prompt}]

    response = _create_message(client, messages)
    for _ in range(MAX_CONTINUATIONS):
        if response.stop_reason != "pause_turn":
            break
        messages = messages + [{"role": "assistant", "content": response.content}]
        response = _create_message(client, messages)

    text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return _parse_suggestions(text)


def _parse_suggestions(text: str) -> list[dict]:
    items = _extract_json_array(text)
    if items is None:
        raise DiscoveryError("Claude's reply did not contain a suggestion list")
    suggestions = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        suggestions.append(
            {
                "name": name.strip(),
                "type": _coerce_type(item.get("type")),
                "city": _clean(item.get("city")),
                "country": _clean(item.get("country")),
                "website": _clean(item.get("website")),
                "artist": _clean(item.get("artist")),
                "source_url": _clean(item.get("source_url")),
            }
        )
    return suggestions


def _extract_json_array(text: str) -> list | None:
    fences = re.findall(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    candidates = list(reversed(fences))
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed
    return None


def _clean(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _coerce_type(value) -> VenueType:
    if isinstance(value, str):
        normalized = re.sub(r"[\s\-]+", "_", value.strip().lower())
        try:
            return VenueType(normalized)
        except ValueError:
            if "club" in normalized:
                return VenueType.jazz_club
            if "festival" in normalized:
                return VenueType.festival
            if "bar" in normalized:
                return VenueType.bar
            if "cultur" in normalized:
                return VenueType.cultural_center
    return VenueType.venue


def _normalized_name(name: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_name.lower()).strip()


def find_pipeline_match(
    name: str, existing: list[tuple[int, str]]
) -> tuple[int, str] | None:
    """Match a suggested name against pipeline venues by name similarity.

    Word order is ignored ("Festival Django Reinhardt" matches "Django
    Reinhardt Festival"); containment only counts for reasonably long
    names so "Bar" doesn't match every bar in the list.
    """
    target = _normalized_name(name)
    if not target:
        return None
    target_sorted = " ".join(sorted(target.split()))
    for venue_id, venue_name in existing:
        candidate = _normalized_name(venue_name)
        if not candidate:
            continue
        if target == candidate:
            return venue_id, venue_name
        shorter = min(len(target), len(candidate))
        if shorter >= 6 and (target in candidate or candidate in target):
            return venue_id, venue_name
        candidate_sorted = " ".join(sorted(candidate.split()))
        ratio = difflib.SequenceMatcher(
            None, target_sorted, candidate_sorted
        ).ratio()
        if ratio >= 0.85:
            return venue_id, venue_name
    return None
