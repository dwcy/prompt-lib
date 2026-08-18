# -*- coding: utf-8 -*-
"""Entry point for `python -m cabal.dotnetgen`."""

from __future__ import annotations

import sys

from cabal.dotnetgen.cli import main

if __name__ == "__main__":
    sys.exit(main())
