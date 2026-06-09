#!/usr/bin/env python3
"""
tests/test_all.py
=================
Run the entire test suite. Use this for a quick "does the engine work?" check
before a commit or deploy.

Usage:
    python tests/test_all.py
    python tests/test_all.py --verbose
"""
import os
import sys
import unittest

# Make engine/ importable
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

# Discover and run all tests
loader = unittest.TestLoader()
suite = loader.discover(start_dir=HERE, pattern="test_*.py", top_level_dir=os.path.dirname(HERE))

verbosity = 2 if "--verbose" in sys.argv else 1
runner = unittest.TextTestRunner(verbosity=verbosity)
result = runner.run(suite)

# Exit with non-zero code on failure (for CI)
sys.exit(0 if result.wasSuccessful() else 1)
