"""Unit tests for LexiconOracle (curated tech vocabulary, J.A.R.V.I.S data loader,
fuzzy matching, online fallback, and Butler vocal TTS).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

# Ensure src is in sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from src.darius_ai.core.lexicon_oracle import LexiconEntry, LexiconOracle
except ImportError:
    from darius_ai.core.lexicon_oracle import LexiconEntry, LexiconOracle  # type: ignore[import-not-found,no-redef]


# Sample dictionary API payload for tests
SAMPLE_DICTIONARY_API_RESPONSE = [
    {
        "word": "algorithm",
        "phonetic": "/ˈæl.ɡə.ɹɪð.əm/",
        "phonetics": [
            {"text": "/ˈæl.ɡə.ɹɪð.əm/", "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/algorithm-us.mp3"}
        ],
        "meanings": [
            {
                "partOfSpeech": "noun",
                "definitions": [
                    {
                        "definition": "A precise step-by-step plan for a computational procedure.",
                        "synonyms": ["procedure", "formula", "recipe"],
                        "antonyms": [],
                    }
                ],
                "synonyms": ["procedure", "rule"],
                "antonyms": [],
            }
        ],
    }
]


# ============================================================================
# LexiconEntry Dataclass Tests
# ============================================================================


def test_lexicon_entry_dataclass_fields():
    """Verify LexiconEntry fields and default factory values."""
    entry = LexiconEntry(
        word="entropy",
        definitions=["A measure of thermal energy unavailable for doing mechanical work."],
        synonyms=["disorder", "randomness"],
        antonyms=["order"],
        phonetic="/ˈɛn.tɹə.pi/",
        source="local",
    )
    assert entry.word == "entropy"
    assert len(entry.definitions) == 1
    assert entry.synonyms == ["disorder", "randomness"]
    assert entry.antonyms == ["order"]
    assert entry.phonetic == "/ˈɛn.tɹə.pi/"
    assert entry.source == "local"


def test_lexicon_entry_defaults():
    """Verify default values for synonyms, antonyms, phonetic, and source."""
    entry = LexiconEntry(
        word="qubit",
        definitions=["A basic unit of quantum information."],
    )
    assert entry.synonyms == []
    assert entry.antonyms == []
    assert entry.phonetic == ""
    assert entry.source == "local"


# ============================================================================
# Curated Local Dictionary Tests (EN & ES)
# ============================================================================


def test_lookup_curated_english_term():
    """Verify built-in curated vocabulary retrieves English tech and science definitions."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    found, entry, suggestions = oracle.lookup("algorithm")

    assert found is True
    assert entry is not None
    assert entry.word.lower() == "algorithm"
    assert len(entry.definitions) >= 1
    assert any("step" in d.lower() or "instruction" in d.lower() or "proced" in d.lower() for d in entry.definitions)
    assert suggestions == []


def test_lookup_curated_spanish_term():
    """Verify built-in curated vocabulary retrieves Spanish definitions."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    found, entry, suggestions = oracle.lookup("algoritmo")

    assert found is True
    assert entry is not None
    assert entry.word.lower() == "algoritmo"
    assert len(entry.definitions) >= 1
    assert any("pasos" in d.lower() or "instrucciones" in d.lower() for d in entry.definitions)
    assert suggestions == []


def test_lookup_case_insensitivity_and_whitespace():
    """Verify lookups are case-insensitive and tolerate surrounding whitespace."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    found1, entry1, _ = oracle.lookup("   ALGORITMO  ")
    found2, entry2, _ = oracle.lookup("Artificial Intelligence")

    assert found1 is True and entry1 is not None
    assert found2 is True and entry2 is not None


# ============================================================================
# J.A.R.V.I.S. data.json Loading Tests
# ============================================================================


