import os
import re

root = r"C:\Users\dario\Documents\Proyectos Personales GH\Darius-AI"

mapping = {
    "audio": [
        "acoustic_trigger",
        "edge_tts_engine",
        "elevenlabs_tts_engine",
        "stt_engine",
        "tts_cache",
        "tts_worker",
        "voice_filter",
    ],
    "core": [
        "config_loader",
        "agent_planner",
        "agentic_bridge",
        "ai_client",
        "deep_research",
        "obsidian_brain",
        "screen_vision",
        "self_test",
    ],
    "gui": ["gui_theme", "human_gui", "byok_settings"],
    "system": ["windows_commands", "workspace_manager"],
}

file_to_module = {}
for category, files in mapping.items():
    for f in files:
        file_to_module[f] = f"src.darius_ai.{category}"


def fix_patches(filepath):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    new_content = content
    for mod, new_path in file_to_module.items():
        # Match patch("mod.something") or mocker.patch('mod.something')
        # We look for quote, module name, dot
        new_content = re.sub(rf'([\'"]){mod}\.', rf"\g<1>{new_path}.{mod}.", new_content)

    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated patches in {filepath}")


for dirpath, _, filenames in os.walk(os.path.join(root, "tests")):
    for f in filenames:
        if f.endswith(".py"):
            fix_patches(os.path.join(dirpath, f))
