"""
Lexicon Oracle — Curated bilingual dictionary, Darius AI vocabulary loader, online fallback & Butler TTS formatting.
"""

from __future__ import annotations

import difflib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

try:
    from src.darius_ai.core.security_guard import AntiSSRFValidator
except ImportError:
    from darius_ai.core.security_guard import AntiSSRFValidator  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger(__name__)

DEFAULT_DARIUS_VOCAB_PATH = str(Path.home() / ".darius_ai" / "lexicon" / "data.json")
DEFAULT_JARVIS_DATA_PATH = DEFAULT_DARIUS_VOCAB_PATH


@dataclass
class LexiconEntry:
    """Represents a structured dictionary entry with definitions, phonetics, and relations."""

    word: str
    definitions: list[str]
    synonyms: list[str] = field(default_factory=list)
    antonyms: list[str] = field(default_factory=list)
    phonetic: str = ""
    source: str = "local"


class LexiconOracle:
    """Lexical oracle providing curated tech/science terms, Darius vocabulary loading,
    fuzzy matching, and online fallback.
    """

    CURATED_TERMS: dict[str, dict[str, Any]] = {
        # English Curated Technical & Scientific Terms
        "algorithm": {
            "definitions": [
                (
                    "A finite sequence of well-defined computer-implementable instructions "
                    "to solve a problem or compute."
                )
            ],
            "synonyms": ["procedure", "method", "computational recipe"],
            "antonyms": [],
            "phonetic": "/ˈæl.ɡə.ɹɪð.əm/",
        },
        "artificial intelligence": {
            "definitions": [
                (
                    "The intelligence of machines or software capable of perception, "
                    "reasoning, learning, and decision-making."
                )
            ],
            "synonyms": ["machine intelligence", "synthetic cognition"],
            "antonyms": [],
            "phonetic": "/ˌɑː.tɪˈfɪʃ.əl ɪnˈtel.ɪ.dʒəns/",
        },
        "neural network": {
            "definitions": [
                (
                    "A computational model inspired by biological nervous systems, "
                    "consisting of interconnected nodes or layers."
                )
            ],
            "synonyms": ["artificial neural network", "deep learning network"],
            "antonyms": [],
            "phonetic": "/ˈnjʊə.rəl ˈnet.wɜːk/",
        },
        "machine learning": {
            "definitions": [
                (
                    "A branch of artificial intelligence focused on building applications "
                    "that learn from data and improve over time."
                )
            ],
            "synonyms": ["statistical learning", "pattern recognition"],
            "antonyms": [],
            "phonetic": "/məˈʃiːn ˈlɜː.nɪŋ/",
        },
        "deep learning": {
            "definitions": [
                (
                    "A subset of machine learning based on multi-layered artificial "
                    "neural networks with representation learning."
                )
            ],
            "synonyms": ["deep neural learning", "hierarchical learning"],
            "antonyms": [],
            "phonetic": "/diːp ˈlɜː.nɪŋ/",
        },
        "quantum computing": {
            "definitions": [
                (
                    "Computation utilizing quantum mechanics phenomena such as "
                    "superposition and entanglement to execute algorithms."
                )
            ],
            "synonyms": ["quantum computation", "qubit computing"],
            "antonyms": [],
            "phonetic": "/ˈkwɒn.təm kəmˈpjuː.tɪŋ/",
        },
        "compiler": {
            "definitions": [
                (
                    "A specialized program that translates high-level programming "
                    "language code into machine code or bytecode."
                )
            ],
            "synonyms": ["code translator", "assembler"],
            "antonyms": ["interpreter"],
            "phonetic": "/kəmˈpaɪ.lər/",
        },
        "operating system": {
            "definitions": [
                (
                    "Low-level system software that manages computer hardware and "
                    "software resources and provides core services."
                )
            ],
            "synonyms": ["OS", "system platform"],
            "antonyms": [],
            "phonetic": "/ˈɒp.ər.eɪ.tɪŋ ˈsɪs.təm/",
        },
        "cybersecurity": {
            "definitions": [
                (
                    "The practice of protecting electronic systems, networks, devices, "
                    "and data from malicious digital attacks."
                )
            ],
            "synonyms": ["information security", "infosec", "computer security"],
            "antonyms": [],
            "phonetic": "/ˌsaɪ.bə.sɪˈkjʊə.rə.ti/",
        },
        "encryption": {
            "definitions": [
                (
                    "The mathematical transformation of data into ciphertext to render "
                    "it unreadable to unauthorized parties."
                )
            ],
            "synonyms": ["cryptographic encoding", "ciphering"],
            "antonyms": ["decryption", "cleartext"],
            "phonetic": "/ɪnˈkrɪp.ʃən/",
        },
        "api": {
            "definitions": [
                "Application Programming Interface; a set of protocols, routines, and tools for building software."
            ],
            "synonyms": ["interface", "web service endpoint"],
            "antonyms": [],
            "phonetic": "/ˌeɪ.piːˈaɪ/",
        },
        "database": {
            "definitions": [
                "An organized collection of structured information or data stored electronically in a computer system."
            ],
            "synonyms": ["data repository", "datastore"],
            "antonyms": [],
            "phonetic": "/ˈdeɪ.tə.beɪs/",
        },
        "protocol": {
            "definitions": [
                "A formal set of standard rules and conventions that govern data transmission between network devices."
            ],
            "synonyms": ["standard", "communication rule"],
            "antonyms": [],
            "phonetic": "/ˈprəʊ.tə.kɒl/",
        },
        "entropy": {
            "definitions": [
                (
                    "A thermodynamic measure of unavailable thermal energy, or in information theory, "
                    "a measure of unpredictability."
                )
            ],
            "synonyms": ["randomness", "disorder"],
            "antonyms": ["order", "determinism"],
            "phonetic": "/ˈen.trə.pi/",
        },
        "qubit": {
            "definitions": [
                (
                    "The basic unit of information in quantum computing, "
                    "representing a two-state quantum-mechanical system."
                )
            ],
            "synonyms": ["quantum bit"],
            "antonyms": ["classical bit"],
            "phonetic": "/ˈkjuː.bɪt/",
        },
        "python": {
            "definitions": [
                (
                    "A high-level, interpreted programming language with dynamic semantics, "
                    "emphasized readability, and clean syntax."
                )
            ],
            "synonyms": ["Python language"],
            "antonyms": [],
            "phonetic": "/ˈpaɪ.θən/",
        },
        "heuristic": {
            "definitions": [
                (
                    "A practical problem-solving technique or shortcut that is not guaranteed "
                    "to be optimal but suffices immediately."
                )
            ],
            "synonyms": ["rule of thumb", "shortcut"],
            "antonyms": ["exact algorithm"],
            "phonetic": "/hjuˈrɪs.tɪk/",
        },
        "cpu": {
            "definitions": [
                (
                    "Central Processing Unit; the principal hardware component of a computer "
                    "that executes instructions of computer programs."
                )
            ],
            "synonyms": ["processor", "microprocessor", "central processor"],
            "antonyms": [],
            "phonetic": "/ˌsiː.piːˈjuː/",
        },
        # Spanish Curated Technical & Scientific Terms
        "algoritmo": {
            "definitions": [
                (
                    "Conjunto ordenado y finito de instrucciones bien definidas "
                    "que conducen a la resolución de un problema."
                )
            ],
            "synonyms": ["método de cálculo", "procedimiento computacional", "lógica"],
            "antonyms": [],
            "phonetic": "al.ɣoˈɾid.mo",
        },
        "inteligencia artificial": {
            "definitions": [
                (
                    "Campo científico y tecnológico que crea sistemas computacionales "
                    "capaces de emular capacidades cognitivas."
                )
            ],
            "synonyms": ["IA", "inteligencia computacional"],
            "antonyms": [],
            "phonetic": "in.te.liˈxen.sja aɾ.ti.fiˈsjal",
        },
        "red neuronal": {
            "definitions": [
                (
                    "Modelo matemático inspirado en las redes neuronales biológicas "
                    "para aproximar funciones complejas y aprender patrones."
                )
            ],
            "synonyms": ["red neuronal artificial", "arquitectura neuronal"],
            "antonyms": [],
            "phonetic": "reð new.ɾoˈnal",
        },
        "aprendizaje automatico": {
            "definitions": [
                (
                    "Subcampo de la inteligencia artificial que otorga a las máquinas "
                    "la facultad de aprender sin programación explícita."
                )
            ],
            "synonyms": ["machine learning", "aprendizaje de máquina"],
            "antonyms": [],
            "phonetic": "a.pɾen.diˈsa.xe ow.toˈma.ti.ko",
        },
        "computacion cuantica": {
            "definitions": [
                (
                    "Paradigma de procesamiento informático fundamentado en la "
                    "superposición cuántica y el entrelazamiento."
                )
            ],
            "synonyms": ["cálculo cuántico", "computación por cúbits"],
            "antonyms": ["computación clásica"],
            "phonetic": "kom.pu.taˈsjon ˈkwan.ti.ka",
        },
        "compilador": {
            "definitions": [
                (
                    "Software de sistema que traduce código escrito en un lenguaje de "
                    "programación de alto nivel a código máquina."
                )
            ],
            "synonyms": ["traductor binario", "ensamblador"],
            "antonyms": ["intérprete"],
            "phonetic": "kom.pi.laˈðoɾ",
        },
        "sistema operativo": {
            "definitions": [
                (
                    "Software principal que administra los recursos de hardware y "
                    "provee servicios a los programas de aplicación."
                )
            ],
            "synonyms": ["SO", "plataforma base"],
            "antonyms": [],
            "phonetic": "sisˈte.ma o.pe.ɾaˈti.βo",
        },
        "ciberseguridad": {
            "definitions": [
                (
                    "Práctica de salvaguardar redes, servidores, dispositivos móviles y "
                    "datos confidenciales contra intrusiones ilícitas."
                )
            ],
            "synonyms": ["seguridad informática", "infosec", "protección digital"],
            "antonyms": [],
            "phonetic": "si.βeɾ.se.ɣu.ɾiˈðað",
        },
        "cifrado": {
            "definitions": [
                (
                    "Técnica criptográfica que altera datos mediante un algoritmo y "
                    "clave para asegurar su confidencialidad absoluta."
                )
            ],
            "synonyms": ["encriptación", "codificación segura"],
            "antonyms": ["descifrado", "texto plano"],
            "phonetic": "siˈfɾa.ðo",
        },
        "base de datos": {
            "definitions": [
                (
                    "Estructura organizada para recopilar, consultar y modificar datos "
                    "de forma rápida y persistente."
                )
            ],
            "synonyms": ["repositorio estructurado", "almacén de datos"],
            "antonyms": [],
            "phonetic": "ˈba.se ðe ˈda.tos",
        },
        "protocolo": {
            "definitions": [
                (
                    "Norma o estándar compartido que define el formato y secuenciamiento "
                    "de paquetes en una comunicación digital."
                )
            ],
            "synonyms": ["estándar de comunicación", "convención"],
            "antonyms": [],
            "phonetic": "pɾo.toˈko.lo",
        },
        "entropia": {
            "definitions": [
                (
                    "Grado de dispersión de la energía en un sistema termodinámico o "
                    "nivel de incertidumbre en teoría de información."
                )
            ],
            "synonyms": ["desorden", "aleatoriedad"],
            "antonyms": ["orden", "certeza"],
            "phonetic": "en.tɾoˈpi.a",
        },
        "cubit": {
            "definitions": [
                (
                    "Unidad fundamental de información cuántica que admite estados continuos "
                    "entre cero y uno mediante superposición."
                )
            ],
            "synonyms": ["cúbit", "bit cuántico"],
            "antonyms": ["bit clásico"],
            "phonetic": "ˈku.βit",
        },
        "paradigma": {
            "definitions": [
                (
                    "Enfoque o esquema de razonamiento que rige el diseño y estructuración "
                    "de programas computacionales o teorías."
                )
            ],
            "synonyms": ["modelo", "patrón conceptual"],
            "antonyms": [],
            "phonetic": "pa.ɾaˈðiɣ.ma",
        },
    }

    def __init__(
        self,
        vocabulary_data_path: str | None = None,
        load_vocabulary_data: bool | None = None,
        jarvis_data_path: str | None = None,
        load_jarvis_data: bool | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        path = vocabulary_data_path or jarvis_data_path or DEFAULT_DARIUS_VOCAB_PATH
        should_load = True
        if load_vocabulary_data is not None:
            should_load = load_vocabulary_data
        elif load_jarvis_data is not None:
            should_load = load_jarvis_data

        self.vocabulary_data_path = path
        self.jarvis_data_path = path
        self.timeout_seconds = timeout_seconds
        self._vocabulary_data: dict[str, list[str]] = {}
        self._jarvis_data = self._vocabulary_data
        self._online_cache: dict[str, LexiconEntry] = {}

        if should_load:
            self._load_vocabulary_data_file(path)

    @staticmethod
    def is_safe_lookup_target(target_url: str) -> tuple[bool, str]:
        """Validate destination against SSRF vulnerability policies."""
        if not target_url:
            return False, "Target is empty"
        return AntiSSRFValidator.is_safe_url(target_url, allow_dns_lookup=False)

    def _load_vocabulary_data_file(self, file_path: str) -> None:
        """Load external vocabulary data.json definitions dictionary safely."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            logger.debug("Vocabulary data file not found at %s; skipping loader", file_path)
            return

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw_dict = json.load(f)

            if isinstance(raw_dict, dict):
                for k, v in raw_dict.items():
                    key_norm = str(k).strip().lower()
                    if isinstance(v, list):
                        self._vocabulary_data[key_norm] = [str(item) for item in v]
                    elif isinstance(v, str):
                        self._vocabulary_data[key_norm] = [v]
            logger.info("Loaded %d vocabulary entries from %s", len(self._vocabulary_data), file_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load vocabulary data file at %s: %s", file_path, exc)

    _load_jarvis_data_file = _load_vocabulary_data_file

    def _get_all_known_keys(self) -> list[str]:
        """Return combined unique vocabulary keys across curated, vocabulary data, and online cache."""
        keys = set(self.CURATED_TERMS.keys())
        keys.update(self._vocabulary_data.keys())
        keys.update(self._online_cache.keys())
        return sorted(keys)

    def lookup(self, word: str) -> tuple[bool, LexiconEntry | None, list[str]]:
        """Look up a word across local curated, vocabulary data, online API, and fuzzy matching.

        Args:
            word: The term or phrase to query.

        Returns:
            Tuple of:
                - bool: True if exact or authoritative definition found, False otherwise.
                - LexiconEntry | None: The resulting structured entry or None if unfound.
                - list[str]: Close phonetic or fuzzy spelling suggestions if not found.
        """
        clean_word = word.strip().lower()
        if not clean_word:
            return False, None, []

        # 1. Curated built-in vocabulary
        if clean_word in self.CURATED_TERMS:
            info = self.CURATED_TERMS[clean_word]
            entry = LexiconEntry(
                word=clean_word,
                definitions=list(info.get("definitions", [])),
                synonyms=list(info.get("synonyms", [])),
                antonyms=list(info.get("antonyms", [])),
                phonetic=info.get("phonetic", ""),
                source="local_curated",
            )
            return True, entry, []

        # 2. Vocabulary data.json definitions
        if clean_word in self._vocabulary_data:
            defs = self._vocabulary_data[clean_word]
            entry = LexiconEntry(
                word=clean_word,
                definitions=defs,
                source="vocabulary_data",
            )
            return True, entry, []

        # 3. In-memory online cache
        if clean_word in self._online_cache:
            return True, self._online_cache[clean_word], []

        # 4. Online Dictionary API fallback
        online_entry = self._query_dictionary_api(clean_word)
        if online_entry is not None:
            self._online_cache[clean_word] = online_entry
            return True, online_entry, []

        # 5. Fuzzy matching with difflib
        candidates = self._get_all_known_keys()
        suggestions = difflib.get_close_matches(clean_word, candidates, n=3, cutoff=0.6)
        if suggestions:
            return False, None, suggestions

        return False, None, []

    def _query_dictionary_api(self, word: str) -> LexiconEntry | None:
        """Query free DictionaryAPI service with Anti-SSRF protection."""
        api_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}"
        safe, msg = self.is_safe_lookup_target(api_url)
        if not safe:
            logger.warning("Dictionary API query blocked by Anti-SSRF: %s (%s)", api_url, msg)
            return None

        headers = {
            "User-Agent": "Darius-AI/1.0 (Windows NT 10.0; Win64; x64; Lexicon Oracle)",
            "Accept": "application/json",
        }

        try:
            resp = httpx.get(api_url, headers=headers, timeout=self.timeout_seconds)
            if resp.status_code != 200:
                return None

            data = resp.json()
            if not isinstance(data, list) or not data:
                return None

            first_item = data[0]
            if not isinstance(first_item, dict):
                return None

            phonetic_str = str(first_item.get("phonetic") or "")
            if not phonetic_str:
                phonetics_list = first_item.get("phonetics") or []
                for p in phonetics_list:
                    if isinstance(p, dict) and p.get("text"):
                        phonetic_str = str(p["text"])
                        break

            definitions: list[str] = []
            synonyms: list[str] = []
            antonyms: list[str] = []

            meanings = first_item.get("meanings") or []
            for m in meanings:
                if not isinstance(m, dict):
                    continue
                for syn in m.get("synonyms") or []:
                    if str(syn) not in synonyms:
                        synonyms.append(str(syn))
                for ant in m.get("antonyms") or []:
                    if str(ant) not in antonyms:
                        antonyms.append(str(ant))

                for d in m.get("definitions") or []:
                    if isinstance(d, dict) and d.get("definition"):
                        def_text = str(d["definition"]).strip()
                        if def_text and def_text not in definitions:
                            definitions.append(def_text)
                        for d_syn in d.get("synonyms") or []:
                            if str(d_syn) not in synonyms:
                                synonyms.append(str(d_syn))
                        for d_ant in d.get("antonyms") or []:
                            if str(d_ant) not in antonyms:
                                antonyms.append(str(d_ant))

            if not definitions:
                return None

            return LexiconEntry(
                word=str(first_item.get("word") or word),
                definitions=definitions,
                synonyms=synonyms,
                antonyms=antonyms,
                phonetic=phonetic_str,
                source="dictionaryapi",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Dictionary API query failed for '%s': %s", word, exc)
            return None

    def format_vocal_definition(self, entry: LexiconEntry | None) -> str:
        """Format definition into authentic J.A.R.V.I.S. Butler cadence for vocal TTS output.

        Args:
            entry: LexiconEntry to vocalize, or None if term was not found.

        Returns:
            Butler vocal dialogue string.
        """
        if entry is None or not entry.definitions:
            return (
                "Señor, no dispongo de una entrada léxica concluyente en los registros disponibles para vocalizar."
            )

        primary_def = entry.definitions[0]
        # Clean newline artifacts if any
        primary_def = " ".join(primary_def.split())

        parts: list[str] = [f"Señor, según el archivo léxico, '{entry.word}' se define como: {primary_def}."]

        if entry.phonetic:
            parts.append(f"Transcripción fonética registrada: [{entry.phonetic}].")

        if entry.synonyms:
            top_syns = ", ".join(entry.synonyms[:3])
            parts.append(f"Entre sus términos o sinónimos afines figuran: {top_syns}.")

        parts.append("Quedo a su disposición si precisa un desglose más exhaustivo, señor.")
        return " ".join(parts)
