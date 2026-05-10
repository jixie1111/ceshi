from src.backend.app.utils.text import normalize_key


def test_normalize_synonyms():
    assert normalize_key('leukocyte') == '白细胞'
    assert normalize_key('炎症反应') == '炎症'
