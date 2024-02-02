"""Build a one-file executable of the application."""

import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Final

from git import Repo

git: Final = Repo(os.getcwd()).git
git_hash: Final[str | None] = git.describe(dirty="+", always=True, exclude="*")
if git_hash is None:
    raise RuntimeError("Could not get git hash")
if git_hash.endswith("+"):
    raise RuntimeError("Uncommitted changes")

git_tag: Final[str | None] = git.describe(dirty="+", always=True, tags=True)
if git_tag is None:
    raise RuntimeError("Could not get git tag")
else:
    version: Final[str] = git_tag

print(f"Building smpgmr {version}, Git SHA {git_hash}\n")

assert subprocess.run(["poetry", "self", "add", "poetry-version-plugin"]).returncode == 0

exception = None

try:
    # build the application
    assert subprocess.run(["poetry", "install"]).returncode == 0
    assert subprocess.run(["poetry", "build"]).returncode == 0

    # find the sdist archive and unpack it
    archives = list(Path("dist").glob(f"smpmgr-{version}.*"))
    assert len(archives) == 1
    shutil.unpack_archive(archives[0], "dist")

    # build the one-file executable
    assert (
        subprocess.run(
            [
                "pyinstaller",
                "--onefile",
                "--add-data",
                f"dist/smpmgr-{version}:smpmgr",
                "--copy-metadata",
                "smpmgr",
                "--name=smpmgr",
                "--collect-submodules",
                "shellingham",
                "smpmgr/__main__.py",
            ]
        ).returncode
        == 0
    )

    # run the executable and check the version
    assert (
        f"Version {version}"
        in subprocess.run(["dist/smpmgr", "--help"], capture_output=True).stdout.decode()
    )

except Exception as e:  # save the exception to raise it later
    exception = e

finally:  # always remove the poetry-version-plugin
    assert subprocess.run(["poetry", "self", "remove", "poetry-version-plugin"]).returncode == 0

if exception is not None:
    print("An exception occurred during the build\n")
    traceback.print_tb(exception.__traceback__)

    print("\nExiting with error 1.")
    sys.exit(1)
