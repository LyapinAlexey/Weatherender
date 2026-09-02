from unittest.mock import MagicMock, patch

from weatherender.WEB.scheduler import (
    init_scheduler,
    run_dbclear_job,
    try_acquire_leadership,
)


class TestScheduler:
    def test_returns_true_when_file_absent(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        result = try_acquire_leadership(str(lock_file))
        assert result is True
        assert lock_file.exists()

    def test_returns_false_when_file_exist(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        result = try_acquire_leadership(str(lock_file))
        assert result is False

    @patch("weatherender.WEB.scheduler.clear")
    @patch("weatherender.WEB.scheduler.SessionLocal")
    def test_run_dbclear_job_calls_clear_with_session(
        self, mock_session_local, mock_clear
    ):
        fake_session = MagicMock()
        mock_session_local.return_value = fake_session
        run_dbclear_job()

        mock_session_local.assert_called_once()
        mock_clear.assert_called_once_with(fake_session)

    @patch("weatherender.WEB.scheduler.BackgroundScheduler")
    @patch("weatherender.WEB.scheduler.try_acquire_leadership", return_value=False)
    def test_scheduler_not_started_when_not_leader(
        self, mock_leadership, mock_scheduler_cls
    ):
        init_scheduler()
        mock_scheduler_cls.assert_not_called()

    @patch("weatherender.WEB.scheduler.BackgroundScheduler")
    @patch("weatherender.WEB.scheduler.try_acquire_leadership", return_value=True)
    def test_scheduler_started_when_leader_exist(
        self, mock_leadership, mock_scheduler_cls
    ):
        init_scheduler()
        mock_instance = mock_scheduler_cls.return_value
        mock_instance.add_job.assert_called_once_with(
            run_dbclear_job, "interval", days=7
        )
        mock_instance.start.assert_called_once()
