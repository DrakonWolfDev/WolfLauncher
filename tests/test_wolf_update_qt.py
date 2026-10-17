import os
import threading
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QThread, QTimer
from PySide6.QtWidgets import QApplication

from wolf_update import CheckResult, CheckStatus
from wolf_update.qt import QtUpdateChecker


class Service:
    called_thread = None

    def check(self, *, manual=False, cancelled=None):
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
            self.assertIs(QThread.currentThread(), caller_thread)
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

    def test_cancelled_queued_result_cannot_finish_a_new_check(self):
        checker = QtUpdateChecker(Service())
        received = []
        checker.result_ready.connect(lambda *args: received.append(args))
        self.assertTrue(checker.check(manual=False))
        self.assertTrue(checker.wait(1000))
        # The first result is queued but has not reached the GUI event loop.
        checker.requestInterruption()
        self.assertTrue(checker.check(manual=True))
        self.assertTrue(checker.wait(1000))
        self.app.processEvents()
        self.assertEqual(len(received), 1)
        self.assertTrue(received[0][1])
        self.assertFalse(checker.is_running())

    def test_deleting_checker_discards_pending_delivery(self):
        checker = QtUpdateChecker(Service())
        received = []
        checker.result_ready.connect(lambda *args: received.append(args))
        self.assertTrue(checker.check())
        self.assertTrue(checker.wait(1000))
        checker.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(received, [])

    def test_interruption_releases_qt_worker_and_suppresses_late_result(self):
        release_transport = threading.Event()

        class StalledService:
            def check(self, *, manual=False, cancelled=None):
                release_transport.wait(2)
                if cancelled and cancelled():
                    return CheckResult(CheckStatus.CANCELLED)
                return CheckResult(CheckStatus.UP_TO_DATE)

        checker = QtUpdateChecker(StalledService())
        received = []
        checker.result_ready.connect(lambda *args: received.append(args))
        self.assertTrue(checker.check(manual=True))

        checker.requestInterruption()

        self.assertFalse(checker.is_running())
        self.assertTrue(checker.wait(500))
        release_transport.set()
        self.app.processEvents()
        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
