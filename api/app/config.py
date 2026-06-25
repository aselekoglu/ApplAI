from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _positive_int_env(name: str, fallback: int) -> int:
    try:
        value = int((os.getenv(name) or "").strip())
    except ValueError:
        return fallback
    return value if value > 0 else fallback


@dataclass
class Settings:
    docs_dir: str = field(default_factory=lambda: os.getenv("APPLAI_DOCS_DIR", "docs"))
    runs_subdir: str = field(default_factory=lambda: os.getenv("APPLAI_RUNS_SUBDIR", "runs"))
    ai_tasks_subdir: str = field(default_factory=lambda: os.getenv("APPLAI_AI_TASKS_SUBDIR", "ai_tasks"))
    default_model: str = field(default_factory=lambda: os.getenv("APPLAI_DEFAULT_MODEL", "gemini-2.5-flash"))
    gemini_default_model: str = field(
        default_factory=lambda: os.getenv(
            "APPLAI_GEMINI_DEFAULT_MODEL",
            os.getenv("APPLAI_DEFAULT_MODEL", "gemini-2.5-flash"),
        )
    )
    ai_task_max_workers: int = field(default_factory=lambda: _positive_int_env("APPLAI_AI_TASK_MAX_WORKERS", 1))
    cors_origins: List[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "APPLAI_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if origin.strip()
        ]
    )
    cors_origin_regex: str = field(
        default_factory=lambda: os.getenv(
            "APPLAI_CORS_ORIGIN_REGEX",
            r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        )
    )

    @property
    def json_exports_dir(self) -> str:
        return os.path.join(self.docs_dir, "json_exports")

    @property
    def master_configs_dir(self) -> str:
        return os.path.join(self.docs_dir, "master_configs")

    @property
    def runs_dir(self) -> str:
        return os.path.join(self.docs_dir, self.runs_subdir)

    @property
    def ai_tasks_dir(self) -> str:
        return os.path.join(self.docs_dir, self.ai_tasks_subdir)

    @property
    def career_brain_dir(self) -> str:
        return os.path.join(self.docs_dir, "career_brain")

    @property
    def tailored_examples_dir(self) -> str:
        return os.path.join(self.docs_dir, "tailored_examples")

    @property
    def jobs_dir(self) -> str:
        return os.path.join(self.docs_dir, "jobs")


settings = Settings()
