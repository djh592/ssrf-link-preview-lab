import pytest

from ssrf_link_preview_lab.fetching.errors import InvalidUrlError
from ssrf_link_preview_lab.fetching.url import validate_http_url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.test/file",
        "http://user:password@example.test/",
        "http://[::1]/",
        "http://example.test/\nheader",
        "http:///missing-host",
        "http://example.test:99999/",
        "http://127.1/",
        "http://2130706433/",
        "http://example.test./",
        "http://exa_mple.test/",
        "http://tést.example/",
        "http://%31%32%37.0.0.1/",
        " http://example.test/",
        "http://example.test/ ",
    ],
)
def test_rejects_urls_outside_common_fetching_contract(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        validate_http_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test/",
        "https://example.test:8443/path?value=1#fragment",
        "http://127.0.0.1/internal",
        "https://xn--bcher-kva.example/",
    ],
)
def test_accepts_http_urls_for_the_unfiltered_baseline(url: str) -> None:
    assert validate_http_url(url) == url
