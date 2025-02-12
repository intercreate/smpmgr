"""Build a one-file executable of the application."""

import os
import platform
import shutil
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Final

from git import Repo
from rich import print

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

exe_name: Final[str] = "smpmgr.exe" if platform.system() == "Windows" else "smpmgr"

print()
print("[bold green]Building distributable package for smpmgr...")
print(f"[bold cyan]Version: {version}, Git SHA: {git_hash}")
print()

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

    # build the portable
    assert (
        subprocess.run(
            (
                "pyinstaller",
                "--add-data",
                f"dist/smpmgr-{version}:smpmgr",
                "--copy-metadat=smpmgr",
                "--copy-metadata=readchar",
                "--name=smpmgr",
                "--collect-submodules=shellingham",
                "--collect-submodules=readchar",
                "--hidden-import=readchar",
                "smpmgr/__main__.py",
            )
            + (
                "--hidden-import=winrt.windows.foundation.collections",  # https://github.com/intercreate/smpmgr/issues/34 # noqa: E501
            )
            if sys.platform == "win32"
            else ()
        ).returncode
        == 0
    )

    # run the executable and check the version
    assert (
        f"Version {version}"
        in subprocess.run(["dist/smpmgr/smpmgr", "--help"], capture_output=True).stdout.decode()
    )

    platform_system: Final = platform.system().lower()
    platform_name: Final = "macos" if platform_system == "darwin" else platform_system

    # create the folder
    dist_path: Final = Path(
        "dist", f"smpmgr-{version}-{platform_name}-{platform.machine().lower()}"
    )
    os.makedirs(dist_path, exist_ok=True)

    # copy the executable to the folder
    shutil.copytree(Path("dist", "smpmgr"), Path(dist_path), dirs_exist_ok=True)

    # create a VERSION.txt stamp
    with open(Path(dist_path, "VERSION.txt"), "w") as f:
        f.writelines(
            (
                "Simple Management Protocol Manager (smpmgr)\n",
                "\n",
                "Copyright (c) Intercreate, Inc. 2023-2025\n",
                "SPDX-License-Identifier: Apache-2.0\n",
                "\n",
                "https://www.intercreate.io/\n",
                "https://github.com/intercreate/smpmgr\n",
                "\n",
                f"Version: {version}\n",
                f"Git SHA: {git_hash}\n",
                f"Build date: {datetime.now()}\n",
                f"Build platform: {platform.platform()}\n",
                f"Python version: {sys.version}\n",
            )
        )

    # copy the LICENSE
    shutil.copy("LICENSE", Path(dist_path, "LICENSE"))

    # make a ZIP archive
    with zipfile.ZipFile(str(dist_path) + ".zip", "w") as zip_file:
        for path, _, files in os.walk(dist_path):
            for file in files:
                zip_file.write(Path(path, file), Path(path, file).relative_to(dist_path))

except Exception as e:  # save the exception to raise it later
    exception = e

finally:  # always remove the poetry-version-plugin
    assert subprocess.run(["poetry", "self", "remove", "poetry-version-plugin"]).returncode == 0

if exception is not None:
    print("An exception occurred during the build\n")
    traceback.print_tb(exception.__traceback__)

    print("\nExiting with error 1.")
    sys.exit(1)
else:
    print("\nBuild successful.")
    print(f"Portable build saved to {dist_path}.zip\n")
    sys.exit(0)
