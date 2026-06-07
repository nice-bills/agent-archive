"""Local dev entrypoint."""

from archive_detective.env import load_project_env
from archive_detective.ui import launch

load_project_env()

if __name__ == "__main__":
    launch()
