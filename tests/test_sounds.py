import tempfile
import unittest
from pathlib import Path

import sounds

FALLBACK = ("alias", "SystemNotification")


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.assets = Path(self.dir.name)
        (self.assets / "bell.wav").write_bytes(b"RIFF")

    def tearDown(self):
        self.dir.cleanup()

    def test_builtin(self):
        self.assertEqual(sounds.resolve("builtin:bell", self.assets), ("file", self.assets / "bell.wav"))

    def test_builtin_missing_file_falls_back(self):
        self.assertEqual(sounds.resolve("builtin:gong", self.assets), FALLBACK)

    def test_system_alias(self):
        self.assertEqual(sounds.resolve("system:SystemHand", self.assets), ("alias", "SystemHand"))

    def test_none(self):
        self.assertIsNone(sounds.resolve("none", self.assets))

    def test_user_file(self):
        wav = self.assets / "mine.WAV"
        wav.write_bytes(b"RIFF")
        self.assertEqual(sounds.resolve(f"file:{wav}", self.assets), ("file", wav))

    def test_user_file_missing_or_not_wav_falls_back(self):
        mp3 = self.assets / "song.mp3"
        mp3.write_bytes(b"ID3")
        for sound_id in (f"file:{self.assets / 'gone.wav'}", f"file:{mp3}"):
            with self.subTest(sound_id):
                self.assertEqual(sounds.resolve(sound_id, self.assets), FALLBACK)

    def test_unknown_falls_back(self):
        for sound_id in ("system:Evil", "builtin:nope", "garbage", ""):
            with self.subTest(sound_id):
                self.assertEqual(sounds.resolve(sound_id, self.assets), FALLBACK)

    def test_catalog(self):
        catalog = sounds.catalog()
        self.assertEqual(catalog[0], "builtin:harp")
        self.assertIn("builtin:bell", catalog)
        self.assertIn("system:SystemNotification", catalog)
        self.assertEqual(catalog[-1], "none")


if __name__ == "__main__":
    unittest.main()
