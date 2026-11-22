import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestCliLazyImports(unittest.TestCase):
    def test_importing_cli_does_not_load_optional_network_adapters(self):
        script = """
import importlib
import sys
importlib.import_module('radar.cli')
for name in (
    'radar.adapters',
    'radar.github_capability',
    'radar.gitee_capability',
    'radar.snowball',
    'radar.fetch',
    'radar.web',
    'radar.verify',
):
    assert name not in sys.modules, name
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
