from app.countries import normalize_country


def test_french_and_local_spellings_fold_to_english():
    assert normalize_country("Suisse") == "Switzerland"
    assert normalize_country("schweiz") == "Switzerland"
    assert normalize_country("Allemagne") == "Germany"
    assert normalize_country("España") == "Spain"
    assert normalize_country("Pays-Bas") == "Netherlands"
    assert normalize_country("Royaume-Uni") == "United Kingdom"


def test_canonical_names_and_case_variants_are_stable():
    assert normalize_country("Switzerland") == "Switzerland"
    assert normalize_country("SWITZERLAND") == "Switzerland"
    assert normalize_country("france") == "France"


def test_unknown_blank_and_none_pass_through():
    assert normalize_country("Ruritania") == "Ruritania"
    assert normalize_country("  Ruritania  ") == "Ruritania"
    assert normalize_country("   ") is None
    assert normalize_country(None) is None
