import unittest

import i18n
import schedule


def rule(name):
    return schedule.parse_rule({"id": "r", "name": name, "anchor_utc": "00:00", "every_minutes": 60})


class I18nTests(unittest.TestCase):
    def test_translate_with_format(self):
        self.assertEqual(i18n.t("it", "active", time="05:00"), "ATTIVO 05:00")
        self.assertEqual(i18n.t("en", "active", time="05:00"), "ACTIVE 05:00")

    def test_every_key_exists_in_both_languages(self):
        self.assertEqual(set(i18n.STRINGS["it"]), set(i18n.STRINGS["en"]))

    def test_day_unit(self):
        self.assertEqual((i18n.t("it", "day_unit"), i18n.t("en", "day_unit")), ("g", "d"))

    def test_utc_offset_label(self):
        from datetime import timedelta
        cases = {timedelta(hours=2): "UTC+2", timedelta(0): "UTC", timedelta(hours=-3, minutes=-30): "UTC-3:30",
                 timedelta(hours=5, minutes=30): "UTC+5:30"}
        for offset, text in cases.items():
            with self.subTest(text):
                self.assertEqual(i18n.utc_offset_label(offset), text)

    def test_unknown_language_uses_english(self):
        self.assertEqual(i18n.t("fr", "save"), "Save")

    def test_resolve_language(self):
        self.assertEqual(i18n.resolve_language("auto", detected="it"), "it")
        self.assertEqual(i18n.resolve_language("en", detected="it"), "en")

    def test_rule_name_string_and_dict(self):
        self.assertEqual(i18n.rule_name(rule("Shugo Festival"), "it"), "Shugo Festival")
        localized = rule({"it": "Reset giornaliero", "en": "Daily reset"})
        self.assertEqual(i18n.rule_name(localized, "it"), "Reset giornaliero")
        self.assertEqual(i18n.rule_name(localized, "en"), "Daily reset")

    def test_rule_name_fallbacks(self):
        self.assertEqual(i18n.rule_name(rule({"en": "Daily reset"}), "it"), "Daily reset")
        self.assertEqual(i18n.rule_name(rule({"it": "Solo IT"}), "en"), "Solo IT")

    def test_sound_labels(self):
        self.assertEqual(i18n.sound_label("builtin:bell", "it"), "Campanello")
        self.assertEqual(i18n.sound_label("file:C:/x/my alarm.wav", "en"), "File: my alarm.wav")


class ParseNameTests(unittest.TestCase):
    def test_rejects_bad_names(self):
        for name in ({}, 5, {"it": 3}):
            with self.subTest(name), self.assertRaises(ValueError):
                rule(name)

    def test_default_sound(self):
        self.assertEqual(rule("X").sound, "builtin:bell")
        r = schedule.parse_rule({"id": "r", "name": "X", "anchor_utc": "00:00", "every_minutes": 60,
                                 "sound": "builtin:gong"})
        self.assertEqual(r.sound, "builtin:gong")


if __name__ == "__main__":
    unittest.main()
