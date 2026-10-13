"""
science_oracle.py — Oráculo Científico y Motor de Consultas Enciclopédicas de DARIUS AI.
========================================================================================
Proporciona recuperación ultrarrápida de resúmenes enciclopédicos mediante la REST API de Wikipedia,
así como reconocimiento determinista y cálculo de constantes físicas fundamentales y conversiones
de unidades técnicas y aeronáuticas formateadas para voz (TTS) con cadencia de mayordomo.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def _format_number_es(val: float, decimals: int = 2) -> str:
    """Formatea un número con separadores legibles en español (punto para miles, coma o punto para decimales)."""
    formatted = f"{val:,.{decimals}f}"
    # Invertir convención anglosajona: comas a puntos para miles
    parts = formatted.split(".")
    thousands = parts[0].replace(",", ".")
    if len(parts) > 1 and int(parts[1]) != 0:
        return f"{thousands}.{parts[1]}"
    return thousands


class ScienceOracle:
    """Oráculo científico y de conocimiento empírico para DARIUS."""

    USER_AGENT: ClassVar[str] = "DariusAI/1.0 (Voice Assistant; Personal Engineering System; Wikipedia REST API)"
    API_URL_TEMPLATE: ClassVar[str] = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{query}"

    # Constantes físicas deterministas y exactas (CODATA / BIPM)
    PHYSICAL_CONSTANTS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (
            re.compile(
                r"\b(velocidad de la luz|speed of light|velocidad luz|constante c)\b",
                re.IGNORECASE,
            ),
            "La velocidad de la luz en el vacío es de exactamente 299.792.458 metros por segundo, {user_name}.",
        ),
        (
            re.compile(
                r"\b(constante reducida de planck|planck reducida|h barra|h-bar)\b",
                re.IGNORECASE,
            ),
            "La constante reducida de Planck equivale a 1.054 por 10 a la menos 34 julios por segundo, {user_name}.",
        ),
        (
            re.compile(
                r"\b(constante de planck|constante planck|cu[aá]nto vale h)\b",
                re.IGNORECASE,
            ),
            "La constante de Planck equivale a 6.626 por 10 a la menos 34 julios por segundo, {user_name}.",
        ),
        (
            re.compile(
                r"\b(gravitaci[oó]n universal|constante gravitacional|constante de gravitaci[oó]n|constante g)\b",
                re.IGNORECASE,
            ),
            "La constante de gravitación universal es de 6.674 por 10 a la menos 11 metros cúbicos "
            "por kilogramo y segundo al cuadrado, {user_name}.",
        ),
        (
            re.compile(
                r"\b(masa del electr[oó]n|masa de un electr[oó]n|electron mass)\b",
                re.IGNORECASE,
            ),
            "La masa en reposo del electrón es de 9.109 por 10 a la menos 31 kilogramos, {user_name}.",
        ),
        (
            re.compile(
                r"\b(masa del prot[oó]n|masa de un prot[oó]n|proton mass)\b",
                re.IGNORECASE,
            ),
            "La masa en reposo del protón es de 1.672 por 10 a la menos 27 kilogramos, {user_name}.",
        ),
        (
            re.compile(
                r"\b(n[uú]mero de avogadro|constante de avogadro|avogadro)\b",
                re.IGNORECASE,
            ),
            "El número de Avogadro es de 6.022 por 10 a la 23 entidades por mol, {user_name}.",
        ),
        (
            re.compile(
                r"\b(constante de boltzmann|boltzmann)\b",
                re.IGNORECASE,
            ),
            "La constante de Boltzmann es de 1.380 por 10 a la menos 23 julios por kelvin, {user_name}.",
        ),
        (
            re.compile(
                r"\b(carga elemental|carga del electr[oó]n|carga de un electr[oó]n)\b",
                re.IGNORECASE,
            ),
            "La magnitud de la carga elemental es de 1.602 por 10 a la menos 19 culombios, {user_name}.",
        ),
        (
            re.compile(
                r"\b(gravedad terrestre|gravedad en la tierra|"
                r"aceleraci[oó]n de la gravedad|aceleracion de la gravedad)\b",
                re.IGNORECASE,
            ),
            "La aceleración estándar de la gravedad terrestre es de 9.806 metros por segundo al cuadrado, {user_name}.",
        ),
        (
            re.compile(
                r"\b(gases ideales|constante de los gases|constante universal de los gases)\b",
                re.IGNORECASE,
            ),
            "La constante universal de los gases ideales es de 8.314 julios por mol y kelvin, {user_name}.",
        ),
        (
            re.compile(
                r"\b(permitividad del vac[ií]o|permitividad en el vac[ií]o)\b",
                re.IGNORECASE,
            ),
            "La permitividad del vacío es de 8.854 por 10 a la menos 12 faradios por metro, {user_name}.",
        ),
        (
            re.compile(
                r"\b(permeabilidad del vac[ií]o|permeabilidad magn[eé]tica del vac[ií]o)\b",
                re.IGNORECASE,
            ),
            "La permeabilidad magnética del vacío es de 1.256 por 10 a la menos 6 newtons por amperio "
            "al cuadrado, {user_name}.",
        ),
        (
            re.compile(
                r"\b(stefan-boltzmann|stefan boltzmann)\b",
                re.IGNORECASE,
            ),
            "La constante de Stefan-Boltzmann es de 5.670 por 10 a la menos 8 vatios por metro cuadrado "
            "y kelvin a la cuarta potencia, {user_name}.",
        ),
        (
            re.compile(
                r"\b(estructura fina)\b",
                re.IGNORECASE,
            ),
            "La constante de estructura fina equivale aproximadamente a 1 sobre 137.036, {user_name}.",
        ),
    ]

    def __init__(self, user_name: str = "señor", timeout: float = 8.0) -> None:
        """Inicializa el oráculo con el tratamiento protocolar y tiempo límite de red."""
        self.user_name = user_name
        self.timeout = timeout

    def get_entity_summary(self, query: str, lang: str = "es") -> tuple[bool, str]:
        """Consulta la API REST de Wikipedia y devuelve un extracto conciso (<2 oraciones) para TTS."""
        term = query.strip()
        if not term:
            return False, f"La consulta enciclopédica no contiene un término válido, {self.user_name}."

        clean_term = term.replace(" ", "_")
        url = self.API_URL_TEMPLATE.format(lang=lang, query=quote(clean_term, safe=""))
        headers = {"User-Agent": self.USER_AGENT, "Accept": "application/json"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=headers)

            if response.status_code == 404:
                return (
                    False,
                    f"No he localizado registros enciclopédicos sobre '{term}', {self.user_name}.",
                )

            if response.status_code != 200:
                return (
                    False,
                    f"El repositorio enciclopédico devolvió un código anómalo ({response.status_code}), "
                    f"{self.user_name}.",
                )

            data = response.json()
            title = data.get("title", term)
            extract = data.get("extract", "").strip()

            if not extract:
                return (
                    False,
                    f"No he localizado información descriptiva concluyente sobre '{term}', {self.user_name}.",
                )

            # Tomar máximo las dos primeras oraciones para garantizar concisión de síntesis de voz (<2 frases)
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extract) if s.strip()]
            selected = " ".join(sentences[:2]).rstrip(". ")

            response_text = f"Según los registros sobre {title}, {selected}, {self.user_name}."
            return True, response_text

        except (httpx.RequestError, httpx.TimeoutException, OSError) as exc:
            logger.warning("Fallo al conectar con la API de Wikipedia para '%s': %s", term, exc)
            return (
                False,
                f"Disculpe, {self.user_name}. La conexión con el repositorio enciclopédico "
                f"no está disponible en este momento.",
            )
        except Exception as exc:
            logger.error("Error inesperado en consulta enciclopédica: %s", exc)
            return False, f"Se ha producido una anomalía inesperada al consultar el oráculo, {self.user_name}."

    def get_constant_or_conversion(self, query: str) -> tuple[bool, str]:
        """Reconoce constantes físicas y efectúa conversiones de unidades directas para lectura por voz."""
        clean_q = query.strip()
        if not clean_q:
            return False, f"No se ha especificado ninguna magnitud para calcular, {self.user_name}."

        # 1. Comprobación de constantes físicas
        for pattern, response_template in self.PHYSICAL_CONSTANTS:
            if pattern.search(clean_q):
                return True, response_template.format(user_name=self.user_name)

        # 2. Conversiones de unidades
        conversion_result = self._evaluate_unit_conversion(clean_q)
        if conversion_result is not None:
            return True, conversion_result

        return (
            False,
            f"No poseo un algoritmo determinista para esa magnitud en mi base local, {self.user_name}.",
        )

    def _evaluate_unit_conversion(self, query: str) -> str | None:
        """Evalúa patrones de conversión de unidades comunes y devuelve la respuesta formateada."""
        # Mach a km/h: "3 mach a km/h" o "mach 1 a km/h"
        match = re.search(r"(?:convertir\s+)?(\d+(?:\.\d+)?)\s*mach\s*(?:a|en)\s*km/?h", query, re.IGNORECASE)
        if not match:
            match = re.search(r"mach\s*(\d+(?:\.\d+)?)\s*(?:a|en)\s*km/?h", query, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            res = val * 1234.8
            formatted_res = _format_number_es(res, 1)
            return (
                f"{val:g} Mach equivalen aproximadamente a {formatted_res} "
                f"kilómetros por hora a nivel del mar, {self.user_name}."
            )

        # Joules a eV: "10 julios a electronvoltios"
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:julios?|joules?|j)\s*(?:a|en)\s*(?:electronvoltios?|ev)",
            query,
            re.IGNORECASE,
        )
        if match:
            val = float(match.group(1))
            res = val / 1.602176634e-19
            # Formatear notación científica para voz
            exponent = 19
            base = val / 1.602176634
            return (
                f"{val:g} julios equivalen a {base:.3f} por 10 a la {exponent} "
                f"electronvoltios, {self.user_name}."
            )

        # eV a Joules: "5 ev a julios"
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:electronvoltios?|ev)\s*(?:a|en)\s*(?:julios?|joules?|j)",
            query,
            re.IGNORECASE,
        )
        if match:
            val = float(match.group(1))
            base = val * 1.602176634
            return (
                f"{val:g} electronvoltios equivalen a {base:.2f} por 10 a la menos 19 "
                f"julios, {self.user_name}."
            )

        # Años luz a km: "2 años luz a kilómetros"
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*a[ñn]os?\s*luz\s*(?:a|en)\s*(?:k[ií]l[oó]metros?|km)",
            query,
            re.IGNORECASE,
        )
        if match:
            val = float(match.group(1))
            base = val * 0.946073
            return (
                f"{val:g} años luz equivalen aproximadamente a {base:.3f} por 10 a la 13 "
                f"kilómetros, {self.user_name}."
            )

        # Unidad astronómica a km: "1 unidad astronómica a km"
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:unidad(?:es)?\s*astron[oó]micas?|ua|au)\s*(?:a|en)\s*(?:k[ií]l[oó]metros?|km)",
            query,
            re.IGNORECASE,
        )
        if match:
            val = float(match.group(1))
            res = val * 149597870.7
            formatted_res = _format_number_es(res, 0)
            return (
                f"{val:g} unidad astronómica equivale a {formatted_res} "
                f"kilómetros, {self.user_name}."
            )

        # PSI a bar: "100 psi a bar"
        match = re.search(r"(\d+(?:\.\d+)?)\s*psi\s*(?:a|en)\s*bar", query, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            res = val * 0.0689476
            return f"{val:g} psi equivalen aproximadamente a {res:.2f} bar, {self.user_name}."

        # Nudos a km/h: "50 nudos a km/h"
        match = re.search(r"(\d+(?:\.\d+)?)\s*nudos?\s*(?:a|en)\s*km/?h", query, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            res = val * 1.852
            return f"{val:g} nudos equivalen a {res:.1f} kilómetros por hora, {self.user_name}."

        # Celsius a Fahrenheit: "100 celsius a fahrenheit"
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*celsius\s*(?:a|en)\s*fahrenheit", query, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            res = (val * 9 / 5) + 32
            return f"{val:g} grados Celsius equivalen a {res:g} grados Fahrenheit, {self.user_name}."

        # Celsius a Kelvin: "0 celsius a kelvin"
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*celsius\s*(?:a|en)\s*kelvin", query, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            res = val + 273.15
            return f"{val:g} grados Celsius equivalen a {res:.2f} Kelvin, {self.user_name}."

        # Millas a km: "10 millas a km"
        match = re.search(r"(\d+(?:\.\d+)?)\s*millas?\s*(?:a|en)\s*(?:k[ií]l[oó]metros?|km)", query, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            res = val * 1.60934
            return f"{val:g} millas equivalen a {res:.2f} kilómetros, {self.user_name}."

        # Caballos de fuerza a vatios: "100 caballos de fuerza a vatios"
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:caballos?\s*de\s*fuerza|hp|cv)\s*(?:a|en)\s*(?:vatios|watts?|w)",
            query,
            re.IGNORECASE,
        )
        if match:
            val = float(match.group(1))
            res = val * 745.7
            formatted_res = _format_number_es(res, 0)
            return (
                f"{val:g} caballos de fuerza equivalen a {formatted_res} "
                f"vatios, {self.user_name}."
            )

        return None
