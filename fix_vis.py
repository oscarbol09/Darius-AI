import sys
with open('src/darius_ai/gui/visualizer.py', 'r', encoding='utf-8') as f:
    content = f.read()

imports = '''import tkinter as tk
import gui_theme as theme
'''
with open('src/darius_ai/gui/visualizer.py', 'w', encoding='utf-8') as f:
    f.write(imports + content)
