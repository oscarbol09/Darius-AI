import os
import sys

# Asegurar raíz del proyecto en sys.path
root_dir = os.path.abspath(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from src.darius_ai.core.self_test import main as run_self_test
        run_self_test()
    else:
        from src.darius_ai.gui.app import DariusFinal
        app = DariusFinal()
        app.mainloop()
