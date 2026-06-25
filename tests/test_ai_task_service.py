import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.app.config import Settings
from api.app.schemas.ai_tasks import AiTaskCreateRequest, AiTaskRecord
from api.app.services import ai_task_service


class AiTaskSchemaTest(unittest.TestCase):
    def test_create_request_requires_known_kind(self):
        payload = AiTaskCreateRequest(
            kind="tailor_cv",
            title="Tailor CV",
            related_label="NRC - AI Analyst",
            input={"master_id": "master", "job_id": "job_abc"},
        )

        self.assertEqual(payload.kind, "tailor_cv")
        self.assertEqual(payload.input["master_id"], "master")

    def test_record_defaults_to_queued(self):
        record = AiTaskRecord.new(
            kind="render_cv",
            title="Render CV",
            related_label="Trend Micro",
            input={"run_id": "run_123"},
        )

        self.assertTrue(record.task_id.startswith("task_"))
        self.assertEqual(record.status, "queued")
        self.assertIsNone(record.result)
        self.assertEqual(record.events[0].message, "Queued task.")


class AiTaskConfigTest(unittest.TestCase):
    def test_invalid_worker_env_values_fall_back_to_one(self):
        for value in ["", "abc", "0", "-2"]:
            with self.subTest(value=value):
                with patch.dict(os.environ, {"APPLAI_AI_TASK_MAX_WORKERS": value}):
                    self.assertEqual(Settings().ai_task_max_workers, 1)


class AiTaskServiceTest(unittest.TestCase):
    def test_create_persists_task_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="tailor_cv",
                    title="Tailor CV",
                    related_label="NRC",
                    input={"master_id": "master"},
                    enqueue=False,
                )

                saved = Path(tmp, f"{record.task_id}.json")
                self.assertTrue(saved.exists())
                loaded = ai_task_service.get_task(record.task_id)
                self.assertEqual(loaded.status, "queued")
                self.assertEqual(loaded.input["master_id"], "master")

    def test_mark_succeeded_sets_restore_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="render_cv",
                    title="Render CV",
                    input={"run_id": "run_1"},
                    enqueue=False,
                )

                updated = ai_task_service.mark_task_succeeded(
                    record.task_id,
                    result={"run_id": "run_1"},
                    restore_path="/runs",
                    restore_state={"selectedRunId": "run_1"},
                )

                self.assertEqual(updated.status, "succeeded")
                self.assertEqual(updated.result["run_id"], "run_1")
                self.assertEqual(updated.restore.path, "/runs")

    def test_cancel_queued_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="tailor_cv",
                    title="Tailor CV",
                    input={},
                    enqueue=False,
                )

                cancelled = ai_task_service.cancel_task(record.task_id)

                self.assertEqual(cancelled.status, "cancelled")
                self.assertEqual(cancelled.events[-1].message, "Cancelled before start.")

    def test_list_tasks_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                for index in range(3):
                    ai_task_service.create_task(
                        kind="tailor_cv",
                        title=f"Tailor CV {index}",
                        input={},
                        enqueue=False,
                    )

                records = ai_task_service.list_tasks(limit=2)

                self.assertEqual(len(records), 2)

    def test_cancel_non_queued_task_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="tailor_cv",
                    title="Tailor CV",
                    input={},
                    enqueue=False,
                )
                ai_task_service.update_task_status(record.task_id, "running", "Task started.")

                with self.assertRaisesRegex(ValueError, "Only queued tasks can be cancelled"):
                    ai_task_service.cancel_task(record.task_id)

    def test_run_task_does_not_overwrite_racing_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="tailor_cv",
                    title="Tailor CV",
                    input={},
                    enqueue=False,
                )
                handler_calls = []

                def handler(task):
                    handler_calls.append(task.task_id)
                    return {"ok": True}, None

                original_get_task = ai_task_service.get_task
                calls = {"count": 0}

                def get_task_with_racing_cancel(task_id):
                    loaded = original_get_task(task_id)
                    if calls["count"] == 0:
                        calls["count"] += 1
                        cancelled = loaded.model_copy(
                            update={
                                "status": "cancelled",
                                "finished_at": loaded.updated_at,
                            }
                        )
                        ai_task_service.save_task(cancelled)
                        return loaded
                    calls["count"] += 1
                    return original_get_task(task_id)

                with patch.dict(ai_task_service._handlers, {"tailor_cv": handler}, clear=True):
                    with patch.object(ai_task_service, "get_task", side_effect=get_task_with_racing_cancel):
                        result = ai_task_service.run_task(record.task_id)

                self.assertEqual(result.status, "cancelled")
                self.assertEqual(handler_calls, [])
                self.assertEqual(ai_task_service.get_task(record.task_id).status, "cancelled")

    def test_create_task_enqueues_gemini_interaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                with patch.object(ai_task_service._executor, "submit") as submit_mock:
                    record = ai_task_service.create_task(
                        kind="gemini_interaction",
                        title="Gemini Interaction",
                        input={"input": "Hello"},
                    )

                self.assertEqual(record.kind, "gemini_interaction")
                submit_mock.assert_called_once_with(ai_task_service.run_task, record.task_id)


