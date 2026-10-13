"""
test_science_oracle.py — Pruebas unitarias para ScienceOracle (Wikipedia REST API y constantes físicas).
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.darius_ai.core.science_oracle import ScienceOracle


class TestScienceOracleEntitySummary:
    """Verifica la consulta y resumen enciclopédico vía Wikipedia REST API."""

    @patch("src.darius_ai.core.science_oracle.httpx.Client")
    def test_get_entity_summary_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Nikola Tesla",
            "extract": "Nikola Tesla fue un inventor, ingeniero eléctrico y mecánico serbio-estadounidense.",
        }
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        oracle = ScienceOracle()
        success, text = oracle.get_entity_summary("Nikola Tesla", lang="es")

        assert success is True
        assert "Nikola Tesla" in text
        assert "inventor" in text
        assert "señor" in text.lower()
        # Verify TTS conciseness: <= 2 sentences
        sentence_count = len([s for s in text.split(".") if s.strip()])
        assert sentence_count <= 3

    @patch("src.darius_ai.core.science_oracle.httpx.Client")
    def test_get_entity_summary_not_found_404(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        oracle = ScienceOracle()
        success, text = oracle.get_entity_summary("EntidadInexistente123456789")

        assert success is False
        assert "no he localizado" in text.lower() or "registros" in text.lower()
        assert "señor" in text.lower()

    @patch("src.darius_ai.core.science_oracle.httpx.Client")
    def test_get_entity_summary_network_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value = mock_client

        oracle = ScienceOracle()
        success, text = oracle.get_entity_summary("Albert Einstein")

        assert success is False
        assert "conexión" in text.lower() or "error" in text.lower()
        assert "señor" in text.lower()

    @patch("src.darius_ai.core.science_oracle.httpx.Client")
    def test_get_entity_summary_empty_extract(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Algo Sin Extracto",
            "extract": "",
        }
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        oracle = ScienceOracle()
        success, text = oracle.get_entity_summary("Algo Sin Extracto")

        assert success is False
        assert "no he localizado" in text.lower() or "información" in text.lower()

    def test_get_entity_summary_empty_query(self):
        oracle = ScienceOracle()
        success, text = oracle.get_entity_summary("   ")
        assert success is False
        assert "señor" in text.lower()

    @patch("src.darius_ai.core.science_oracle.httpx.Client")
    def test_get_entity_summary_server_error_500(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        oracle = ScienceOracle()
        success, text = oracle.get_entity_summary("ErrorServer")
        assert success is False
        assert "500" in text

    @patch("src.darius_ai.core.science_oracle.httpx.Client")
    def test_get_entity_summary_unexpected_exception(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__.side_effect = RuntimeError("Crash fatal")
        mock_client_cls.return_value = mock_client

        oracle = ScienceOracle()
        success, text = oracle.get_entity_summary("TestCrash")
        assert success is False
        assert "anomalía inesperada" in text.lower()


class TestScienceOraclePhysicalConstants:
    """Verifica el reconocimiento y respuesta de constantes físicas fundamentales."""

    @pytest.mark.parametrize(
        "query,expected_keyword",
        [
            ("cuál es la velocidad de la luz", "299"),
            ("speed of light", "299"),
            ("dime la constante de planck", "6.626"),
            ("cuál es la constante reducida de planck", "1.054"),
            ("constante de gravitacion universal", "6.674"),
            ("masa del electrón", "9.109"),
            ("masa del protón", "1.672"),
            ("número de avogadro", "6.022"),
            ("constante de boltzmann", "1.380"),
            ("carga elemental del electrón", "1.602"),
            ("gravedad en la tierra", "9.8"),
            ("constante de los gases ideales", "8.314"),
        ],
    )
    def test_recognized_constants(self, query, expected_keyword):
        oracle = ScienceOracle()
        success, text = oracle.get_constant_or_conversion(query)
        assert success is True, f"Failed to match constant for '{query}'"
        assert expected_keyword in text
        assert "señor" in text.lower()
        # Voice TTS conciseness check
        assert len(text) < 250
        assert not any(symbol in text for symbol in ["\\frac", "\\cdot", "\\times"])


class TestScienceOracleUnitConversions:
    """Verifica conversiones directas de unidades científicas y aeronáuticas."""

    @pytest.mark.parametrize(
        "query,expected_part",
        [
            ("convertir 3 mach a km/h", "3.704"),  # 3 * 1234.8 = 3704.4 km/h
            ("mach 1 a km/h", "1.234"),
            ("10 julios a electronvoltios", "6.24"),  # 10 / 1.602e-19 = 6.241e19 eV
            ("5 ev a julios", "8.01"),  # 5 * 1.602e-19 J
            ("2 años luz a kilómetros", "1.892"),  # 2 * 9.461e12 km
            ("1 unidad astronómica a km", "149.597"),  # ~149.597.870 km
            ("100 psi a bar", "6.89"),  # 100 * 0.0689476 = 6.89 bar
            ("50 nudos a km/h", "92.6"),  # 50 * 1.852 = 92.6 km/h
            ("100 celsius a fahrenheit", "212"),
            ("0 celsius a kelvin", "273.15"),
            ("10 millas a km", "16.09"),
            ("100 caballos de fuerza a vatios", "74.5"),
        ],
    )
    def test_recognized_conversions(self, query, expected_part):
        oracle = ScienceOracle()
        success, text = oracle.get_constant_or_conversion(query)
        assert success is True, f"Failed to convert '{query}'"
        assert expected_part in text
        assert "señor" in text.lower()
        assert len(text) < 250

    def test_unrecognized_query(self):
        oracle = ScienceOracle()
        success, text = oracle.get_constant_or_conversion("cómo preparar una paella")
        assert success is False
        assert "señor" in text.lower()

    def test_empty_query_constant_or_conversion(self):
        oracle = ScienceOracle()
        success, text = oracle.get_constant_or_conversion("   ")
        assert success is False
        assert "señor" in text.lower()
