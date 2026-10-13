"""
tests/test_dialogue_stack.py — Pruebas unitarias para DialogueFrame y DariusDialogueStack
=========================================================================================
Valida la pila LIFO interactiva de diálogos, confirmaciones multi-turno, timeouts,
limpieza de marcos expirados y matching con fast-path afirmativo/negativo en español.
"""

from __future__ import annotations

import threading
import time

import pytest

try:
    from src.darius_ai.core.dialogue_stack import (
        DariusDialogueStack,
        DialogueFrame,
        StarkDialogueStack,
        get_darius_dialogue_stack,
        get_dialogue_stack,
        get_stark_dialogue_stack,
    )
except ImportError:
    from darius_ai.core.dialogue_stack import (
        DariusDialogueStack,
        DialogueFrame,
        StarkDialogueStack,
        get_darius_dialogue_stack,
        get_dialogue_stack,
        get_stark_dialogue_stack,
    )


def test_dialogue_frame_defaults():
    frame = DialogueFrame(
        frame_id="frame-001",
        intent="confirm_purge",
        prompt="¿Desea purgar los archivos temporales?",
        expected_options={"si": "purgar", "no": "cancelar"},
    )
    assert frame.frame_id == "frame-001"
    assert frame.intent == "confirm_purge"
    assert frame.prompt == "¿Desea purgar los archivos temporales?"
    assert frame.expected_options == {"si": "purgar", "no": "cancelar"}
    assert frame.context_data == {}
    assert frame.timeout_seconds == 60.0
    assert frame.created_at > 0


def test_dialogue_stack_lifo_operations():
    stack = DariusDialogueStack()
    assert stack.is_empty() is True
    assert stack.peek() is None
    assert stack.pop() is None

    frame1 = DialogueFrame(
        frame_id="f1",
        intent="main_flow",
        prompt="¿Iniciar diagnóstico?",
        expected_options={"si": "start", "no": "stop"},
    )
    frame2 = DialogueFrame(
        frame_id="f2",
        intent="sub_flow",
        prompt="¿Sobrescribir logs?",
        expected_options={"si": "overwrite", "no": "keep"},
    )

    stack.push(frame1)
    assert stack.is_empty() is False
    assert stack.peek() == frame1

    stack.push(frame2)
    # LIFO: frame2 debe estar arriba
    assert stack.peek() == frame2

    popped = stack.pop()
    assert popped == frame2
    assert stack.peek() == frame1

    popped2 = stack.pop()
    assert popped2 == frame1
    assert stack.is_empty() is True
    assert stack.pop() is None


def test_dialogue_stack_clear():
    stack = DariusDialogueStack()
    stack.push(DialogueFrame(frame_id="f1", intent="i1", prompt="p1", expected_options={"si": "1"}))
    stack.push(DialogueFrame(frame_id="f2", intent="i2", prompt="p2", expected_options={"si": "2"}))
    assert stack.is_empty() is False

    stack.clear()
    assert stack.is_empty() is True
    assert stack.peek() is None


def test_dialogue_stack_clean_expired():
    stack = DariusDialogueStack()
    now = time.time()
    expired_frame = DialogueFrame(
        frame_id="f_old",
        intent="old_intent",
        prompt="Pregunta antigua",
        expected_options={"si": "ok"},
        timeout_seconds=5.0,
        created_at=now - 20.0,
    )
    active_frame = DialogueFrame(
        frame_id="f_new",
        intent="new_intent",
        prompt="Pregunta nueva",
        expected_options={"si": "ok"},
        timeout_seconds=60.0,
        created_at=now,
    )

    stack.push(expired_frame)
    stack.push(active_frame)

    cleaned = stack.clean_expired()
    assert len(cleaned) == 1
    assert cleaned[0].frame_id == "f_old"
    assert stack.peek() == active_frame


def test_process_response_when_stack_empty():
    stack = DariusDialogueStack()
    matched, message, frame = stack.process_response("sí")
    assert matched is False
    assert frame is None
    assert "No hay ningún diálogo activo" in message or "inactividad" in message or "activo" in message


def test_process_response_when_top_frame_expired():
    stack = DariusDialogueStack()
    now = time.time()
    expired_frame = DialogueFrame(
        frame_id="f_expired",
        intent="expired_intent",
        prompt="¿Confirma acción?",
        expected_options={"si": "do_it", "no": "cancel"},
        timeout_seconds=2.0,
        created_at=now - 10.0,
    )
    stack.push(expired_frame)

    matched, message, frame = stack.process_response("sí")
    assert matched is False
    assert message == "El diálogo ha expirado por inactividad, señor."
    assert frame == expired_frame
    # El marco expirado debió ser desapilado
    assert stack.is_empty() is True


@pytest.mark.parametrize(
    "affirmative_word",
    ["si", "sí", "claro", "confirmo", "adelante", "procede", "SÍ", "  Claro! "],
)
def test_process_response_affirmative_fast_path(affirmative_word):
    stack = DariusDialogueStack()
    frame = DialogueFrame(
        frame_id="f_confirm",
        intent="nuclear_launch",
        prompt="¿Autoriza el despliegue?",
        expected_options={"si": "launch_confirmed", "no": "launch_aborted"},
    )
    stack.push(frame)

    matched, action, returned_frame = stack.process_response(affirmative_word)
    assert matched is True
    assert action == "launch_confirmed"
    assert returned_frame == frame
    assert stack.is_empty() is True


