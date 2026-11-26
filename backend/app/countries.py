"""One canonical name per country, so the board filter never shows twins.

Countries are free text written by different hands — the Notion import and
Claude's scans write English ("Switzerland"), manual edits are often French
("Suisse") — and each spelling becomes its own filter entry. Everything that
writes venue.country runs through normalize_country(), which folds the common
French / German / local spellings of the countries we tour into one canonical
English name (matching the imported data). Unknown values pass through
trimmed, never dropped.
"""

# alias (lowercase) -> canonical English name. English names map to
# themselves via the canonical set below, so only foreign spellings and
# accent/diacritic variants need listing.
_ALIASES = {
    # Switzerland
    "suisse": "Switzerland",
    "schweiz": "Switzerland",
    "svizzera": "Switzerland",
    # Germany
    "allemagne": "Germany",
    "deutschland": "Germany",
    # Belgium
    "belgique": "Belgium",
    "belgien": "Belgium",
    "belgië": "Belgium",
    "belgie": "Belgium",
    # Spain
    "espagne": "Spain",
    "españa": "Spain",
    "espana": "Spain",
    # Italy
    "italie": "Italy",
    "italia": "Italy",
    # Netherlands
    "pays-bas": "Netherlands",
    "pays bas": "Netherlands",
    "nederland": "Netherlands",
    "holland": "Netherlands",
    "hollande": "Netherlands",
    # United Kingdom
    "royaume-uni": "United Kingdom",
    "royaume uni": "United Kingdom",
    "uk": "United Kingdom",
    "grande-bretagne": "United Kingdom",
    "england": "United Kingdom",
    "angleterre": "United Kingdom",
    # Austria
    "autriche": "Austria",
    "österreich": "Austria",
    "osterreich": "Austria",
    # Portugal is the same word everywhere; France too.
    # Luxembourg likewise (Luxemburg is the German spelling)
    "luxemburg": "Luxembourg",
    # Denmark / Sweden / Norway
    "danemark": "Denmark",
    "danmark": "Denmark",
    "suède": "Sweden",
    "suede": "Sweden",
    "sverige": "Sweden",
    "norvège": "Norway",
    "norvege": "Norway",
    "norge": "Norway",
    # Poland / Czechia
    "pologne": "Poland",
    "polska": "Poland",
    "tchéquie": "Czech Republic",
    "tchequie": "Czech Republic",
    "république tchèque": "Czech Republic",
    "czechia": "Czech Republic",
    # Ireland / Greece / Hungary / Croatia
    "irlande": "Ireland",
    "grèce": "Greece",
    "grece": "Greece",
    "hongrie": "Hungary",
    "croatie": "Croatia",
    # United States (some festivals list it)
    "usa": "United States",
    "états-unis": "United States",
    "etats-unis": "United States",
}

# Canonical names, for fixing pure case variants ("switzerland" -> "Switzerland").
_CANONICAL = {name.lower(): name for name in set(_ALIASES.values())} | {
    name.lower(): name
    for name in (
        "France",
        "Portugal",
        "Luxembourg",
        "Monaco",
        "Finland",
        "Slovenia",
        "Slovakia",
        "Romania",
    )
}


def normalize_country(value: str | None) -> str | None:
    """Fold a country spelling onto its canonical English name.

    Trims whitespace; empty becomes None. Values we don't recognise are kept
    as typed — normalisation must never lose information.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    key = cleaned.lower()
    return _ALIASES.get(key) or _CANONICAL.get(key) or cleaned
