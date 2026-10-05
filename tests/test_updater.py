import unittest

import updater

RELEASE = {"tag_name": "v1.2.0", "html_url": "https://github.com/o/A2Timers/releases/tag/v1.2.0"}


class VersionTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updater.parse_version("v1.2.0"), (1, 2, 0))
        self.assertEqual(updater.parse_version("1.10"), (1, 10))
        self.assertIsNone(updater.parse_version("latest"))

    def test_is_newer(self):
        self.assertTrue(updater.is_newer("v1.10.0", "1.9.3"))
        self.assertFalse(updater.is_newer("v1.0.0", "1.0.0"))
        self.assertFalse(updater.is_newer("v0.9", "1.0.0"))
        self.assertFalse(updater.is_newer("nightly", "1.0.0"))


class CheckTests(unittest.TestCase):
    def test_newer_release_found(self):
        calls = []

        def fetch(url, timeout):
            calls.append((url, timeout))
            return RELEASE

        self.assertEqual(updater.check_for_update("o/A2Timers", "1.0.0", fetch),
                         ("v1.2.0", RELEASE["html_url"]))
        self.assertEqual(calls, [("https://api.github.com/repos/o/A2Timers/releases/latest", 5)])

    def test_same_version_returns_none(self):
        self.assertIsNone(updater.check_for_update("o/A2Timers", "1.2.0", lambda u, t: RELEASE))

    def test_errors_return_none(self):
        def boom(url, timeout):
            raise OSError("offline")

        self.assertIsNone(updater.check_for_update("o/A2Timers", "1.0.0", boom))
        self.assertIsNone(updater.check_for_update("o/A2Timers", "1.0.0", lambda u, t: {"oops": 1}))

    def test_no_repo_configured(self):
        self.assertIsNone(updater.check_for_update("", "1.0.0", lambda u, t: RELEASE))


if __name__ == "__main__":
    unittest.main()
