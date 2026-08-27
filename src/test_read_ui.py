"""uia_is_useful must reject Cursor/VS Code chrome so OCR can run."""

import unittest

from read_ui import uia_is_useful


class UiaIsUsefulTests(unittest.TestCase):
    def test_editor_group_empty_is_junk(self):
        self.assertFalse(uia_is_useful(["Editor Group 1 (empty)"]))

    def test_editor_group_numbered_is_junk(self):
        self.assertFalse(uia_is_useful(["Editor Group 2"]))

    def test_model_name_is_useful(self):
        self.assertTrue(uia_is_useful(["Composer 2.5"]))

    def test_gpt_name_is_useful(self):
        self.assertTrue(uia_is_useful(["GPT-5.4"]))

    def test_model_plus_editor_group_ancestor_is_useful(self):
        self.assertTrue(uia_is_useful(["Composer 2.5", "Editor Group 1 (empty)"]))

    def test_chrome_hwnd_is_junk(self):
        self.assertFalse(uia_is_useful(["Chrome_WidgetWin_1"]))


if __name__ == "__main__":
    unittest.main()
