import json
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket

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
        activations = []
        try:
            self.assertTrue(primary.start_or_notify())
            primary.set_activation_handler(lambda: activations.append(True))

            started, error = self.forward(primary, None)
            self.assertFalse(started)
            self.assertEqual(error, "")
            self.pump(lambda: bool(activations))
            self.assertEqual(activations, [True])
        finally:
            primary.close()

    def pump(self, condition=lambda: True):
        for _ in range(10):
            self.app.processEvents()
        deadline = time.monotonic() + 0.5
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertTrue(condition())

    def primary(self):
        primary = SingleInstanceGuard(f"wolflauncher-test-{uuid4().hex}")
        self.assertTrue(primary.start_or_notify())
        self.addCleanup(primary.close)
        return primary

    def client(self, primary, frame):
        client = QLocalSocket()
        client.connectToServer(primary.server_name)
        self.assertTrue(client.waitForConnected(500))
        client.write(frame)
        client.waitForBytesWritten(500)
        return client

    def forward(self, primary, url):
        # Match two real launches. Blocking Qt socket waits in a Python thread
        # can retain the GIL needed by the primary's Python signal handlers.
        code = """
import json, sys
from PySide6.QtCore import QCoreApplication
from wolflauncher.single_instance import SingleInstanceGuard
app = QCoreApplication([])
guard = SingleInstanceGuard(sys.argv[1])
print(json.dumps([guard.start_or_notify(sys.argv[2] or None), guard.delivery_error]))
"""
        with subprocess.Popen(
            [sys.executable, "-c", code, primary.server_name, url or ""],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as child:
            self.pump(lambda: child.poll() is not None)
            output, error = child.communicate(timeout=2)
            self.assertEqual(child.returncode, 0, error)
        return json.loads(output)

    def test_existing_instance_receives_the_exact_link_once(self):
        primary = self.primary()
        urls, activations = [], []
        primary.set_activation_handler(lambda: activations.append(True))
        primary.set_url_handler(urls.append)
        url = "wolflauncher://join?v=1&host=203.0.113.10&game_port=2302&query_port=27016"
        secondary_started, error = self.forward(primary, url)
        self.assertFalse(secondary_started)
        self.assertEqual(error, "")
        self.pump(lambda: len(urls) == 1)
        self.assertEqual(urls, [url])
        self.assertEqual(activations, [True])
        self.assertEqual(primary._clients, {})

    def test_fragmented_frame_waits_for_completion_and_is_delivered_once(self):
        primary = self.primary()
        urls = []
        primary.set_url_handler(urls.append)
        frame = json.dumps({"action": "open_url", "url": "a-link"}).encode() + b"\n"
        split = len(frame) // 2
        client = self.client(primary, frame[:split])
        self.pump(lambda: bool(primary._clients))
        self.assertEqual(urls, [])
        client.write(frame[split:])
        client.waitForBytesWritten(500)
        self.pump(lambda: len(urls) == 1)
        self.assertEqual(urls, ["a-link"])

    def test_early_startup_links_are_bounded_and_delivered_when_handler_is_ready(self):
        primary = self.primary()
        for number in range(6):
            frame = json.dumps({"action": "open_url", "url": f"link-{number}"}).encode() + b"\n"
            client = self.client(primary, frame)
            self.pump()
            client.abort()
        self.assertEqual(primary._pending_urls, [f"link-{n}" for n in range(4)])
        urls = []
        primary.set_url_handler(urls.append)
        self.pump(lambda: len(urls) == 4)
        self.assertEqual(urls, [f"link-{n}" for n in range(4)])

    def test_malformed_oversized_and_repeated_ipc_fields_cannot_dispatch(self):
        primary = self.primary()
        urls, activations = [], []
        primary.set_activation_handler(lambda: activations.append(True))
        primary.set_url_handler(urls.append)
        frames = [
            b"not-json\n",
            b"[]\n",
            b'{"action":"launch","url":"test"}\n',
            b'{"action":"open_url","url":3}\n',
            b'{"action":"open_url","url":"x","extra":true}\n',
            b'{"action":"open_url","url":"one","url":"two"}\n',
            b'{"action":"open_url","url":"x"}\nextra',
            b"[" * 1800 + b"]" * 1800 + b"\n",
            b"x" * 5000,
        ]
        for frame in frames:
            client = self.client(primary, frame)
            self.pump()
            client.abort()
            self.pump(lambda: not primary._clients)
        self.assertEqual(urls, [])
        self.assertEqual(activations, [])

    def test_secondary_close_does_not_unlink_the_running_primary(self):
        primary = self.primary()
        secondary = SingleInstanceGuard(primary.server_name)
        with patch.object(secondary, "_notify_existing_instance", return_value=True):
            self.assertFalse(secondary.start_or_notify())
        secondary.close()
        self.assertEqual(self.forward(primary, None), [False, ""])
        self.assertTrue(primary.server.isListening())

    def test_activation_without_acknowledgement_is_reported(self):
        primary = self.primary()
        with patch.object(primary, "_read", side_effect=lambda socket: primary._finish(socket)):
            started, error = self.forward(primary, None)
        self.assertFalse(started)
        self.assertIn("did not confirm activation", error)

    def test_older_running_instance_without_acknowledgement_is_reported(self):
        primary = self.primary()
        with patch.object(primary, "_read", side_effect=lambda socket: primary._finish(socket)):
            started, error = self.forward(primary, "a-link")
        self.assertFalse(started)
        self.assertIn("did not confirm", error)


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
