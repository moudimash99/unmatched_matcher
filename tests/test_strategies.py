import re

import pytest

import strategies
from app import app, FIGHTERS_DATA, STRATEGY_GUIDES


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_every_fighter_has_both_guides():
    missing = [f["id"] for f in FIGHTERS_DATA
               if not (STRATEGY_GUIDES.get(f["id"], {}).get("short") and STRATEGY_GUIDES[f["id"]].get("full"))]
    assert missing == []


@pytest.mark.parametrize("kind,prefix", [("short", "s"), ("full", "f")])
def test_guides_render_cleanly(kind, prefix):
    for fid, guide in STRATEGY_GUIDES.items():
        html = str(guide[kind])
        assert not re.search(r"\*\*|\]\(|`|<!--|", html), fid  # no Markdown left over
        cited = set(re.findall(r'href="#%s-ref-(\d+)"' % prefix, html))
        listed = set(re.findall(r'id="%s-ref-(\d+)"' % prefix, html))
        assert cited <= listed, (fid, cited - listed)


def test_render_escapes_html_and_links_sources():
    html = strategies.render(
        "<!-- id: x -->\n## X\n\n**In short:** a <b> test [1].\n\n### References\n"
        "1. Someone. *Site*, 2024. https://example.com/a_b/\n\nA note on `input/heroes.json`.\n\n### Not cited\n"
        "- [Video](https://youtu.be/x): Channel · video (not yet reviewed)\n"
        "- [Thread](https://example.com/t): Reddit · thread (read; no strategy)\n---", "f")
    assert "&lt;b&gt;" in html and "<b>" not in html
    assert '<a href="#f-ref-1">[1]</a>' in html and 'id="f-ref-1"' in html
    assert '<a href="https://example.com/a_b/"' in html and "<em>Site</em>" in html
    assert "Channel · video</li>" in html and "Thread" not in html
    assert "A note on" not in html  # research notes under References stay off the site


def test_fighter_page_shows_the_guide(client):
    html = client.get("/fighter/daredevil").get_data(as_text=True)
    assert "How to play Daredevil" in html
    assert "Read the full guide" in html
    assert "Devil of Hell&#39;s Kitchen" in html or "Devil of Hell's Kitchen" in html
