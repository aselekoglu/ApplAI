from __future__ import annotations

import unittest

from api.app.schemas.jobs import ScoreJobRequest
from api.app.services.job_scoring_service import score_job


class JobScoringServiceTest(unittest.TestCase):
    def test_score_job_returns_contract_fields(self) -> None:
        result = score_job(
            ScoreJobRequest(
                job_description="Python developer role building REST APIs, React dashboards, SQL reports, and automation.",
                company_name="ExampleCo",
                job_title="Software Developer",
            )
        )

        self.assertTrue(result.job_id.startswith("job_"))
        self.assertGreaterEqual(result.match_score, 0)
        self.assertLessEqual(result.match_score, 100)
        self.assertIn(result.recommendation, {"apply", "skip", "worth_20_minutes"})
        self.assertIsInstance(result.reasons, list)
        self.assertIsInstance(result.concerns, list)
        self.assertIsInstance(result.missing_keywords, list)
        self.assertIsInstance(result.best_evidence_block_ids, list)

    def test_score_job_is_deterministic_for_same_input(self) -> None:
        payload = ScoreJobRequest(job_description="Python SQL React automation")

        first = score_job(payload)
        second = score_job(payload)

        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(first.match_score, second.match_score)
        self.assertEqual(first.recommendation, second.recommendation)


if __name__ == "__main__":
    unittest.main()
