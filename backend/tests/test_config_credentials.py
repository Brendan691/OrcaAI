"""Credential-isolation regression tests."""

from src.core.config import Settings


def _settings(**overrides) -> Settings:
    values = {
        "DASHSCOPE_API_KEY": "",
        "DASHSCOPE_BASE_URL": "https://example.invalid/dashscope",
        "QWEN38_API_KEY": "",
        "QWEN38_BASE_URL": "",
        "QWEN38_MODEL": "",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_qwen38_credential_is_not_reused_for_general_services():
    settings = _settings(
        QWEN38_API_KEY="qwen-only-key",
        QWEN38_BASE_URL="https://example.invalid/qwen",
        QWEN38_MODEL="qwen3.8-max",
    )

    assert settings.qwen38_complete is True
    assert settings.has_api_key is True
    assert settings.has_dashscope_api_key is False


def test_incomplete_qwen38_credential_does_not_enable_llm():
    settings = _settings(
        DASHSCOPE_API_KEY="dashscope-key",
        QWEN38_API_KEY="partial-key",
    )

    assert settings.qwen38_configured is True
    assert settings.qwen38_complete is False
    assert settings.has_partial_qwen38_config is True
    assert settings.has_api_key is False
    assert settings.has_dashscope_api_key is True
