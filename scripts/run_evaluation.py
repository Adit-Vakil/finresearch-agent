#!/usr/bin/env python3
"""Thin wrapper to run evaluation from the project root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.evaluation.run_eval import main

if __name__ == "__main__":
    main()
