"""Word-boundary and phrase-separator tests for term matching.

These pin the V0.4.2 behaviour of term_matches / match_terms: full-word hits
only (``cat`` must not match ``category``), with spaces in configured phrases
treated as interchangeable space / hyphen / underscore separators.
"""

from __future__ import annotations

import unittest

from ceramic_report import match_terms, term_matches


class WordBoundaryTests(unittest.TestCase):
    def test_cat_does_not_match_category(self):
        self.assertFalse(term_matches("category theory reading list", "cat"))

    def test_cat_does_not_match_plural_cats(self):
        # "cats" is its own configured exclude term; the singular must not
        # fire inside the plural.
        self.assertFalse(term_matches("two cats on the sofa", "cat"))

    def test_cat_does_not_match_inside_scattered(self):
        self.assertFalse(term_matches("scattered glaze drips", "cat"))

    def test_cat_does_not_match_before_digit(self):
        self.assertFalse(term_matches("cat5 cable spool", "cat"))

    def test_cat_matches_standalone_word(self):
        self.assertTrue(term_matches("my cat sleeps in the studio", "cat"))

    def test_cat_matches_with_punctuation_and_edges(self):
        self.assertTrue(term_matches("cat!", "cat"))
        self.assertTrue(term_matches("a photo of the cat.", "cat"))
        self.assertTrue(term_matches("cat", "cat"))

    def test_empty_term_never_matches(self):
        self.assertFalse(term_matches("anything at all", ""))


class PhraseSeparatorTests(unittest.TestCase):
    def test_space_hyphen_underscore_are_interchangeable(self):
        for text in (
            "wheel throwing basics",
            "wheel-throwing basics",
            "wheel_throwing basics",
            "wheel   throwing basics",
            "wheel - throwing basics",
        ):
            with self.subTest(text=text):
                self.assertTrue(term_matches(text, "wheel throwing"))

    def test_joined_words_without_separator_do_not_match(self):
        self.assertFalse(term_matches("wheelthrowing basics", "wheel throwing"))

    def test_phrase_requires_word_boundaries(self):
        self.assertTrue(term_matches("new test tile rack", "test tile"))
        self.assertFalse(term_matches("latest tile rack", "test tile"))

    def test_long_phrase_with_flexible_separators(self):
        self.assertTrue(
            term_matches("five-nights-at-freddy fan art", "five nights at freddy")
        )

    def test_literal_hyphen_in_term_is_preserved(self):
        self.assertTrue(term_matches("made with dall-e today", "dall-e"))
        self.assertFalse(term_matches("made with dalle today", "dall-e"))


class MatchTermsTests(unittest.TestCase):
    def test_lowercases_text_and_collects_hits(self):
        hits = match_terms(
            "My CAT loves Wheel-Throwing", ["cat", "wheel throwing", "kiln"]
        )
        self.assertEqual(hits, ["cat", "wheel throwing"])

    def test_blank_terms_are_skipped(self):
        self.assertEqual(match_terms("cat", ["", "   "]), [])


if __name__ == "__main__":
    unittest.main()
