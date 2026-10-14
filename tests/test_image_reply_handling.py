import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication

from wolflauncher.local_tools_feature import LocalToolsFeatureMixin
from wolflauncher.mods_feature import ModsFeatureMixin


class ImageReplyHandlingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_failed_or_closed_replies_are_not_read(self):
        for error, readable in (
            (QNetworkReply.OperationCanceledError, False),
            (QNetworkReply.ContentNotFoundError, True),
            (QNetworkReply.NoError, False),
        ):
            for editor in (False, True):
                with self.subTest(error=error, readable=readable, editor=editor):
                    reply = Mock()
                    reply.error.return_value = error
                    reply.isReadable.return_value = readable
                    window = SimpleNamespace(
                        mod_thumbnail_reply=reply,
                        editor_image_reply=reply,
                        _show_mod_thumbnail_placeholder=Mock(),
                    )
                    if editor:
                        LocalToolsFeatureMixin._finish_editor_image_load(window, reply)
                        self.assertIsNone(window.editor_image_reply)
                    else:
                        ModsFeatureMixin.finish_mod_thumbnail_load(window, reply)
                        self.assertIsNone(window.mod_thumbnail_reply)
                        window._show_mod_thumbnail_placeholder.assert_called_once_with()
                    reply.readAll.assert_not_called()
                    reply.deleteLater.assert_called_once_with()

    def test_replacing_request_detaches_reply_before_synchronous_abort_callback(self):
        reply = Mock()
        window = SimpleNamespace(
            mod_thumbnail_reply=reply,
            mod_detail_thumbnail=Mock(),
            _show_mod_thumbnail_placeholder=Mock(),
        )
        reply.abort.side_effect = lambda: ModsFeatureMixin.finish_mod_thumbnail_load(window, reply)

        ModsFeatureMixin.load_mod_thumbnail(window, "")

        self.assertIsNone(window.mod_thumbnail_reply)
        reply.readAll.assert_not_called()
        reply.error.assert_not_called()
        reply.deleteLater.assert_called_once_with()
        window._show_mod_thumbnail_placeholder.assert_called_once_with()
