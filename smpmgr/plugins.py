"""Runtime discovery and execution of user-provided plugins."""

import logging
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Final, NamedTuple

import typer

logger: Final = logging.getLogger(__name__)


class Plugin(NamedTuple):
    """An SMP group plugin."""

    app: typer.Typer
    path: Path


def get_plugins(argv: list[str]) -> tuple[Plugin, ...]:
    """Returns a tuple of plugin paths and removes them from `argv`."""

    logger.debug(f"{argv=}")
    paths: Final[list[Path]] = []
    for arg in argv[:]:
        if arg.startswith("--plugin-path="):
            logger.debug(f"Found plugin path argument: {arg}")
            path = Path(arg.split("=")[1]).expanduser().resolve()
            if path.is_dir():
                logger.debug(f"Adding plugin path and removing from argv: {path}")
                paths.append(path)
                argv.remove(arg)
            else:
                raise ValueError(f"Invalid plugin path: {path}")

    files: Final = tuple(file for path in paths for file in path.glob("*_group.py"))

    plugins: Final[list[Plugin]] = []
    for file in files:
        if (spec := spec_from_file_location(file.stem, file)) and spec.loader:
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            raise ImportError(f"Could not load module from {file}")
        app = getattr(module, "app", None)
        if app is None:
            raise ImportError(f"Module {file} does not have an 'app' attribute")
        if not isinstance(app, typer.Typer):
            raise TypeError(f"Module {file} 'app' attribute is not a typer.Typer")
        plugins.append(Plugin(app=app, path=file))

    logger.debug(f"Plugins found: {plugins}")

    return tuple(plugins)
