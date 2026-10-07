import os
import re

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# HighPerfWaveVisualizer is line 219-349
# So lines[218:349] is the visualizer.
vis_lines = lines[218:349]

# DariusFinal is line 356-end
# Top stuff is lines[0:218]

# Create directories
os.makedirs('src/darius_ai/core', exist_ok=True)
os.makedirs('src/darius_ai/gui', exist_ok=True)
os.makedirs('src/darius_ai/commands', exist_ok=True)

for dir_path in ['src', 'src/darius_ai', 'src/darius_ai/core', 'src/darius_ai/gui', 'src/darius_ai/commands']:
    init_path = os.path.join(dir_path, '__init__.py')
    if not os.path.exists(init_path):
        with open(init_path, 'w', encoding='utf-8') as f:
            f.write('')

# Write visualizer.py
vis_imports = [
    "import customtkinter as ctk\n",
    "import math\n",
    "import time\n",
    "import threading\n",
    "from collections import deque\n",
    "import numpy as np\n"
]
with open('src/darius_ai/gui/visualizer.py', 'w', encoding='utf-8') as f:
    f.writelines(vis_imports)
    f.write('\n')
    f.writelines(vis_lines)

# Write app.py
# We need to replace HighPerfWaveVisualizer reference or import it in app.py
app_top = lines[0:218]
app_bottom = lines[350:] # From line 351 to end, which includes DariusFinal

with open('src/darius_ai/gui/app.py', 'w', encoding='utf-8') as f:
    f.writelines(app_top)
    f.write('from src.darius_ai.gui.visualizer import HighPerfWaveVisualizer\n')
    f.writelines(app_bottom)

# Write new main.py
new_main = '''import sys
import os

# Add src to path just in case
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.darius_ai.gui.app import DariusFinal

if __name__ == "__main__":
    app = DariusFinal()
    app.mainloop()
'''
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(new_main)

print('Refactor done')
