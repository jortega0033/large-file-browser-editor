import unittest

from line_editor.validation import (
    ApiError,
    validate_base_revision,
    validate_payload,
    validate_text,
    validate_title,
)


class TitleTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(len(validate_title("a" * 120)), 120)
        with self.assertRaises(ApiError) as cm:
            validate_title("a" * 121)
        self.assertEqual((cm.exception.status, cm.exception.field), (400, "title"))

    def test_astral_counts_as_one(self):
        self.assertEqual(validate_title("\U0001F600" * 120), "\U0001F600" * 120)
        with self.assertRaises(ApiError):
            validate_title("\U0001F600" * 121)

    def test_trim_and_empty(self):
        self.assertEqual(validate_title("  hi \n"), "hi")
        for bad in ("", "   ", "\t\n"):
            with self.assertRaises(ApiError):
                validate_title(bad)

    def test_trim_happens_before_length(self):
        self.assertEqual(validate_title(" " + "a" * 120 + " "), "a" * 120)

    def test_control_and_surrogates_rejected(self):
        for bad in ("a\x00b", "a\x07b", "a\tb", "a\nb", "a\ud800b"):
            with self.assertRaises(ApiError, msg=repr(bad)):
                validate_title(bad)

    def test_non_string(self):
        for bad in (None, 1, True, ["a"]):
            with self.assertRaises(ApiError):
                validate_title(bad)


class TextTests(unittest.TestCase):
    def test_boundaries(self):
        validate_text("")
        validate_text("a" * 262144)
        with self.assertRaises(ApiError) as cm:
            validate_text("a" * 262145)
        self.assertEqual((cm.exception.status, cm.exception.code), (413, "text_too_large"))

    def test_bytes_not_code_points(self):
        validate_text("é" * 131072)  # 262144 bytes
        with self.assertRaises(ApiError) as cm:
            validate_text("é" * 131073)
        self.assertEqual(cm.exception.status, 413)

    def test_nul_and_surrogate(self):
        for bad in ("a\x00", "\udc00"):
            with self.assertRaises(ApiError) as cm:
                validate_text(bad)
            self.assertEqual(cm.exception.code, "invalid_field")

    def test_newlines_unchanged(self):
        s = "a\r\nb\nc\r\t"
        self.assertEqual(validate_text(s), s)


class PayloadTests(unittest.TestCase):
    def test_base_revision(self):
        self.assertEqual(validate_base_revision(1), 1)
        for bad in (0, -1, True, 1.0, "1", None, 2**63):
            with self.assertRaises(ApiError):
                validate_base_revision(bad)

    def test_unknown_missing_and_type(self):
        with self.assertRaises(ApiError):
            validate_payload({"title": "a", "text": "", "x": 1}, False)
        with self.assertRaises(ApiError):
            validate_payload({"title": "a", "text": "", "base_revision": 1}, False)
        with self.assertRaises(ApiError) as cm:
            validate_payload({"title": "a", "text": ""}, True)
        self.assertEqual(cm.exception.field, "base_revision")
        with self.assertRaises(ApiError) as cm:
            validate_payload([], False)
        self.assertEqual(cm.exception.code, "invalid_json")

    def test_ok(self):
        out = validate_payload({"title": " a ", "text": "x", "base_revision": 3}, True)
        self.assertEqual(out, {"title": "a", "text": "x", "base_revision": 3})


if __name__ == "__main__":
    unittest.main()
