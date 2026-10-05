import hashlib
import tempfile
import unittest
from pathlib import Path

import updater

REPO = "o/A2Timers"
DL = "https://github.com/o/A2Timers/releases/download/v1.2.0/"
SETUP = b"fake installer bytes"
SETUP_HASH = hashlib.sha256(SETUP).hexdigest()
RELEASE_JSON = {
    "tag_name": "v1.2.0",
    "html_url": "https://github.com/o/A2Timers/releases/tag/v1.2.0",
    "assets": [
        {"name": "A2Timers-Setup-1.2.0.exe", "browser_download_url": DL + "A2Timers-Setup-1.2.0.exe"},
        {"name": "SHA256SUMS.txt", "browser_download_url": DL + "SHA256SUMS.txt"},
    ],
}


def release(setup_url=DL + "A2Timers-Setup-1.2.0.exe", sums_url=DL + "SHA256SUMS.txt"):
    return updater.Release("v1.2.0", RELEASE_JSON["html_url"], setup_url, sums_url)


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
            calls.append(url)
            return RELEASE_JSON

        self.assertEqual(updater.check_for_update(REPO, "1.0.0", fetch), release())
        self.assertEqual(calls, ["https://api.github.com/repos/o/A2Timers/releases/latest"])

    def test_assets_outside_the_repo_are_ignored(self):
        evil = dict(RELEASE_JSON, assets=[
            {"name": "A2Timers-Setup-1.2.0.exe", "browser_download_url": "https://evil.example/A2Timers-Setup.exe"},
            {"name": "SHA256SUMS.txt", "browser_download_url": DL + "SHA256SUMS.txt"},
        ])
        found = updater.check_for_update(REPO, "1.0.0", lambda u, t: evil)
        self.assertIsNone(found.setup_url)

    def test_release_without_assets(self):
        found = updater.check_for_update(REPO, "1.0.0", lambda u, t: dict(RELEASE_JSON, assets=[]))
        self.assertEqual(found, release(None, None))

    def test_same_version_returns_none(self):
        self.assertIsNone(updater.check_for_update(REPO, "1.2.0", lambda u, t: RELEASE_JSON))

    def test_errors_return_none(self):
        def boom(url, timeout):
            raise OSError("offline")

        self.assertIsNone(updater.check_for_update(REPO, "1.0.0", boom))
        self.assertIsNone(updater.check_for_update(REPO, "1.0.0", lambda u, t: {"oops": 1}))

    def test_no_repo_configured(self):
        self.assertIsNone(updater.check_for_update("", "1.0.0", lambda u, t: RELEASE_JSON))


class SumsTests(unittest.TestCase):
    def test_parse_sums(self):
        text = f"{SETUP_HASH.upper()}  A2Timers-Setup-1.2.0.exe\nabc  other.txt\n"
        self.assertEqual(updater.parse_sums(text, "A2Timers-Setup-1.2.0.exe"), SETUP_HASH)
        self.assertIsNone(updater.parse_sums(text, "missing.exe"))
        self.assertIsNone(updater.parse_sums("nothex  A2Timers-Setup-1.2.0.exe", "A2Timers-Setup-1.2.0.exe"))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.dest = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def fetcher(self, setup=SETUP, sums_hash=SETUP_HASH):
        def fetch(url, timeout):
            if url.endswith("SHA256SUMS.txt"):
                return f"{sums_hash}  A2Timers-Setup-1.2.0.exe\n".encode()
            return setup
        return fetch

    def test_verified_download(self):
        path = updater.download_update(release(), self.dest, self.fetcher())
        self.assertEqual(path, self.dest / "A2Timers-Setup-1.2.0.exe")
        self.assertEqual(path.read_bytes(), SETUP)

    def test_hash_mismatch_is_rejected(self):
        self.assertIsNone(updater.download_update(release(), self.dest, self.fetcher(setup=b"tampered")))
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_missing_assets(self):
        self.assertIsNone(updater.download_update(release(sums_url=None), self.dest, self.fetcher()))
        self.assertIsNone(updater.download_update(release(setup_url=None), self.dest, self.fetcher()))

    def test_network_error(self):
        def boom(url, timeout):
            raise OSError("offline")

        self.assertIsNone(updater.download_update(release(), self.dest, boom))

    def test_clean_downloads_keeps_only_newer(self):
        for name in ("A2Timers-Setup-1.0.0.exe", "A2Timers-Setup-1.1.0.exe", "A2Timers-Setup-1.2.0.exe"):
            (self.dest / name).write_bytes(b"x")
        updater.clean_downloads(self.dest, "1.1.0")
        self.assertEqual([p.name for p in self.dest.iterdir()], ["A2Timers-Setup-1.2.0.exe"])

    def test_cached_file_is_reused(self):
        (self.dest / "A2Timers-Setup-1.2.0.exe").write_bytes(SETUP)

        def sums_only(url, timeout):
            if url.endswith("SHA256SUMS.txt"):
                return f"{SETUP_HASH}  A2Timers-Setup-1.2.0.exe\n".encode()
            raise AssertionError("setup must not be downloaded again")

        self.assertEqual(updater.download_update(release(), self.dest, sums_only),
                         self.dest / "A2Timers-Setup-1.2.0.exe")


class LaunchTests(unittest.TestCase):
    def test_launch_installer_runs_powershell_hidden_but_not_detached(self):
        # DETACHED_PROCESS makes powershell.exe exit without running the command.
        import subprocess
        from unittest import mock

        with mock.patch.object(updater.subprocess, "Popen") as popen:
            updater.launch_installer(Path(r"C:\x\A2Timers-Setup-1.2.0.exe"))
        args, kwargs = popen.call_args
        self.assertEqual(args[0][0], "powershell.exe")
        self.assertIn("/AUTOUPDATE=1", args[0][-1])
        self.assertEqual(kwargs["env"]["A2T_SETUP"], r"C:\x\A2Timers-Setup-1.2.0.exe")
        self.assertTrue(kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW)
        self.assertFalse(kwargs["creationflags"] & subprocess.DETACHED_PROCESS)


if __name__ == "__main__":
    unittest.main()
