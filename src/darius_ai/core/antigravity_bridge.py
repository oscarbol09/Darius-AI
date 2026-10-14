"""Módulo AntigravityAgentBridge — Enlace con el runtime autónomo de Antigravity.

Permite conectar a Darius AI directamente con el cerebro de Antigravity,
otorgándole razonamiento autónomo, planificación de ingeniería,
ejecución de comandos y herramientas del sistema en el espacio de trabajo.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.darius_ai.core.config_loader import cfg
from src.darius_ai.core.darius_persona import DariusPersona

log = logging.getLogger("DARIUS.AntigravityBridge")


@dataclass
class AntigravityResult:
    """Resultado de la ejecución de una consulta o tarea a través de Antigravity."""

    success: bool
    response_text: str
    tool_calls: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0


class AntigravityAgentBridge:
    """Puente de comunicación e interoperabilidad con el runtime de Antigravity."""

    def __init__(self, workspace_path: str | Path | None = None):
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self._lock = threading.Lock()
        self._persona = DariusPersona()

    def is_available(self) -> bool:
        """Comprueba si el paquete google-antigravity está instalado y accesible."""
        try:
            import google.antigravity  # noqa: F401

            return True
        except ImportError:
            return False

    def build_system_instructions(self, user_name: str = "señor") -> str:
        """Construye las instrucciones de sistema para el agente Antigravity."""
        return (
            f"Eres Antigravity, el motor de inteligencia de élite e ingeniería operando dentro de DARIUS AI. "
            f"Te diriges respetuosamente al usuario como '{user_name}'. "
            f"Tienes acceso al repositorio y herramientas del sistema. "
            f"Eres analítico, conciso, riguroso con los protocolos de ingeniería (TDD, ECC) "
            f"y ejecutas las tareas con absoluta precisión técnica sin explicaciones superfluas."
        )

    async def _execute_agent_chat(
        self,
        prompt: str,
        system_instructions: str | None = None,
        timeout: float = 60.0,
    ) -> AntigravityResult:
        """Ejecuta una interacción con el runtime de Agent de Antigravity."""
        t0 = time.time()
        tool_calls_executed: list[str] = []

        try:
            from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig

            user_name = cfg.user_name or "señor"
            sys_inst = system_instructions or self.build_system_instructions(user_name)

            config = LocalAgentConfig(
                system_instructions=sys_inst,
                capabilities=CapabilitiesConfig(
                    enable_subagents=True,
                ),
                workspaces=[str(self.workspace_path)],
            )

            # Invocar al agente dentro del contexto asíncrono oficial
            async with Agent(config) as agent:
                response = await asyncio.wait_for(agent.chat(prompt), timeout=timeout)

                # Inspección de llamadas a herramientas
                if hasattr(response, "tool_calls") and response.tool_calls:
                    try:
                        if hasattr(response.tool_calls, "__aiter__"):
                            async for tc in response.tool_calls:
                                tool_calls_executed.append(str(tc))
                        else:
                            for tc in response.tool_calls:
                                tool_calls_executed.append(str(tc))
                    except Exception as err:
                        log.debug(f"[AntigravityBridge] No se pudieron iterar tool_calls: {err}")

                # Obtener el texto de la respuesta
                text = ""
                if hasattr(response, "text"):
                    if callable(response.text):
                        import inspect

                        if inspect.iscoroutinefunction(response.text):
                            text = await response.text()
                        else:
                            text = str(response.text())
                    else:
                        text = str(response.text)
                else:
                    # En caso de respuesta en streaming
                    chunks = []
                    async for token in response:
                        chunks.append(str(token))
                    text = "".join(chunks)

                dt = time.time() - t0
                return AntigravityResult(
                    success=True,
                    response_text=str(text).strip(),
                    tool_calls=tool_calls_executed,
                    execution_time_seconds=dt,
                )

        except TimeoutError:
            dt = time.time() - t0
            err_msg = f"Tiempo de espera agotado ({timeout}s) al consultar al Agente Antigravity, señor."
            log.warning(f"[AntigravityBridge] {err_msg}")
            return AntigravityResult(
                success=False,
                response_text=err_msg,
                tool_calls=tool_calls_executed,
                execution_time_seconds=dt,
            )
        except Exception as exc:
            dt = time.time() - t0
            err_msg = f"Error en el motor Antigravity: {exc}"
            log.error(f"[AntigravityBridge] {err_msg}", exc_info=True)
            return AntigravityResult(
                success=False,
                response_text=f"Señor, ocurrió un fallo al comunicarse con Antigravity: {exc}",
                tool_calls=tool_calls_executed,
                execution_time_seconds=dt,
            )

    async def ask_agent_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        timeout: float = 60.0,
    ) -> AntigravityResult:
        """Punto de entrada asíncrono para enviar prompts al agente."""
        return await self._execute_agent_chat(prompt, system_instructions=system_prompt, timeout=timeout)

    def ask_agent(
        self,
        prompt: str,
        system_prompt: str | None = None,
        timeout: float = 60.0,
    ) -> AntigravityResult:
        """Punto de entrada síncrono para su uso en llamadas bloqueantes o clientes GUI."""
        with self._lock:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            try:
                if loop and loop.is_running():
                    # Si ya estamos dentro de un bucle de eventos, ejecutamos en hilo separado
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.ask_agent_async(prompt, system_prompt=system_prompt, timeout=timeout),
                        )
                        return future.result()
                else:
                    return asyncio.run(
                        self.ask_agent_async(prompt, system_prompt=system_prompt, timeout=timeout)
                    )
            except Exception as exc:
                log.error(f"[AntigravityBridge] Error síncrono al consultar agente: {exc}")
                return AntigravityResult(
                    success=False,
                    response_text=f"Señor, ocurrió un fallo al comunicarse con Antigravity: {exc}",
                )

    def execute_development_instruction(self, instruction: str) -> tuple[bool, str]:
        """Ejecuta una instrucción técnica o de ingeniería y formatea la respuesta vocal."""
        log.info(f"[AntigravityBridge] Ejecutando instrucción técnica: '{instruction}'")
        res = self.ask_agent(instruction)

        if not res.success:
            return False, res.response_text

        # Si el agente ejecutó herramientas, armar un reporte enriquecido
        tools_summary = ""
        if res.tool_calls:
            count = len(res.tool_calls)
            tools_summary = f" Se ejecutaron {count} acciones técnicas en el entorno."

        formatted_speech = f"{res.response_text}{tools_summary}"
        return True, formatted_speech


_GLOBAL_BRIDGE: AntigravityAgentBridge | None = None
_BRIDGE_LOCK = threading.Lock()


def get_antigravity_bridge() -> AntigravityAgentBridge:
    """Obtiene la instancia singleton de AntigravityAgentBridge."""
    global _GLOBAL_BRIDGE
    if _GLOBAL_BRIDGE is None:
        with _BRIDGE_LOCK:
            if _GLOBAL_BRIDGE is None:
                _GLOBAL_BRIDGE = AntigravityAgentBridge()
    return _GLOBAL_BRIDGE
