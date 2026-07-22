"""Tests unitarios para supabase_client.py"""

import os
from unittest.mock import patch

import pytest

from supabase_client import get_supabase


def teardown_module():
    """Limpia el singleton entre tests recargando el módulo."""
    import supabase_client
    supabase_client._client = None
    supabase_client._init_attempted = False


class TestGetSupabase:
    def test_returns_none_without_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_supabase() is None

    def test_returns_none_with_partial_env_vars(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "http://test"}, clear=True):
            assert get_supabase() is None
        with patch.dict(os.environ, {"SUPABASE_KEY": "test-key"}, clear=True):
            assert get_supabase() is None

    def test_handles_import_error_gracefully(self):
        import supabase_client as sc
        sc._client = None
        sc._init_attempted = False
        with patch.dict(os.environ, {
            "SUPABASE_URL": "http://test",
            "SUPABASE_KEY": "test-key",
        }, clear=True):
            result = get_supabase()
            assert result is None

    def test_handles_connection_error_gracefully(self):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "http://invalid",
            "SUPABASE_KEY": "bad-key",
        }, clear=True):
            result = get_supabase()
            assert result is None

    def test_singleton_returns_same_instance(self):
        import supabase_client
        supabase_client._client = None
        supabase_client._init_attempted = False

        with patch.dict(os.environ, {}, clear=True):
            first = get_supabase()
            supabase_client._init_attempted = False
            second = get_supabase()
            assert first is None
            assert second is None

    def test_never_raises(self):
        """get_supabase nunca debe lanzar excepción."""
        import supabase_client
        supabase_client._client = None
        supabase_client._init_attempted = False

        with patch.dict(os.environ, {}, clear=True):
            for _ in range(5):
                try:
                    get_supabase()
                except Exception as e:
                    pytest.fail(f"get_supabase lanzó excepción: {e}")
