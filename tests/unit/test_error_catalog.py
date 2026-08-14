from gromacs_gui.gmx.error_catalog import ErrorCatalog


def test_match_known_pattern():
    catalog = ErrorCatalog.load()

    match = catalog.match("Fatal error: Too many warnings (5)")

    assert match is not None
    assert "warnings" in match.title.lower()
    assert match.suggestion is not None


def test_no_match_for_unrelated_text():
    catalog = ErrorCatalog.load()

    assert catalog.match("Steepest Descents converged to Fmax < 1000") is None
