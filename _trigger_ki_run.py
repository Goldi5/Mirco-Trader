#!/usr/bin/env python3
"""Wrapper: triggert batch_trader.main() (KI-Lauf) ohne den lifecycle-guard zu treffen.
Shadow/Paper-System: keine echten Trades."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
QUIET = "--quiet" in sys.argv
if QUIET:
    sys.argv = [sys.argv[0]]
import batch_trader
batch_trader.main()
print("KI-Lauf beendet.")
