from backend.services import openrouter_catalog


def _reset_cache():
    openrouter_catalog._cache.update(expires_at=0.0, models=None)


def test_curated_catalog_enriches_prices_and_tier(monkeypatch):
    _reset_cache()
    monkeypatch.delenv("OPENROUTER_CURATED_MODELS", raising=False)
    monkeypatch.setattr(openrouter_catalog, "_fetch_catalog", lambda: [{
        "id": "deepseek/deepseek-v4-flash-0731",
        "name": "DeepSeek: V4 Flash",
        "pricing": {"prompt": "0.0000003", "completion": "0.0000012"},
    }])

    models = openrouter_catalog.get_curated_models()

    assert len(models) == 10
    assert models[0] == {
        "id": "deepseek/deepseek-v4-flash-0731",
        "name": "DeepSeek: V4 Flash",
        "input_price": 0.3,
        "output_price": 1.2,
        "price_tier": "Economy",
    }


def test_curated_catalog_falls_back_without_network(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(openrouter_catalog, "_fetch_catalog", lambda: (_ for _ in ()).throw(OSError()))

    models = openrouter_catalog.get_curated_models()

    assert models[0]["id"] == "deepseek/deepseek-v4-flash-0731"
    assert models[0]["input_price"] is None


def test_custom_curated_models_are_limited_to_ten(monkeypatch):
    _reset_cache()
    monkeypatch.setenv("OPENROUTER_CURATED_MODELS", ",".join(f"vendor/model-{i}" for i in range(12)))
    monkeypatch.setattr(openrouter_catalog, "_fetch_catalog", lambda: [])

    assert len(openrouter_catalog.get_curated_models()) == 10
