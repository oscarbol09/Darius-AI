import os
import sys

# Add src to path just in case
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from src.darius_ai.gui.app import DariusFinal

if __name__ == "__main__":
    app = DariusFinal()
    app.mainloop()
