"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Pytest configuration to ensure project root is importable in tests.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
