import sys
with open('src/darius_ai/gui/app.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('from src.darius_ai.gui.visualizer import HighPerfWaveVisualizer\n', 'from src.darius_ai.gui.visualizer import HighPerfWaveVisualizer  # noqa: E402\n')
with open('src/darius_ai/gui/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