def test_load_vocabulary_data_json_custom_file(tmp_path):
    """Verify custom data.json file loads and integrates into the in-memory cache."""
    test_data = {
        "cyber core": ["A high-performance energy generator developed for Darius AI."],
        "darius": ["Dynamic Autonomous Realtime Intelligent Utility System."],
    }
    json_path = tmp_path / "custom_darius_data.json"
    json_path.write_text(json.dumps(test_data), encoding="utf-8")

    oracle = LexiconOracle(vocabulary_data_path=str(json_path))
    found, entry, _ = oracle.lookup("cyber core")

    assert found is True
    assert entry is not None
    assert "energy generator" in entry.definitions[0]
    assert entry.source == "vocabulary_data"


def test_load_vocabulary_data_missing_file_handled_gracefully():
    """Verify non-existent vocabulary_data_path does not raise exception."""
    oracle = LexiconOracle(vocabulary_data_path="C:\\non_existent_path\\invalid_data.json")
    # Must still function with built-in dictionary
    found, entry, _ = oracle.lookup("algorithm")
    assert found is True


def test_load_vocabulary_data_corrupted_json_handled_gracefully(tmp_path):
    """Verify corrupted JSON file does not crash the oracle."""
    corrupted_file = tmp_path / "corrupted.json"
    corrupted_file.write_text("{invalid_json_format", encoding="utf-8")

    oracle = LexiconOracle(vocabulary_data_path=str(corrupted_file))
    found, entry, _ = oracle.lookup("algorithm")
    assert found is True


# Retrocompatibilidad
test_load_jarvis_data_json_custom_file = test_load_vocabulary_data_json_custom_file
test_load_jarvis_data_missing_file_handled_gracefully = test_load_vocabulary_data_missing_file_handled_gracefully
test_load_jarvis_data_corrupted_json_handled_gracefully = test_load_vocabulary_data_corrupted_json_handled_gracefully


# ============================================================================
# Online Dictionary API Fallback Tests
# ============================================================================


@patch("src.darius_ai.core.lexicon_oracle.httpx.get")
def test_online_dictionaryapi_success_and_caching(mock_get):
    """Verify fallback to DictionaryAPI when term is not present locally."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_DICTIONARY_API_RESPONSE
    mock_get.return_value = mock_resp

    oracle = LexiconOracle(load_vocabulary_data=False)
    # Use a word unlikely to be in curated local set
    found, entry, suggestions = oracle.lookup("serendipity")

    assert found is True
    assert entry is not None
    assert entry.source == "dictionaryapi"
    assert entry.phonetic == "/ˈæl.ɡə.ɹɪð.əm/"
    assert len(entry.definitions) >= 1
    assert "procedure" in entry.synonyms

    # Verify cached on second lookup
    call_count = mock_get.call_count
    found2, entry2, _ = oracle.lookup("serendipity")
    assert found2 is True
    assert mock_get.call_count == call_count


@patch("src.darius_ai.core.lexicon_oracle.httpx.get")
def test_online_dictionaryapi_network_failure_resilience(mock_get):
    """Verify HTTP failure or timeout does not raise unhandled exception."""
    mock_get.side_effect = httpx.ConnectTimeout("Request timed out")

    oracle = LexiconOracle(load_vocabulary_data=False)
    # Searching non-curated word with network down
    found, entry, suggestions = oracle.lookup("unobtainium_random_word_99")

    assert found is False
    assert entry is None
    assert isinstance(suggestions, list)


def test_anti_ssrf_validator_blocks_malicious_lookup():
    """Verify AntiSSRFValidator protects against SSRF injection in lookup."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    # Injected host / path attempt
    safe, _ = oracle.is_safe_lookup_target("http://169.254.169.254/latest/meta-data")
    assert safe is False


# ============================================================================
# Fuzzy Matching Tests (difflib)
# ============================================================================


def test_fuzzy_matching_close_matches():
    """Verify close spelling mistakes return fuzzy suggestions."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    # Misspelled term
    found, entry, suggestions = oracle.lookup("algoritm")

    assert found is False
    assert entry is None
    assert len(suggestions) >= 1
    assert "algorithm" in [s.lower() for s in suggestions] or "algoritmo" in [s.lower() for s in suggestions]


def test_unknown_word_no_close_matches():
    """Verify complete gibberish returns found=False with empty suggestions."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    with patch("src.darius_ai.core.lexicon_oracle.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        found, entry, suggestions = oracle.lookup("zzzxxyyqwerty1234567")

        assert found is False
        assert entry is None
        assert suggestions == []


