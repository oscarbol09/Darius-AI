"""Tests unitarios para config_loader.py"""



from config_loader import _DEFAULTS, _SCHEMA, _deep_merge, _validate_types


class TestValidateTypes:
    def test_valid_types_pass_unchanged(self):
        data = {
            "gemini": {
                "model": "gemini-pro", "max_tokens": 500,
                "temperature": 0.5, "history_turns": 5,
            },
        }
        result = _validate_types(data, _SCHEMA)
        assert result["gemini"]["max_tokens"] == 500
        assert result["gemini"]["temperature"] == 0.5

    def test_wrong_type_falls_back_to_default(self):
        data = {
            "gemini": {"max_tokens": "ochocientos", "temperature": 0.7},
        }
        result = _validate_types(data, _SCHEMA)
        assert isinstance(result["gemini"]["max_tokens"], int)
        assert result["gemini"]["max_tokens"] == 800

    def test_missing_key_gets_default(self):
        result = _validate_types({}, _SCHEMA)
        assert "assistant" in result
        assert result["assistant"]["name"] == "darius"


class TestDeepMerge:
    def test_override_nested_key(self):
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"b": 99}}
        result = _deep_merge(base, override)
        assert result["a"]["b"] == 99
        assert result["a"]["c"] == 2

    def test_new_top_level_key(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 2


class TestDefaults:
    def test_gemini_max_tokens_is_800(self):
        assert _DEFAULTS["gemini"]["max_tokens"] == 800

    def test_all_schema_keys_have_defaults(self):
        for key, expected_type in _SCHEMA.items():
            if isinstance(expected_type, dict):
                for subkey, _ in expected_type.items():
                    assert subkey in _DEFAULTS.get(key, {}), f"Falta default para {key}.{subkey}"
            else:
                assert key in _DEFAULTS, f"Falta default para {key}"


class TestConfigLive:
    def test_cfg_imports_without_error(self):
        from config_loader import cfg
        assert cfg.assistant_name == "darius"
        assert cfg.gemini_max_tokens == 800
        assert cfg.gemini_model == "gemini-2.5-flash"

    def test_cfg_get_returns_default_for_missing(self):
        from config_loader import cfg
        assert cfg.get("nonexistent", default="fallback") == "fallback"

    def test_cfg_set_updates_and_persists(self):
        from config_loader import cfg
        original = cfg.user_name
        cfg.set("TestUser", "assistant", "user_name")
        assert cfg.user_name == "TestUser"
        cfg.set(original, "assistant", "user_name")
        assert original == cfg.user_name
