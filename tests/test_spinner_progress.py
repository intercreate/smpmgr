import io

import pytest
from rich.console import Console

from smpmgr.common import spinner_progress


def _render(encoding: str, *, legacy_windows: bool = False) -> str:
    raw = io.BytesIO()
    console = Console(
        file=io.TextIOWrapper(raw, encoding=encoding),
        force_terminal=True,
        legacy_windows=legacy_windows,
    )
    with spinner_progress(console) as progress:
        progress.add_task(description="Connecting...", total=None)
        progress.refresh()
    console.file.flush()
    return raw.getvalue().decode(encoding)


@pytest.mark.parametrize("encoding", ["cp1252", "ascii"])
def test_spinner_progress_draws_ascii_on_a_non_utf_console(encoding: str) -> None:
    assert _render(encoding).isascii()


def test_spinner_progress_draws_ascii_on_a_legacy_windows_console() -> None:
    assert _render("utf-8", legacy_windows=True).isascii()


def test_spinner_progress_keeps_the_braille_spinner_on_a_utf8_console() -> None:
    assert any("⠀" <= c <= "⣿" for c in _render("utf-8"))
