import pytest

from rolecard.services.dedup import fold, is_web_url, match_key, text_key, url_key


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://Jobs.Example.com/o/1/", "https://jobs.example.com/o/1"),
        ("https://jobs.example.com/o/1?utm_source=x&utm_medium=y", "https://jobs.example.com/o/1"),
        ("https://jobs.example.com/o/1#apply", "https://jobs.example.com/o/1"),
        ("https://jobs.example.com:443/o/1?id=3&gclid=z", "https://jobs.example.com/o/1?id=3"),
        ("  HTTP://x.com/a  ", "http://x.com/a"),
    ],
)
def test_same_offer_same_key(a, b):
    assert url_key(a) == url_key(b)


def test_different_offers_different_keys():
    assert url_key("https://x.com/o?id=1") != url_key("https://x.com/o?id=2")
    assert url_key("https://x.com:8080/o") != url_key("https://x.com/o")


@pytest.mark.parametrize("url", ["", None, "javascript:alert(1)", "ftp://x.com/a", "x.com/a",
                                 "http://", "data:text/html,hi"])
def test_non_web_urls(url):
    assert url_key(url) is None
    assert not is_web_url(url or "")


def test_text_key_ignores_spacing_and_case():
    assert text_key("Senior  Python\nDeveloper ") == text_key("senior python developer")
    assert text_key("a b") != text_key("a c")


def test_fold_and_match_key():
    assert fold("  Désarrollo, S.L.  ") == "desarrollo s l"
    assert match_key("Ácme", "Python Dev!", "Málaga") == "acme|python dev|malaga"
    assert match_key("", "Python Dev") is None and match_key("Acme", "  ") is None
