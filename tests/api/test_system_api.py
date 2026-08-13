def test_system_config_exposes_openrouter_without_secret(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-leak")
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model:free")

    response = client.get('/api/system/config')

    assert response.status_code == 200
    payload = response.get_json()
    provider = payload["summary_providers"]["openrouter"]
    assert provider == {
        "configured": True,
        "external": True,
        "default_model": "vendor/model:free",
        "supports_custom_model": True,
    }
    assert payload["task_providers"]["openrouter"] == provider
    assert "must-not-leak" not in response.get_data(as_text=True)


def test_system_config_exposes_curated_openai_56_models(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4")

    response = client.get('/api/system/config')

    assert response.status_code == 200
    provider = response.get_json()["task_providers"]["openai"]
    assert provider["models"] == [
        "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
    ]
    assert provider["default_model"] == "gpt-5.6-luna"
    assert "gpt-5.4" not in response.get_data(as_text=True)
    assert "must-not-leak" not in response.get_data(as_text=True)


def test_openrouter_models_endpoint_does_not_expose_key(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-leak")
    monkeypatch.setattr("backend.api.system.get_curated_models", lambda: [{
        "id": "vendor/model", "name": "Model", "input_price": 1,
        "output_price": 2, "price_tier": "Balanced",
    }])

    response = client.get('/api/system/openrouter-models')

    assert response.status_code == 200
    assert response.get_json()["models"][0]["price_tier"] == "Balanced"
    assert "must-not-leak" not in response.get_data(as_text=True)
