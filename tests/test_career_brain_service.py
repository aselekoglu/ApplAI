from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api.app.config import settings
from api.app.schemas.career_brain import CareerBrainProfile
from api.app.services.career_brain_service import (
    career_brain_profile_path,
    ensure_career_brain_profile,
    load_career_brain_profile,
    update_career_brain_profile,
)


class CareerBrainServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._original_docs_dir = settings.docs_dir
        self._tmp = tempfile.TemporaryDirectory()
        settings.docs_dir = self._tmp.name

    def tearDown(self) -> None:
        settings.docs_dir = self._original_docs_dir
        self._tmp.cleanup()

    def test_default_seed_is_created_and_loadable(self) -> None:
        path = career_brain_profile_path()
        self.assertFalse(path.exists())

        profile = ensure_career_brain_profile()

        self.assertEqual(profile.owner, "Ata Selekoglu")
        self.assertTrue(profile.evidence_blocks)
        self.assertTrue(path.exists())
        loaded = load_career_brain_profile()
        self.assertEqual(loaded.owner, profile.owner)
        self.assertEqual(loaded.evidence_blocks[0].block_id, profile.evidence_blocks[0].block_id)

    def test_update_persists_profile(self) -> None:
        profile = ensure_career_brain_profile()
        updated = CareerBrainProfile.model_validate(profile.model_dump())
        updated.role_preferences.preferred_roles.append("AI Technical Analyst")

        persisted, path = update_career_brain_profile(updated)

        self.assertEqual(Path(path), career_brain_profile_path())
        self.assertIn("AI Technical Analyst", persisted.role_preferences.preferred_roles)
        reloaded = load_career_brain_profile()
        self.assertIn("AI Technical Analyst", reloaded.role_preferences.preferred_roles)


if __name__ == "__main__":
    unittest.main()
