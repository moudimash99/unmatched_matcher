import app as app_module


def test_owned_sets_default_buttons_rendered():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="save-default-sets-btn"' in html
    assert 'id="load-default-sets-btn"' in html
