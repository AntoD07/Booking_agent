"""Build a festival-application email for a venue from the band's fixed template.

The pitch prose is approved and fixed — the band's story does not change per
venue. Only two things vary and both are reviewed by a human before anything
is sent (the app never sends email itself):

1. the personalisation hook — one or two sentences naming a real artist from
   the venue's recent programming and the link to its spirit; and
2. the date line — when we would like to play.

The greeting, subject, and signature are filled deterministically from the
venue and the band profile. The personalisation is written by Claude when an
API key is configured — Claude web-searches the venue's recent programme to
name a real artist it has booked and returns the page that documents it — and
falls back to a clearly bracketed placeholder when there is no key or nothing
verifiable turns up. Either way it must be checked before sending.
"""

import logging
import re
import time

import anthropic

from app.config import anthropic_api_key
from app.discovery import (
    MAX_CONTINUATIONS,
    REQUEST_TIMEOUT_SECONDS,
    DiscoveryError,
    _create_message,
    _extract_json_object,
)
from app.models import BandProfile, Venue, VenueType

logger = logging.getLogger(__name__)

# Drafting one hook is a single-venue lookup, so keep the whole web-search
# turn short — it runs inside the request, not as a background job.
DRAFT_MAX_SECONDS = 90.0

# The season we are booking; used for the subject and the default date line
# when the venue carries no more specific year. Bump when the season rolls over.
TARGET_SEASON_YEAR = 2027

# Francophone countries get the French template; everything else, English —
# those are the two versions of the pitch the band has approved.
FRENCH_COUNTRIES = {
    "france",
    "belgium",
    "belgique",
    "switzerland",
    "suisse",
    "luxembourg",
    "monaco",
}

# Country/role words that must never be mistaken for a contact's first name in
# the greeting (so "Programmation" or "Festival" falls back to the team form).
_NOT_A_FIRST_NAME = {
    "programmation",
    "programming",
    "direction",
    "booking",
    "contact",
    "festival",
    "equipe",
    "équipe",
    "team",
    "artistic",
    "artistique",
    "director",
    "directrice",
    "directeur",
    "info",
    "bureau",
    "office",
    "association",
}

# The fixed body. Only the bracketed {tokens} are filled per venue; the prose
# in between is the band's approved pitch and must match it exactly.
_FRENCH_BODY = """\
Bonjour {greeting},

{personalisation}

On s'appelle {band_name}, on vient de Lausanne et ça fait dix ans qu'on joue \
ensemble. On propose une fusion entre jazz manouche et hard bop acoustique, \
avec une formation atypique (deux guitares manouches, clarinette et basse \
électrique) : un hommage à Coltrane, Lee Morgan et Django dans un son qui \
parle autant aux amateurs de manouche qu'au public jazz plus large.

On sort notre premier album, Mixology, en septembre 2026 — huit relectures \
acoustiques, du hard bop des années 60 aux compositions de Django, \
enregistrées dans notre studio R-26 à Lausanne. L'album est aussi un projet \
visuel : la peintre Tara Harris (Birmingham) a transposé chacun des huit \
morceaux en une toile originale, avec des liner notes du guitariste Rodrigue \
Vera Ortiz.

On aimerait beaucoup le défendre sur scène chez vous {date_line}.

Deux extraits live qui donnent une bonne idée de notre énergie sur scène :
- {video1}
- {video2}

Vous trouverez tout le reste (album, toiles, photos, fiche technique) dans \
notre EPK : {epk}.

Je reste à dispo pour toute information complémentaire.

Musicalement,
{signature_name} pour {band_name}
{contact_line}"""

_ENGLISH_BODY = """\
Hello {greeting},

{personalisation}

We're {band_name}, from Lausanne, Switzerland, and we've been playing \
together for ten years. We offer a fusion of gypsy jazz and acoustic hard bop \
with an unconventional lineup (two manouche guitars, clarinet and electric \
bass): a tribute to Coltrane, Lee Morgan and Django, in a sound that \
resonates with manouche lovers and the broader jazz audience alike.

Our debut album, Mixology, is out in September 2026 — eight acoustic \
reinterpretations, from 1960s hard bop to Django's own compositions, recorded \
at our R-26 studio in Lausanne. The album is also a visual project: painter \
Tara Harris (Birmingham) translated each of the eight tracks into an original \
canvas, with liner notes by guitarist Rodrigue Vera Ortiz.

We'd love to bring it to your stage {date_line}.

Two live excerpts that give a good sense of our stage energy:
- {video1}
- {video2}

Everything else (album, paintings, photos, tech rider) is in our EPK: {epk}.

Happy to share anything else you need.

Musically yours,
{signature_name} for {band_name}
{contact_line}"""

