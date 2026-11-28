import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow, QMenuBar, QWidget

from src.gui.menu_bar import MenuBar


class MenuBarLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_menu_and_former_toolbar_controls_share_one_widget(self):
        menu_bar = MenuBar()

        self.assertIsInstance(menu_bar, QWidget)
        self.assertIsInstance(menu_bar.menu_bar, QMenuBar)
        self.assertEqual(len(menu_bar.menu_bar.actions()), 4)
        self.assertEqual(menu_bar.search_field.objectName(), "quickSearchField")
        self.assertIsNotNone(menu_bar.left_show_btn)
        self.assertIsNotNone(menu_bar.bottom_show_btn)
        self.assertIsNotNone(menu_bar.right_show_btn)

        menu_bar.deleteLater()
        self.app.processEvents()

    def test_composite_menu_widget_leaves_space_for_central_content(self):
        window = QMainWindow()
        menu_bar = MenuBar(parent=window)
        central = QWidget()
        window.setMenuWidget(menu_bar)
        window.setCentralWidget(central)
        window.resize(1200, 800)
        window.show()
        self.app.processEvents()

        self.assertTrue(menu_bar.isVisible())
        self.assertTrue(menu_bar.search_field.isVisible())
        self.assertTrue(central.isVisible())
        self.assertGreater(central.geometry().top(), menu_bar.geometry().top())

        window.close()
        window.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
