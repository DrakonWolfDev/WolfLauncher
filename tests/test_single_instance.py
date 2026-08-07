import unittest
from uuid import uuid4

from PySide6.QtCore import QCoreApplication

from wolflauncher.single_instance import SingleInstanceGuard, activate_window


class ActivateWindowTests(unittest.TestCase):
    def test_restores_a_minimized_window_before_raising_it(self):
        window = FakeWindow(minimized=True)

        activate_window(window)

        self.assertEqual(window.calls, ["showNormal", "raise", "activate"])

    def test_shows_an_unminimized_window_before_raising_it(self):
        window = FakeWindow(minimized=False)

        activate_window(window)

        self.assertEqual(window.calls, ["show", "raise", "activate"])


class SingleInstanceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_second_instance_notifies_the_primary_instance(self):
        server_name = f"wolflauncher-test-{uuid4().hex}"
        primary = SingleInstanceGuard(server_name)
        secondary = SingleInstanceGuard(server_name)
        activations = []
        try:
            self.assertTrue(primary.start_or_notify())
            primary.set_activation_handler(lambda: activations.append(True))

            self.assertFalse(secondary.start_or_notify())
            for _ in range(10):
                self.app.processEvents()
            self.assertEqual(activations, [True])
        finally:
            primary.close()


class FakeWindow:
    def __init__(self, minimized):
        self.minimized = minimized
        self.calls = []

    def isMinimized(self):
        return self.minimized

    def showNormal(self):
        self.calls.append("showNormal")

    def show(self):
        self.calls.append("show")

    def raise_(self):
        self.calls.append("raise")

    def activateWindow(self):
        self.calls.append("activate")