# Placeholders left in the body when the band profile has no link yet, so the
# gap is obvious in the draft rather than an empty bullet.
_PLACEHOLDERS = {
    "fr": {
        "video1": "[lien vidéo 1]",
        "video2": "[lien vidéo 2]",
        "epk": "[lien EPK]",
        "personalisation": (
            "[À COMPLÉTER : citez un artiste réel de leur programmation "
            "récente et ce qui vous relie à l'esprit du festival.]"
        ),
    },
    "en": {
        "video1": "[video link 1]",
        "video2": "[video link 2]",
        "epk": "[EPK link]",
        "personalisation": (
            "[TO COMPLETE: name a real artist from their recent line-up and "
            "what connects you to the festival's spirit.]"
        ),
    },
}

_HOOK_PROMPT = """\
We are the gypsy jazz quartet Gipsy Tonic, writing a booking email to the \
venue below for our 2027 season. Write ONLY the opening personalisation line \
of that email — one or two sentences, in {language_name}.

It must name a REAL artist this venue has actually programmed (ideally in the \
last few seasons) and connect that to the spirit of what we do (gypsy jazz \
meeting acoustic hard bop). Use web search to check the venue's recent \
programme or line-up and find a concrete, verifiable name; you may also use \
the reference artists we already know played here.

Venue: {name}{place_clause} ({venue_type})
Reference artists we already know played here: {appearances}
Our research notes on the venue: {notes}

Rules:
- Ground the line in a real, checkable appearance — never invent an artist or \
an edition.
- If, after searching, you cannot verify any artist this venue programmed, do \
NOT guess: set "personalisation" to exactly "{placeholder}" and "source" to null.
- Warm and specific, not flattering filler. No greeting, no sign-off — just \
the one or two sentences.

End your reply with ONLY a JSON object inside a ```json code fence, with \
exactly these keys:
- "personalisation": the line, in {language_name} (string)
- "source": the URL of the page documenting that artist's appearance or \
programming at this venue, or null
"""


class DraftingError(Exception):
    """Claude replied, but not with a usable personalisation line."""


def draft_language(country: str | None) -> str:
    """'fr' for francophone venues, 'en' otherwise."""
    if country and country.strip().lower() in FRENCH_COUNTRIES:
        return "fr"
    return "en"


def _edition_year(venue: Venue) -> int:
    """The 2027-or-later year to name for this venue, best effort.

    Prefer a future year already on the card (event dates, then deadline);
    fall back to the target season. A past year never appears in the pitch.
    """
    if venue.event_dates:
        years = [int(m) for m in re.findall(r"\b(20\d{2})\b", venue.event_dates)]
        future = [y for y in years if y >= TARGET_SEASON_YEAR]
        if future:
            return min(future)
    if venue.application_deadline and venue.application_deadline.year >= TARGET_SEASON_YEAR:
        # A deadline in year N usually opens the edition of that same year.
        return venue.application_deadline.year
    return TARGET_SEASON_YEAR


def _date_line(venue: Venue, language: str, year: int) -> str:
    """Where we would like to play — an edition for festivals, else the season."""
    if language == "fr":
        if venue.type == VenueType.festival:
            return f"lors de votre édition {year}"
        return f"en {year}"
    if venue.type == VenueType.festival:
        return f"for your {year} edition"
    return f"in {year}"


def _first_name(booking_contact: str | None) -> str | None:
    """Extract a plausible first name from the booking contact, or None."""
    if not booking_contact:
        return None
    # First alphabetic token before a comma/role; ignore role words.
    head = re.split(r"[,;(/]", booking_contact.strip())[0].strip()
    token = re.split(r"\s+", head)[0] if head else ""
    letters = re.sub(r"[^\w'’-]", "", token, flags=re.UNICODE)
    if len(letters) < 2 or letters.lower() in _NOT_A_FIRST_NAME:
        return None
    if not letters[0].isupper():
        return None
    return letters


