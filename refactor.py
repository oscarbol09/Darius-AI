import os
import shutil
import re

root = r"C:\Users\dario\Documents\Proyectos Personales GH\Darius-AI"
src_dir = os.path.join(root, "src", "darius_ai")

mapping = {
    "audio": ["acoustic_trigger.py", "edge_tts_engine.py", "elevenlabs_tts_engine.py", "stt_engine.py", "tts_cache.py", "tts_worker.py", "voice_filter.py"],
    "core": ["config_loader.py", "agent_planner.py", "agentic_bridge.py", "ai_client.py", "deep_research.py", "obsidian_brain.py", "screen_vision.py", "self_test.py"],
    "gui": ["gui_theme.py", "human_gui.py", "byok_settings.py"],
    "system": ["windows_commands.py", "workspace_manager.py"]
}

# 1. Create dirs and move files
file_to_module = {}
for category, files in mapping.items():
    cat_dir = os.path.join(src_dir, category)
    os.makedirs(cat_dir, exist_ok=True)
    init_file = os.path.join(cat_dir, "__init__.py")
    if not os.path.exists(init_file):
        open(init_file, 'w').close()
        
    for f in files:
        src_path = os.path.join(root, f)
        dst_path = os.path.join(cat_dir, f)
        if os.path.exists(src_path):
            shutil.move(src_path, dst_path)
            print(f"Moved {f} to {category}")
        else:
            print(f"Warning: {src_path} not found")
        
        module_name = f[:-3]
        file_to_module[module_name] = f"src.darius_ai.{category}"

# 2. Fix imports
def fix_imports(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for mod, new_path in file_to_module.items():
        # import mod
        new_content = re.sub(rf'^(\s*)import {mod}(\s*(?:#.*)?)$', rf'\1from {new_path} import {mod}\2', new_content, flags=re.MULTILINE)
        # import mod as alias
        new_content = re.sub(rf'^(\s*)import {mod} as (\w+)(\s*(?:#.*)?)$', rf'\1from {new_path} import {mod} as \2\3', new_content, flags=re.MULTILINE)
        # from mod import x
        new_content = re.sub(rf'^(\s*)from {mod} import ', rf'\1from {new_path}.{mod} import ', new_content, flags=re.MULTILINE)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated imports in {filepath}")

# Process src, tests, and main.py
for dirpath, _, filenames in os.walk(os.path.join(root, "src")):
    for f in filenames:
        if f.endswith('.py'):
            fix_imports(os.path.join(dirpath, f))

for dirpath, _, filenames in os.walk(os.path.join(root, "tests")):
    for f in filenames:
        if f.endswith('.py'):
            fix_imports(os.path.join(dirpath, f))

main_path = os.path.join(root, "main.py")
if os.path.exists(main_path):
    fix_imports(main_path)
