import app as app_module


def test_owned_sets_load_collection_button_rendered():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    # The matcher loads the collection saved on /collection; there's no separate "default" to save
    assert 'id="load-default-sets-btn"' in html and "Load my collection" in html
    assert 'id="save-default-sets-btn"' not in html


def test_collection_page_has_an_explicit_save_button():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        html = client.get("/collection").get_data(as_text=True)
    assert 'id="save-collection"' in html