def _greeting(venue: Venue, language: str) -> str:
    name = _first_name(venue.booking_contact)
    if name:
        return name
    if language == "fr":
        return f"l'équipe de {venue.name}"
    return f"the {venue.name} team"


def _contact_line(profile: BandProfile) -> str:
    parts = [profile.phone, profile.email, profile.website]
    return " · ".join(part for part in parts if part and part.strip())


def _appearances_text(venue: Venue, language: str) -> str:
    items = []
    for appearance in venue.artists:
        if appearance.year:
            items.append(f"{appearance.name} ({appearance.year})")
        else:
            items.append(appearance.name)
    if items:
        return ", ".join(items)
    return "aucun connu" if language == "fr" else "none on record"


def _research_personalisation(venue: Venue, language: str) -> tuple[str, str | None]:
    """Web-search the venue's programme for the hook and its source.

    Returns (personalisation, source_url). Falls back to the bracketed
    placeholder (and no source) without a key, or if the search turns up
    nothing verifiable or errors — a hook problem must never sink the draft,
    since the rest of the email is fixed.
    """
    placeholder = _PLACEHOLDERS[language]["personalisation"]
    if not anthropic_api_key():
        return placeholder, None
    place = ", ".join(part for part in (venue.city, venue.country) if part)
    prompt = _HOOK_PROMPT.format(
        language_name="French" if language == "fr" else "English",
        name=venue.name,
        place_clause=f", {place}" if place else "",
        venue_type=venue.type.value,
        appearances=_appearances_text(venue, language),
        notes=(venue.research_notes or "—").strip(),
        placeholder=placeholder,
    )
    client = anthropic.Anthropic(
        api_key=anthropic_api_key(),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=1,
    )
    deadline = time.monotonic() + DRAFT_MAX_SECONDS
    messages: list = [{"role": "user", "content": prompt}]
    try:
        response = _create_message(client, messages, None, deadline)
        for _ in range(MAX_CONTINUATIONS):
            if response.stop_reason != "pause_turn":
                break
            messages = messages + [{"role": "assistant", "content": response.content}]
            response = _create_message(client, messages, None, deadline)
    except (DiscoveryError, anthropic.APIError) as exc:
        logger.warning("drafting: hook search failed (%s) — using placeholder", exc)
        return placeholder, None

    text = "".join(block.text for block in response.content if block.type == "text")
    data = _extract_json_object(text)
    value = data.get("personalisation") if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        # A malformed reply must not sink the whole draft — the rest is fixed.
        logger.warning("drafting: no usable personalisation in reply %r", text[:200])
        return placeholder, None
    source = data.get("source") if isinstance(data, dict) else None
    if not (isinstance(source, str) and source.strip() and source.strip().lower() != "null"):
        source = None
    else:
        source = source.strip()[:500]
    return value.strip(), source


def build_draft(venue: Venue, profile: BandProfile) -> tuple[str, str, str | None]:
    """Return (subject, body, source) for this venue's application email.

    `source` is the page Claude used to ground the opening line, or None.
    """
    language = draft_language(venue.country)
    year = _edition_year(venue)
    fill = _PLACEHOLDERS[language]
    band_name = profile.band_name or "Gipsy Tonic"

    if language == "fr":
        subject = f"{band_name} — Candidature {venue.name} {year} (sortie d'album)"
        template = _FRENCH_BODY
    else:
        subject = f"{band_name} — Application {venue.name} {year} (album release)"
        template = _ENGLISH_BODY

    personalisation, source = _research_personalisation(venue, language)
    body = template.format(
        greeting=_greeting(venue, language),
        personalisation=personalisation,
        date_line=_date_line(venue, language, year),
        band_name=band_name,
        signature_name=profile.signature_name or "Antony",
        contact_line=_contact_line(profile),
        video1=(profile.video1_url or fill["video1"]),
        video2=(profile.video2_url or fill["video2"]),
        epk=(profile.epk_url or fill["epk"]),
    )
    return subject[:300], body, source
