"""Local dev entrypoint — custom gr.Server board UI."""

from archive_detective.env import load_project_env
from archive_detective.server_app import launch

load_project_env()

if __name__ == "__main__":
    launch()