class AiTaskHandlerTest(unittest.TestCase):
    def test_score_handler_forces_saved_draft_for_restore_target(self):
        fake_response = type(
            "ScoreResponse",
            (),
            {"model_dump": lambda self: {"job_id": "job_abc"}, "job_id": "job_abc"},
        )()

        with patch("api.app.services.ai_task_service.score_job", return_value=fake_response) as score_job_mock:
            record = AiTaskRecord.new(
                kind="score_job",
                title="Score Job",
                input={"job_description": "Build AI automation", "company_name": "NRC"},
            )

            result, restore = ai_task_service.handle_score_job(record)

            request = score_job_mock.call_args.args[0]
            self.assertIs(request.save_draft, True)
            self.assertEqual(result["job_id"], "job_abc")
            self.assertEqual(restore.state["jobId"], "job_abc")

    def test_tailor_handler_returns_run_restore(self):
        from api.app.schemas.ai_tasks import AiTaskRestoreTarget

        fake_response = type(
            "TailorResponse",
            (),
            {"model_dump": lambda self: {"run_id": "run_abc"}, "run_id": "run_abc"},
        )()

        with patch("api.app.services.ai_task_service.run_tailoring_job", return_value=fake_response):
            record = AiTaskRecord.new(
                kind="tailor_cv",
                title="Tailor CV",
                input={
                    "master_id": "master",
                    "job_description": "JD",
                    "options": {"model_name": "gemini-2.5-flash"},
                },
            )

            result, restore = ai_task_service.handle_tailor_cv(record)

            self.assertEqual(result["run_id"], "run_abc")
            self.assertIsInstance(restore, AiTaskRestoreTarget)
            self.assertEqual(restore.state["selectedRunId"], "run_abc")

    def test_render_handler_returns_run_restore(self):
        fake_export = type(
            "ExportResponse",
            (),
            {"model_dump": lambda self: {"run_id": "run_abc", "pdf_path": "docs/out.pdf"}},
        )()

        with patch("api.app.services.ai_task_service.export_run", return_value=fake_export):
            record = AiTaskRecord.new(kind="render_cv", title="Render CV", input={"run_id": "run_abc"})

            result, restore = ai_task_service.handle_render_cv(record)

            self.assertEqual(result["pdf_path"], "docs/out.pdf")
            self.assertTrue(restore.state["showExports"])

    def test_gemini_interaction_handler_validates_request_and_returns_no_restore(self):
        expected_result = {"id": "interaction_1", "output_text": "hello"}

        with patch(
            "api.app.services.ai_task_service.create_text_interaction",
            return_value=expected_result,
        ) as create_mock:
            record = AiTaskRecord.new(
                kind="gemini_interaction",
                title="Gemini Interaction",
                input={"input": "hello", "model": "gemini-2.5-flash"},
            )

            result, restore = ai_task_service.handle_gemini_interaction(record)

        create_mock.assert_called_once()
        request = create_mock.call_args.args[0]
        self.assertEqual(request.input, "hello")
        self.assertEqual(request.model, "gemini-2.5-flash")
        self.assertFalse(request.store)
        self.assertEqual(result, expected_result)
        self.assertIsNone(restore)


if __name__ == "__main__":
    unittest.main()
