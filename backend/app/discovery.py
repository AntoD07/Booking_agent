"""Reference-artist venue discovery via the Claude API.

Given one or two reference artists from the manouche/swing scene, ask
Claude (with the server-side web search tool) where they have played in
Europe and return structured venue suggestions for human review. Nothing
is written to the pipeline here — accepting a suggestion happens in the
discovery router, one suggestion at a time.
"""

import difflib
import json
import logging
import re
import time
import unicodedata
from typing import Callable

import anthropic

from app.config import anthropic_api_key
from app.models import VenueType

logger = logging.getLogger(__name__)

DISCOVERY_MODEL = "claude-opus-4-8"
# Kept small on purpose: each search triggers extra server-side filtering
# steps, and a scan must finish comfortably inside SCAN_MAX_SECONDS.
MAX_WEB_SEARCHES = 6
# With streaming this bounds the wait for the next event, not the whole
# scan — a healthy scan sends events continuously, so a long gap means the
# request is stuck and should fail rather than zombie.
REQUEST_TIMEOUT_SECONDS = 300.0
# Hard wall-clock cap for a whole scan; past this the stream is torn down
# and the job fails with a clear message instead of hanging.
SCAN_MAX_SECONDS = 600.0
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

Return 6 to 12 suggestions. End your reply with ONLY a JSON array inside a
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

_GENERAL_PROMPT = """\
We are a gypsy jazz (jazz manouche) quartet booking our 2027 season in
Europe. Find {what} in {region}{period_clause} that could book a band
like ours — places with a jazz, swing, or acoustic-music programme.

Use web search to find real, current listings — festival calendars, venue
programmes, cultural agendas, event announcements. Only include places in
Europe.

Return 6 to 12 suggestions. End your reply with ONLY a JSON array inside a
```json code fence, one object per venue, with exactly these keys:
- "name": the venue or festival name
- "type": one of "festival", "venue", "jazz_club", "bar", "cultural_center"
- "city": city, or null
- "country": country name in English, or null
- "website": the venue's own website URL, or null
- "event_dates": when the event or season takes place, as free text, or null
- "source_url": URL of the page documenting the event, or null

Do not invent venues; only include places you found evidence for.
"""

_TYPE_PHRASES = {
    VenueType.festival: "festivals",
    VenueType.venue: "concert venues",
    VenueType.jazz_club: "jazz clubs",
    VenueType.bar: "bars with live music",
    VenueType.cultural_center: "cultural centers",
}


class DiscoveryError(Exception):
    """Claude replied, but not with a usable suggestion list."""


def ping() -> dict:
    """A near-free Claude round-trip to verify key, network, and model.

    Costs a fraction of a cent — use it to rule out infrastructure before
    burning money on full scans.
    """
    client = anthropic.Anthropic(
        api_key=anthropic_api_key(), timeout=30.0, max_retries=0
    )
    started = time.monotonic()
    response = client.messages.create(
        model=DISCOVERY_MODEL,
        max_tokens=32,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
    )
    seconds = round(time.monotonic() - started, 1)
    logger.info("ping: %s answered in %.1fs", response.model, seconds)
    return {"ok": True, "model": response.model, "seconds": seconds}


def _create_message(
    client: anthropic.Anthropic,
    messages: list,
    note: "Progress | None" = None,
    deadline: float | None = None,
) -> anthropic.types.Message:
    # Streamed because a web-search turn runs for minutes: a non-streaming
    # request sits idle the whole time and dies on connection timeouts,
    # while a stream keeps the connection alive until the turn completes.
    # Iterating the events lets us surface live progress and enforce the
    # scan-wide deadline mid-turn.
    steps = 0
    with client.messages.stream(
        model=DISCOVERY_MODEL,
        # Thinking counts against this too; leave generous headroom so the
        # final JSON list never gets cut off mid-reply.
        max_tokens=16000,
        thinking={"type": "adaptive"},
        # Scans are retrieval, not hard reasoning; medium is faster and
        # plenty for this task.
        output_config={"effort": "medium"},
        tools=[
            {
                # The basic search variant on purpose: the _20260209 version
                # runs server-side filtering programs around every search
                # (observed: 19+ tool steps for a 6-search budget, ~8-minute
                # turns). Plain searches keep a scan down to a few minutes.
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_WEB_SEARCHES,
            }
        ],
        messages=messages,
    ) as stream:
        for event in stream:
            if deadline is not None and time.monotonic() > deadline:
                raise DiscoveryError(
                    f"the scan exceeded {int(SCAN_MAX_SECONDS // 60)} minutes "
                    "and was stopped"
                )
            if note is None or event.type != "content_block_start":
                continue
            block_type = getattr(event.content_block, "type", None)
            if block_type == "server_tool_use":
                # Counts searches AND the tool's internal filtering steps —
                # so this number can exceed MAX_WEB_SEARCHES; it's a
                # liveness signal, not a search count.
                steps += 1
                note(f"Research step {steps}…")
            elif block_type == "thinking":
                note("Claude is thinking…")
            elif block_type == "text":
                note("Claude is writing up its findings…")
        return stream.get_final_message()


Progress = Callable[[str], None]


def run_discovery(
    artist_names: list[str], progress: Progress | None = None
) -> list[dict]:
    if len(artist_names) > 1:
        joined = ", ".join(artist_names[:-1]) + " and " + artist_names[-1]
    else:
        joined = artist_names[0]
    return _run_prompt(_PROMPT.format(artists=joined), progress)


def run_general_discovery(
    region: str,
    event_type: VenueType | None,
    period: str | None,
    progress: Progress | None = None,
) -> list[dict]:
    what = _TYPE_PHRASES.get(event_type, "festivals, jazz clubs, and concert venues")
    period_clause = f" during {period}" if period else ""
    return _run_prompt(
        _GENERAL_PROMPT.format(what=what, region=region, period_clause=period_clause),
        progress,
    )


def _run_prompt(prompt: str, progress: Progress | None = None) -> list[dict]:
    scan_started = time.monotonic()
    deadline = scan_started + SCAN_MAX_SECONDS

    def note(message: str) -> None:
        stamped = f"{message} ({time.monotonic() - scan_started:.0f}s elapsed)"
        logger.info("scan: %s", stamped)
        if progress is not None:
            progress(stamped)

    client = anthropic.Anthropic(
        api_key=anthropic_api_key(),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=1,
    )
    messages: list = [{"role": "user", "content": prompt}]
    note("Contacting Claude…")

    response = _create_message(client, messages, note, deadline)
    note(f"First round finished (stop reason: {response.stop_reason})")
    for continuation in range(MAX_CONTINUATIONS):
        if response.stop_reason != "pause_turn":
            break
        messages = messages + [{"role": "assistant", "content": response.content}]
        note(f"Search continues (round {continuation + 2})…")
        response = _create_message(client, messages, note, deadline)
        note(
            f"Round {continuation + 2} finished "
            f"(stop reason: {response.stop_reason})"
        )

    text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    try:
        suggestions = _parse_suggestions(text)
    except DiscoveryError:
        if response.stop_reason == "max_tokens":
            raise DiscoveryError(
                "Claude ran out of room before writing the suggestion list "
                "— try again with fewer artists or a narrower search"
            )
        raise
    note(f"Parsed {len(suggestions)} suggestions from Claude's reply")
    return suggestions


def _parse_suggestions(text: str) -> list[dict]:
    items = _extract_json_array(text)
    if items is None:
        raise DiscoveryError(
            "Claude's reply did not contain a suggestion list "
            f"(reply starts: {text[:200]!r})"
        )
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
                "event_dates": _clean(item.get("event_dates")),
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
