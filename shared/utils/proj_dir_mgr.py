import logging
import os
import subprocess
from pathlib import Path


class ProjectDirBulder:
    def __init__(
        self,
        system: str,
        gitlab_url: str,
        logger: logging.Logger,
    ):
        self.system = system
        self.gitlab_url = gitlab_url
        self.logger = logger

        self._target_path: str = None
        self.progect_name = "dwa"
        self.proj_directory = "Projects"

    @property
    def target_path(self):
        if self._target_path is None:
            current_path = str(Path().resolve())
            path_root_directory = "/" + current_path.parts[1]
            path_app_dir = current_path.parts[2]
            if path_app_dir.lower() == "users":
                path_directory = os.path.join(
                    path_root_directory, path_app_dir, current_path.parts[3], "dwa", self.system.upper()
                )
            else:
                path_directory = os.path.join(path_root_directory, "Projects", "dwa", self.system.upper())
            self._target_path = path_directory
            self.logger.info(f"Target path: {self._target_path}")
        return self._target_path

    def _add_gitlab_directory(self):
        try:
            # Initialize git repository if not already initialized
            subprocess.run(["git", "init", self.target_path], check=True)
            # Add remote origin for GitLab
            subprocess.run(["git", "-C", self.target_path, "remote", "add", "origin", self.gitlab_url], check=True)
            self.logger.info(f"GitLab remote added to {self.target_path}")
        except Exception as e:
            self.logger.info(f"Error adding GitLab directory: {e}")

    def save_file(self, file, target_path):
        try:
            # os.makedirs(target_path, exist_ok=True)
            sql_file_path = os.path.join(target_path, "query.sql")
            with open(sql_file_path, "w") as f:
                f.write(file)
            self.logger.info(f"File saved at: {sql_file_path}")
            self.logger.info(f"Directory exists: {os.path.exists(target_path)}")
            self.logger.info(f"File exists: {os.path.exists(sql_file_path)}")
        except Exception as e:
            self.logger.error(f"Error saving file: {e}")

    def create_and_clone_git(self):
        try:
            os.makedirs(self.target_path, exist_ok=True)
            self._add_gitlab_directory()
        except Exception as e:
            self.logger.info(f"Error creating and cloning Git repository: {e}")

    def push_to_gitlab(self, commit_message="Auto-commit from Databricks"):
        try:
            subprocess.run(["git", "-C", self.target_path, "add", "."], check=True)
            subprocess.run(["git", "-C", self.target_path, "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "-C", self.target_path, "push", "origin", "master"], check=True)
            self.logger.info(f"Changes pushed to GitLab remote for {self.target_path}")
        except Exception as e:
            self.logger.error(f"Error pushing to GitLab: {str(e)[:200]}")


# proj_dir_builder = ProjectDirBulder(
#     system="POC", gitlab_url="hhttps://git.example.com/repos/edh-group/dwa.git", logger=default_logger
# )
# proj_dir_builder.create_and_clone_git()
