import json
from urllib.parse import quote

import pytest

from app import app, FIGHTERS_DATA, HEROES, PRICES

MY_SETS = ["Battle of Legends Vol. 1", "Cobble & Fog"]


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def with_collection(client, sets=MY_SETS):
    # Same format the browser writes: encodeURIComponent(JSON)
    client.set_cookie("ufs_default_owned_sets", quote(json.dumps(sets)))
    return client


@pytest.mark.parametrize("path", [
    "/collection", "/fighters", "/fighter/medusa", "/buy-next", "/buy-next?sort=value&in_stock=1",
    "/tiers", "/counter", "/counter?vs=medusa", "/game-night", "/game-night?go=1&players=3",
    "/game-night?go=1&mode=2v2", "/draft", "/log",
])
def test_tool_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert 'class="site-nav"' in resp.get_data(as_text=True)


def test_unknown_fighter_is_404(client):
    assert client.get("/fighter/not-a-fighter").status_code == 404


def test_every_fighter_has_card_data_and_a_page(client):
    assert {f["id"] for f in FIGHTERS_DATA} <= set(HEROES)
    html = client.get("/fighter/medusa").get_data(as_text=True)
    assert "Gaze of Stone" in html                      # deck list
    assert "deal 1 damage to an opposing fighter" in html  # special ability
    assert "Harpies" in html                            # sidekicks


def test_collection_cookie_drives_the_tools(client):
    with_collection(client)
    html = client.get("/buy-next").get_data(as_text=True)
    assert "Using <strong>your collection</strong>: 2 sets" in html
    for owned in MY_SETS:
        assert f". {owned}</h2>" not in html            # owned sets aren't offered
    tiers = client.get("/tiers").get_data(as_text=True)
    assert "/fighter/medusa" in tiers and "/fighter/spider_man" not in tiers


def test_sets_in_the_url_override_the_cookie(client):
    with_collection(client)
    html = client.get("/tiers?sets=Teen%20Spirit").get_data(as_text=True)
    assert "/fighter/ms_marvel" in html and "/fighter/medusa" not in html


def test_buy_next_shows_price_and_stock(client):
    with_collection(client)
    html = client.get("/buy-next").get_data(as_text=True)
    priced = next(s for s, p in PRICES.items() if s not in MY_SETS)
    assert PRICES[priced]["url"] in html


def test_sitemap_lists_fighter_pages(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/fighter/medusa</loc>" in xml and "/buy-next</loc>" in xml


def test_only_draft_and_log_embed_the_matchup_table(client):
    assert '"medusa": {' in client.get("/draft").get_data(as_text=True)
    assert "const MATCHUPS = {};" in client.get("/fighters").get_data(as_text=True)
