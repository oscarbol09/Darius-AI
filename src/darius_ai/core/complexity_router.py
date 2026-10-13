"""
complexity_router.py — Analizador multidimensional de complejidad y enrutador inteligente de modelos
====================================================================================================
Arquitectura Nativa Darius AI. Evalúa consultas de voz y texto con 5 señales
ponderadas para asignar presupuestos de tokens óptimos y enrutar a modelos locales rápidos o modelos frontera.
"""

from __future__ import annotations

import logging
import re
from enum import StrEnum

log = logging.getLogger("DARIUS.ComplexityRouter")


class ComplexityTier(StrEnum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class ModelTarget(StrEnum):
    LOCAL_FAST = "local_fast"          # Modelos locales ligeros (Ollama, Groq rápido)
    STANDARD = "standard"              # Modelos estándar balanceados (Gemini Flash, GPT-4o-mini)
    FRONTIER_REASONING = "frontier_reasoning"  # Modelos de razonamiento profundo (DeepSeek-R1, o1, Claude Sonnet)


# Presupuestos base de tokens por nivel
TIER_TOKEN_BUDGETS = {
    ComplexityTier.TRIVIAL: 1024,
    ComplexityTier.SIMPLE: 2048,
    ComplexityTier.MODERATE: 4096,
    ComplexityTier.COMPLEX: 8192,
    ComplexityTier.VERY_COMPLEX: 16384,
}

# Palabras clave de programación y matemáticas
CODE_KEYWORDS = re.compile(
    r"\b(python|javascript|typescript|c\+\+|rust|html|css|sql|function|def|class|async|await|"
    r"return|import|json|api|regex|dijkstra|algoritmo|matriz|ecuacion|calculo)\b",
    re.IGNORECASE,
)

# Indicadores de razonamiento y análisis profundo
REASONING_KEYWORDS = re.compile(
    r"\b(por qu[eé]|explica|compara|analiza|diseña|evalua|diferencia|pros y contras|"
    r"trade-offs|arquitectura|demuestra|complejidad)\b",
    re.IGNORECASE,
)

# Solicitudes creativas o de síntesis
CREATIVE_KEYWORDS = re.compile(
    r"\b(redacta|escribe|crea|genera|resume|sintetiza|propuesta|borrador|historia|guion)\b",
    re.IGNORECASE,
)


class ComplexityRouter:
    """
    Analizador determinista y ligero (<1ms) de complejidad de consultas.
    """

    def __init__(
        self,
        length_weight: float = 0.20,
        domain_weight: float = 0.25,
        reasoning_weight: float = 0.25,
        structure_weight: float = 0.15,
        creative_weight: float = 0.15,
    ) -> None:
        self.w_length = length_weight
        self.w_domain = domain_weight
        self.w_reasoning = reasoning_weight
        self.w_structure = structure_weight
        self.w_creative = creative_weight

    def get_token_budget(self, tier: ComplexityTier, is_reasoning_model: bool = False) -> int:
        """Devuelve el presupuesto asignado, duplicándolo si el modelo utiliza cadena de razonamiento oculta."""
        base = TIER_TOKEN_BUDGETS.get(tier, 2048)
        return base * 2 if is_reasoning_model else base

    def analyze(self, query: str) -> tuple[float, ComplexityTier, int, ModelTarget]:
        """
        Analiza la consulta y retorna (score, tier, token_budget, model_target).
        """
        text = query.strip()
        if not text:
            return 0.0, ComplexityTier.TRIVIAL, TIER_TOKEN_BUDGETS[ComplexityTier.TRIVIAL], ModelTarget.LOCAL_FAST

        # 1. Señal de longitud (0.0 a 1.0)
        char_len = len(text)
        if char_len < 30:
            s_len = 0.05
        elif char_len < 100:
            s_len = 0.25
        elif char_len < 300:
            s_len = 0.60
        else:
            s_len = 1.0

        # 2. Señal de dominio / código
        matches_code = len(CODE_KEYWORDS.findall(text))
        s_domain = min(1.0, matches_code * 0.35)

        # 3. Señal de razonamiento
        matches_reason = len(REASONING_KEYWORDS.findall(text))
        s_reason = min(1.0, matches_reason * 0.40)

        # 4. Señal de estructura (puntuación, listas, preguntas)
        num_questions = text.count("?") + text.count("¿")
        num_bullets = len(re.findall(r"(?:^|\n)\s*[-*•\d+\.]", text))
        s_struct = min(1.0, (num_questions * 0.3) + (num_bullets * 0.4))

        # 5. Señal creativa / síntesis
        matches_creative = len(CREATIVE_KEYWORDS.findall(text))
        s_creative = min(1.0, matches_creative * 0.40)

        # Score global ponderado
        score = (
            (s_len * self.w_length)
            + (s_domain * self.w_domain)
            + (s_reason * self.w_reasoning)
            + (s_struct * self.w_structure)
            + (s_creative * self.w_creative)
        )
        score = round(min(1.0, max(0.0, score)), 3)

        # Asignar Tier
        if score < 0.20:
            tier = ComplexityTier.TRIVIAL
            target = ModelTarget.LOCAL_FAST
        elif score < 0.40:
            tier = ComplexityTier.SIMPLE
            target = ModelTarget.LOCAL_FAST
        elif score < 0.60:
            tier = ComplexityTier.MODERATE
            target = ModelTarget.STANDARD
        elif score < 0.80:
            tier = ComplexityTier.COMPLEX
            target = ModelTarget.FRONTIER_REASONING
        else:
            tier = ComplexityTier.VERY_COMPLEX
            target = ModelTarget.FRONTIER_REASONING

        budget = self.get_token_budget(tier, is_reasoning_model=False)
        return score, tier, budget, target