@pytest.mark.parametrize("negative_word", ["no", "cancela", "cancelar", "espera", "abortar", "NO", " Cancelar. "])
def test_process_response_negative_fast_path(negative_word):
    stack = DariusDialogueStack()
    frame = DialogueFrame(
        frame_id="f_cancel",
        intent="wipe_disk",
        prompt="¿Formatear la unidad?",
        expected_options={"si": "format_disk", "no": "abort_format"},
    )
    stack.push(frame)

    matched, action, returned_frame = stack.process_response(negative_word)
    assert matched is True
    assert action == "abort_format"
    assert returned_frame == frame
    assert stack.is_empty() is True


def test_process_response_custom_options():
    stack = DariusDialogueStack()
    frame = DialogueFrame(
        frame_id="f_custom",
        intent="choose_monitor",
        prompt="¿Qué monitor desea activar?",
        expected_options={"monitor 1": "activate_m1", "monitor 2": "activate_m2"},
    )
    stack.push(frame)

    matched, action, returned_frame = stack.process_response("Monitor 2")
    assert matched is True
    assert action == "activate_m2"
    assert returned_frame == frame
    assert stack.is_empty() is True


def test_process_response_unmatched_keeps_frame():
    stack = DariusDialogueStack()
    frame = DialogueFrame(
        frame_id="f_ask",
        intent="reboot_system",
        prompt="¿Desea reiniciar el sistema?",
        expected_options={"si": "reboot", "no": "cancel"},
    )
    stack.push(frame)

    matched, message, returned_frame = stack.process_response("tal vez la próxima semana")
    assert matched is False
    assert message.startswith("Respuesta no concluyente. Por favor confirme")
    assert returned_frame == frame
    # El marco permanece en la pila para reintentar
    assert stack.peek() == frame


def test_multi_turn_nested_dialogue_stack():
    stack = DariusDialogueStack()
    parent_frame = DialogueFrame(
        frame_id="f_parent",
        intent="delete_all_files",
        prompt="¿Eliminar todos los archivos?",
        expected_options={"si": "delete_all", "no": "abort"},
    )
    sub_frame = DialogueFrame(
        frame_id="f_sub",
        intent="confirm_backup_first",
        prompt="¿Desea realizar una copia de seguridad previa?",
        expected_options={"si": "backup_then_delete", "no": "delete_without_backup"},
    )

    stack.push(parent_frame)
    stack.push(sub_frame)

    # 1. Responder a la sub-pregunta
    matched1, action1, frame1 = stack.process_response("adelante")
    assert matched1 is True
    assert action1 == "backup_then_delete"
    assert frame1 == sub_frame

    # Ahora el marco padre debe ser el tope
    assert stack.peek() == parent_frame

    # 2. Responder al marco padre
    matched2, action2, frame2 = stack.process_response("confirmo")
    assert matched2 is True
    assert action2 == "delete_all"
    assert frame2 == parent_frame
    assert stack.is_empty() is True


def test_dialogue_stack_thread_safety():
    stack = DariusDialogueStack()
    threads = []

    def pusher():
        for i in range(25):
            f = DialogueFrame(
                frame_id=f"t_{threading.get_ident()}_{i}",
                intent="test",
                prompt="prompt",
                expected_options={"si": "ok"},
            )
            stack.push(f)

    for _ in range(4):
        t = threading.Thread(target=pusher)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 4 hilos * 25 marcos = 100 marcos
    count = 0
    while stack.pop() is not None:
        count += 1
    assert count == 100


def test_process_response_substring_matching():
    stack = DariusDialogueStack()
    frame = DialogueFrame(
        frame_id="f_substr",
        intent="select_device",
        prompt="¿Qué dispositivo?",
        expected_options={"auriculares": "headphones", "altavoces": "speakers"},
    )
    stack.push(frame)

    matched, action, returned_frame = stack.process_response("por favor activa los auriculares ahora")
    assert matched is True
    assert action == "headphones"
    assert returned_frame == frame
    assert stack.is_empty() is True


def test_process_response_binary_inference_affirmative_and_negative():
    stack = DariusDialogueStack()
    # Caso 1: una opción claramente negativa ("cancelar_descarga"), deducir la otra como afirmativa
    frame1 = DialogueFrame(
        frame_id="f_bin1",
        intent="download",
        prompt="¿Descargar paquete?",
        expected_options={"descargar": "do_download", "cancelar_descarga": "abort"},
    )
    stack.push(frame1)

    matched1, action1, _ = stack.process_response("sí")
    assert matched1 is True
    assert action1 == "do_download"

    # Caso 2: una opción claramente afirmativa ("autorizar_acceso"), deducir la otra como negativa
    frame2 = DialogueFrame(
        frame_id="f_bin2",
        intent="auth",
        prompt="¿Autorizar?",
        expected_options={"autorizar_acceso": "grant", "denegar": "deny"},
    )
    stack.push(frame2)

    matched2, action2, _ = stack.process_response("no")
    assert matched2 is True
    assert action2 == "deny"


def test_dialogue_stack_singleton_and_aliases():
    s1 = get_darius_dialogue_stack()
    s2 = get_dialogue_stack()
    s3 = get_stark_dialogue_stack()
    assert s1 is s2
    assert s1 is s3
    assert StarkDialogueStack is DariusDialogueStack


