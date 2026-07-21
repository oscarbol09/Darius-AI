# Migración UI: CustomTkinter → PySide6

## Por qué migrar

| Aspecto | CustomTkinter | PySide6 |
|---------|--------------|---------|
| Mantenimiento | Proyecto personal, actualizaciones esporádicas | Qt oficial, respaldo de The Qt Company |
| Widgets | Limitados (CTkButton, CTkEntry, CTkTextbox) | Completo (QTableWidget, QTreeView, QTabWidget, etc.) |
| Rendimiento | Lento con muchos widgets | Optimizado, C++ nativo |
| Async | No soportado nativamente | QThread, QAsync, señales/slots |
| Theming | Solo light/dark básico | QSS completo (hojas de estilo Qt) |
| Sistema de audio | No integrado | QMediaPlayer, QAudioOutput |
| Cross-platform | Windows + macOS + Linux | Windows + macOS + Linux + Android + iOS |
| Layouts | Pack/Grid simple | QHBoxLayout, QVBoxLayout, QGridLayout, QFormLayout |
| Accesibilidad | Básica | ARIA via QAccessible |

## Estrategia de migración (faseada)

### Fase 1: Paralelo (2-3 días)
- Crear `ui_pyside6.py` como reemplazo de `main.py`
- Mantener `main.py` funcional como fallback
- Ambos comparten `config_loader.py`, `ai_client.py`, `tts_worker.py`

### Fase 2: Transición (1 semana)
- Migrar componentes uno por uno:
  1. Ventana principal y layout → QMainWindow + QVBoxLayout
  2. Chat display → QTextEdit + QScrollBar
  3. Visualización de ondas → QGraphicsScene + QTimer (animación)
  4. Botones y controles → QPushButton + QComboBox
  5. Input de texto → QLineEdit + QShortcut
  6. Modo PTT → QHotkey (global)

### Fase 3: Features nuevas (póst-migración)
- Tabs para separar chat / consola / configuración
- Notificaciones del sistema (QSystemTrayIcon)
- Soporte para múltiples micrófonos

## Código base

```python
# ui_pyside6.py — Borrador de la migración
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QTextEdit, QLineEdit, QLabel,
    QComboBox, QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
from PySide6.QtGui import QFont, QAction, QIcon, QPalette, QColor

from config_loader import cfg

class DariusMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DARIUS AI")
        self.setMinimumSize(600, 700)
        self._setup_ui()

    def _setup_ui(self):
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        # ... migrar componentes aquí
```

## Dependencias

```bash
pip install PySide6
# Opcionales:
pip install PySide6-WebEngine  # para vistas web
```
