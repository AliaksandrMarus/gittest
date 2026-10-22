import sys
from pathlib import Path

# invoice_kit лежит рядом с папкой tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
