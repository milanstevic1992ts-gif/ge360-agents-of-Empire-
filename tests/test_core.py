from pathlib import Path
import tempfile
import unittest

from ge360_agent.config import load_settings
from ge360_agent.security import validate_session_name


class SecurityTests(unittest.TestCase):
    def test_valid_session_names(self):
        self.assertEqual(validate_session_name("jarvis"), "jarvis")
        self.assertEqual(validate_session_name("mautic-fix_1"), "mautic-fix_1")

    def test_invalid_session_names(self):
        for name in ["", "../root", "hello world", "a" * 41, "-bad"]:
            with self.assertRaises(ValueError):
                validate_session_name(name)


class ConfigTests(unittest.TestCase):
    def test_load_toml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            config = root / "config.toml"
            config.write_text(
                f"""
[server]
host = "127.0.0.1"
port = 9999
session_prefix = "test-"

[codex]
command = "codex"

[services]
systemd_units = ["example.service"]

[[workspaces]]
id = "test"
name = "Test"
path = "{workspace}"
"""
            )
            settings = load_settings(config)
            self.assertEqual(settings.port, 9999)
            self.assertEqual(settings.session_prefix, "test-")
            self.assertEqual(settings.workspaces[0].id, "test")
            self.assertEqual(settings.systemd_units, ["example.service"])


if __name__ == "__main__":
    unittest.main()
