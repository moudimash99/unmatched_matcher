import re

import pytest

import strategies
from app import app, FIGHTERS_DATA, HEROES, STRATEGY_GUIDES


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_every_fighter_has_a_short_and_a_medium_guide():
    missing = [f["id"] for f in FIGHTERS_DATA
               if not (STRATEGY_GUIDES.get(f["id"], {}).get("short") and STRATEGY_GUIDES[f["id"]].get("medium"))]
    assert missing == []


@pytest.mark.parametrize("kind,prefix", [("short", "s"), ("medium", "m"), ("cards", "c")])
def test_guides_render_cleanly(kind, prefix):
    for fid, guide in STRATEGY_GUIDES.items():
        if not guide[kind]:
            continue
        html = str(guide[kind])
        assert not re.search(r"\*\*|\]\(|`|<!--|", html), fid  # no Markdown left over
        cited = set(re.findall(r'href="#%s-ref-(\d+)"' % prefix, html))
        listed = set(re.findall(r'id="%s-ref-(\d+)"' % prefix, html))
        assert cited <= listed, (fid, cited - listed)


def test_card_by_card_headings_are_real_cards():
    # In the card-by-card guides every card entry is a bold line holding only card names
    path = "input/fighter_guides_cards.md"
    for fid, entry in strategies.load(path).items():
        titles = {strategies._clean_title(c["title"]).lower() for c in HEROES[fid]["deck"]}
        for line in re.findall(r"^\*\*([^*]+)\*\*\s*$", entry.split("### References")[0], re.M):
            line = line.strip().lower().replace("’", "'")
            assert line in titles or all(n in titles for n in re.split(r" and |, ", line)), (fid, line)


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


def test_card_names_become_hover_cards():
    deck = [
        {"title": "What's That In My Basket? 🌟", "type": "versatile", "value": 4, "boost": 3, "copies": 4,
         "character": "Little Red", "effect": "Counts as <any> symbol."},
        {"title": "Feint", "type": "versatile", "value": 2, "boost": 2, "copies": 3, "character": "Any",
         "effect": "Cancel all effects."},
        {"title": "HINDSIGHT", "type": "scheme", "boost": 1, "copies": 1, "character": "Loki", "effect": "Draw."},
        {"title": "Again", "type": "scheme", "boost": 1, "copies": 1, "character": "Any", "effect": "x"},
    ]
    cards = strategies.card_matcher(deck, "Little Red")
    html = str(strategies.render(
        "## X\n\n- Attack with What’s That In My Basket? [1], then Feint, not feinting. Hindsight helps. "
        "Again, play it.\n\n### References\n1. Feint guide. https://example.com/Feint", "m", cards))
    assert html.count('class="card-ref"') == 3
    assert "What’s That In My Basket?<span class=\"card-pop\"" in html
    assert "Counts as &lt;any&gt; symbol." in html  # card text is escaped
    assert "Versatile · value 4 · boost 3 · ×4" in html
    assert 'card-pop-who">Loki' in html and 'card-pop-who">Little Red' not in html
    assert "feinting" in html and "Again, play it" in html  # ordinary words stay plain
    assert '<a href="https://example.com/Feint"' in html  # nothing inside References or URLs


def test_fighter_page_shows_the_guide_tabs(client):
    html = client.get("/fighter/daredevil").get_data(as_text=True)
    assert "How to play Daredevil" in html
    assert 'id="guide-tab-medium"' in html and 'aria-selected="true"' in html
    assert re.search(r'id="guide-medium"[^>]*>', html).group(0).find("hidden") == -1  # Medium shows first
    assert re.search(r'id="guide-short"[^>]*hidden', html)


def test_v2_guides_link_their_cards(client):
    html = client.get("/fighter/medusa").get_data(as_text=True)
    medium = html[html.index('id="guide-medium"'):]
    assert 'class="card-ref"' in medium and "Gaze of Stone<span" in medium


def test_guide_layout_boxes_labels_and_card_pictures():
    deck = [{"title": "Feint", "type": "versatile", "value": 2, "boost": 2, "copies": 3, "effect": "Cancel."},
            {"title": "Skirmish", "type": "attack", "value": 4, "boost": 2, "copies": 3, "effect": "Move."}]
    cards = strategies.card_matcher(deck, "X", {"Feint": "https://img.example/feint.png"})
    html = str(strategies.render(
        "## X\n\n**In short:** Fight. [1]\n\n### How they win\n\n**Early pressure**\n\n"
        "- **Choose this when:** they are slow. [1]\n- **On your turn:** attack with Skirmish.\n\n"
        "### How they lose\n\n- **Cancels:** they hurt. **Answer:** bait with Feint. [1]\n\n"
        "### Cards: when and how to use them\n\n**Feint**\n\n- **When:** early.\n\n**Skirmish**\n\n- **How:** often.\n\n"
        "### References\n1. Someone. https://example.com/a", "c", cards))
    assert '<p class="guide-lede">' in html
    assert '<div class="guide-box"><h4>Early pressure</h4>' in html
    assert '<li class="guide-item guide-choose"><span class="guide-label">Choose this when</span>' in html
    assert '<span class="guide-answer">Answer</span> bait with' in html
    assert '<img class="card-pop-img" src="https://img.example/feint.png" alt="Feint: Cancel."' in html
    assert "Attack · value 4" in html  # no picture: the card text stands in
    assert '<nav class="guide-jump" aria-label="Cards"><a href="#c-card-feint">Feint</a><a href="#c-card-skirmish">' in html
    assert '<div class="guide-box guide-card" id="c-card-feint"><img class="guide-thumb"' in html
    assert '<div class="guide-box guide-card" id="c-card-skirmish"><h4>' in html
    assert html.index('<details class="guide-sources">') < html.index('id="c-ref-1"')


def test_fighter_page_layout(client):
    html = client.get("/fighter/medusa").get_data(as_text=True)
    assert '<nav class="page-jump"' in html and 'href="#deck"' in html
    assert '<div class="deck-grid">' in html and "static.unmatched.cards" in html
    assert re.search(r'id="all-matchups">\s*<details class="fold">', html)
    no_pictures = client.get("/fighter/loki").get_data(as_text=True)  # not in the card database yet
    assert '<div class="deck-grid">' not in no_pictures and "<table class=\"data\">" in no_pictures
