from pathlib import Path
import tempfile
import unittest

import ge360_agent.activity as activity
from ge360_agent.versioning import release_info


class VersioningTests(unittest.TestCase):
    def test_release_manifest_is_current(self):
        info = release_info()
        self.assertEqual(info.version, "0.7.0")
        self.assertGreaterEqual(info.schema_version, 3)
        self.assertEqual(info.channel, "stable")


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = activity.DB
        activity.DB = Path(self.tmp.name) / "activity.sqlite3"

    def tearDown(self):
        activity.DB = self.old_db
        self.tmp.cleanup()

    def test_status_and_timeline(self):
        activity.record("ge360-test", "ge360_n8n_engineer", "working", "delegated", "test")
        activity.record("ge360-test", "ge360_docker", "waiting", "queued", "test")
        latest = activity.latest_by_agent()
        self.assertEqual(latest["ge360_n8n_engineer"]["status"], "working")
        self.assertEqual(latest["ge360_docker"]["status"], "waiting")
        events = activity.timeline(session="ge360-test")
        self.assertEqual(len(events), 2)
        self.assertIn("ge360_n8n_engineer", activity.agents_for_session("ge360-test"))

    def test_unknown_status_is_normalized(self):
        activity.record("ge360-test", "jarvis", "nonsense", "test")
        latest = activity.latest_by_agent()
        self.assertEqual(latest["jarvis"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