# ============================================================================
# J.A.R.V.I.S. Butler Vocal Definition Formatting Tests
# ============================================================================


def test_format_vocal_definition_with_full_entry():
    """Verify Butler TTS format with complete definition, phonetic, and synonyms."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    entry = LexiconEntry(
        word="ciberseguridad",
        definitions=["Práctica de proteger sistemas y redes frente a ataques cibernéticos maliciosos."],
        synonyms=["seguridad informática", "infosec"],
        antonyms=[],
        phonetic="si.βeɾ.se.ɣu.ɾiˈðað",
        source="local",
    )

    speech = oracle.format_vocal_definition(entry)

    assert "señor" in speech.lower()
    assert "ciberseguridad" in speech.lower()
    assert "proteger sistemas" in speech.lower()
    assert "seguridad informática" in speech


def test_format_vocal_definition_none_entry():
    """Verify vocal response when entry is None."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    speech = oracle.format_vocal_definition(None)

    assert "señor" in speech.lower()
    assert "no dispongo" in speech.lower() or "no he encontrado" in speech.lower()


def test_lookup_empty_or_whitespace():
    """Verify empty or blank word returns found=False with None entry and empty list."""
    oracle = LexiconOracle(load_vocabulary_data=False)
    assert oracle.lookup("") == (False, None, [])
    assert oracle.lookup("    ") == (False, None, [])


def test_is_safe_lookup_target_empty():
    """Verify is_safe_lookup_target returns False on empty string."""
    safe, msg = LexiconOracle.is_safe_lookup_target("")
    assert safe is False
    assert "empty" in msg.lower()


def test_load_vocabulary_data_string_values(tmp_path):
    """Verify data.json entries with plain string values instead of lists are handled."""
    test_data = {"monolith": "A large single upright block of stone or large software system."}
    json_path = tmp_path / "str_data.json"
    json_path.write_text(json.dumps(test_data), encoding="utf-8")

    oracle = LexiconOracle(vocabulary_data_path=str(json_path))
    found, entry, _ = oracle.lookup("monolith")

    assert found is True
    assert entry is not None
    assert "upright block" in entry.definitions[0]


# Retrocompatibilidad
test_load_jarvis_data_string_values = test_load_vocabulary_data_string_values


@patch("src.darius_ai.core.lexicon_oracle.httpx.get")
def test_online_dictionaryapi_phonetic_fallback_and_antonyms(mock_get):
    """Verify phonetic extracted from phonetics list when top-level phonetic is missing."""
    mock_payload = [
        {
            "word": "entropy",
            "phonetic": None,
            "phonetics": [{"text": "/ˈɛn.tɹə.pi/"}],
            "meanings": [
                {
                    "partOfSpeech": "noun",
                    "antonyms": ["order"],
                    "synonyms": ["disorder"],
                    "definitions": [
                        {
                            "definition": "Lack of order or predictability.",
                            "synonyms": ["randomness"],
                            "antonyms": ["pattern"],
                        }
                    ],
                }
            ],
        }
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload
    mock_get.return_value = mock_resp

    oracle = LexiconOracle(load_vocabulary_data=False)
    # Search non-curated term to trigger online
    found, entry, _ = oracle.lookup("entropy_variant_ext")

    assert found is True
    assert entry is not None
    assert entry.phonetic == "/ˈɛn.tɹə.pi/"
    assert "order" in entry.antonyms
    assert "pattern" in entry.antonyms
    assert "randomness" in entry.synonyms


@patch("src.darius_ai.core.lexicon_oracle.httpx.get")
def test_online_dictionaryapi_empty_data_handled(mock_get):
    """Verify empty JSON list from dictionary API returns None."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_get.return_value = mock_resp

    oracle = LexiconOracle(load_vocabulary_data=False)
    entry = oracle._query_dictionary_api("empty_term")
    assert entry is None

