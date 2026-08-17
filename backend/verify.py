import os
import sys

# Ensure current folder is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    import pytest
except ImportError:
    print("pytest not installed. Installing dependencies first.")
    sys.exit(1)

if __name__ == "__main__":
    print("Starting AI Operating System Scaffolding Verification...")
    # Run pytest on the tests directory
    exit_code = pytest.main(["-v", "tests"])
    sys.exit(exit_code)
