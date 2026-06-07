"""Hugging Face Space entrypoint — custom gr.Server board."""

from __future__ import annotations

from archive_detective.env import load_project_env
from archive_detective.server_app import launch

load_project_env()

if __name__ == "__main__":
    launch(server_name="0.0.0.0")
