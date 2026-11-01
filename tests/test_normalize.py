import pytest

from app.services.normalize import normalize_domain, normalize_phone


@pytest.mark.parametrize(("raw", "expected"), [
    ("0712345678", "254712345678"),
    ("0712 345 678", "254712345678"),
    ("+254 712 345 678", "254712345678"),
    ("254112345678", "254112345678"),
    ("712345678", "254712345678"),
    ("0812345678", None),
    ("12345", None),
    ("", None),
])
def test_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("acme.co.ke", "acme.co.ke"),
    ("https://www.Acme.co.ke/shop?x=1", "acme.co.ke"),
    ("http://shop.acme.com:8080", "shop.acme.com"),
    ("localhost", None),
    ("not a domain", None),
    ("", None),
])
def test_domain(raw, expected):
    assert normalize_domain(raw) == expected
