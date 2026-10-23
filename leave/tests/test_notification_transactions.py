from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.db import transaction
from django.test import TestCase
from leave.threading import LeaveMailSendThread


class LeaveNotificationTransactionTests(TestCase):
    def thread(self):
        request = SimpleNamespace(
            get_host=lambda: "testserver", is_secure=lambda: False
        )
        return LeaveMailSendThread(request, Mock(), "request")

    def test_delivery_starts_only_after_commit(self):
        thread = self.thread()
        with patch("threading.Thread.start") as start:
            with self.captureOnCommitCallbacks(execute=True):
                thread.start()
                start.assert_not_called()
            start.assert_called_once()

    def test_rolled_back_changes_never_start_delivery(self):
        thread = self.thread()
        with patch("threading.Thread.start") as start:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        thread.start()
                        raise ValueError("Synthetic rollback")
                except ValueError:
                    pass
            start.assert_not_called()

    def test_delivery_closes_its_connection_even_when_sending_fails(self):
        thread = self.thread()
        with patch.object(
            thread,
            "_run_notifications",
            side_effect=RuntimeError("Synthetic mail failure"),
        ), patch("leave.threading.close_old_connections") as opened, patch(
            "leave.threading.connections.close_all"
        ) as closed:
            with self.assertRaises(RuntimeError):
                thread.run()
            opened.assert_called_once()
            closed.assert_called_once()
