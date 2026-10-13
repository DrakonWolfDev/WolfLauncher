import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtWidgets import QApplication

from wolf_update import CheckResult, CheckStatus
from wolf_update.qt import QtUpdateChecker


class Service:
    called_thread = None

    def check(self, *, manual=False):
        self.called_thread = QThread.currentThread()
        return CheckResult(CheckStatus.UP_TO_DATE, message=str(manual))


class QtUpdateCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_checker_returns_result_without_running_service_on_caller_thread(self):
        service = Service()
        checker = QtUpdateChecker(service)
        caller_thread = self.app.thread()
        loop = QEventLoop()
        received = []

        def ready(result, manual):
            received.append((result, manual))

        checker.result_ready.connect(ready)
        self.assertTrue(checker.check(manual=True))
        self.assertTrue(checker.is_running())
        self.assertFalse(checker.check(manual=False))
        QTimer.singleShot(2000, loop.quit)
        loop.exec()

        self.assertTrue(received)
        self.assertIs(received[0][0].status, CheckStatus.UP_TO_DATE)
        self.assertTrue(received[0][1])
        self.assertIsNot(service.called_thread, caller_thread)

    def test_repeated_completed_checks_destroy_workers_on_their_own_threads(self):
        checker = QtUpdateChecker(Service())

        for _ in range(25):
            loop = QEventLoop()
            checker.result_ready.connect(loop.quit)
            self.assertTrue(checker.check())
            QTimer.singleShot(2000, loop.quit)
            loop.exec()
            self.app.processEvents()
            self.assertFalse(checker.is_running())
            checker.result_ready.disconnect(loop.quit)


if __name__ == "__main__":
    unittest.main()
