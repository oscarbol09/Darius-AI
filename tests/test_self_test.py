"""
test_self_test.py — Pruebas unitarias para la suite de auto-certificación hermética
"""

from unittest.mock import patch

from self_test import (
    CheckResult,
    check_obsidian_vault,
    check_tool_contracts,
    check_vision_pipeline,
    check_win32_topology,
    run_self_test,
)


def test_check_win32_topology_mocked():
    with patch("self_test.get_monitor_rects", return_value=[(0, 0, 1920, 1080)]), \
         patch("self_test.get_monitor_count", return_value=1):
        res = check_win32_topology()
        assert res.status == "PASS"
        assert "1 monitor(es)" in res.detail


def test_check_obsidian_vault_mocked():
    from unittest.mock import MagicMock, PropertyMock
    with patch("obsidian_brain.ObsidianBrain.vault_path", new_callable=PropertyMock) as mock_vault:
        mock_vault.return_value = MagicMock(exists=lambda: True)
        res = check_obsidian_vault()
        assert res.status == "PASS"


def test_check_vision_pipeline_mocked():
    mock_ret = ("fake_b64", {"width": 1280, "height": 720, "size_bytes": 50000})
    with patch("self_test.vision_engine.capture_screen_base64", return_value=mock_ret):
        res = check_vision_pipeline()
        assert res.status == "PASS"
        assert "1280x720" in res.detail


def test_check_tool_contracts():
    res = check_tool_contracts()
    assert res.status == "PASS"
    assert "acciones del SO" in res.detail


def test_run_self_test_structure():
    results = run_self_test()
    assert isinstance(results, list)
    assert len(results) >= 6
    for r in results:
        assert isinstance(r, CheckResult)
        assert r.status in ("PASS", "WARN", "FAIL")
