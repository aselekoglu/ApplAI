import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app.main import app
from api.app.services import ai_task_service


class AiTaskRoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tasks_patch = patch.object(ai_task_service, "tasks_dir", return_value=Path(self.tmp_dir.name))
        self.tasks_patch.start()

    def tearDown(self):
        self.tasks_patch.stop()
        self.tmp_dir.cleanup()

    def test_create_and_get_task(self):
        with patch.object(ai_task_service._executor, "submit") as submit_mock:
            response = self.client.post(
                "/ai-tasks",
                json={
                    "kind": "tailor_cv",
                    "title": "Tailor CV",
                    "related_label": "NRC",
                    "input": {
                        "master_id": "master",
                        "job_description": "Build AI automation for public-sector research workflows.",
                    },
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["task_id"].startswith("task_"))
        self.assertEqual(payload["kind"], "tailor_cv")
        submit_mock.assert_called_once_with(ai_task_service.run_task, payload["task_id"])

        get_response = self.client.get(f"/ai-tasks/{payload['task_id']}")

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["kind"], "tailor_cv")

    def test_list_tasks(self):
        ai_task_service.create_task(
            kind="tailor_cv",
            title="Tailor CV",
            related_label="NRC",
            input={"master_id": "master", "job_description": "JD"},
            enqueue=False,
        )

        response = self.client.get("/ai-tasks")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["tasks"]), 1)

    def test_list_tasks_clamps_limit_bounds(self):
        for index in range(3):
            ai_task_service.create_task(
                kind="tailor_cv",
                title=f"Tailor CV {index}",
                related_label="NRC",
                input={"master_id": "master", "job_description": "JD"},
                enqueue=False,
            )

        low_response = self.client.get("/ai-tasks?limit=0")
        high_response = self.client.get("/ai-tasks?limit=201")

        self.assertEqual(low_response.status_code, 200)
        self.assertEqual(low_response.json()["count"], 1)
        self.assertEqual(high_response.status_code, 200)
        self.assertEqual(high_response.json()["count"], 3)

    def test_get_missing_task_returns_404(self):
        response = self.client.get("/ai-tasks/task_missing")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
