"""Tests for the decision to mark an uploaded image for a test in `upgrade`.

Regression coverage for https://github.com/intercreate/smpmgr/issues/116: with an application's SMP
server and MCUboot in direct-XIP with revert, `upgrade --slot 0` didn't mark the upload, and MCUboot
erased it as faulty.
"""

from typing import Final

import pytest
from smp.image_management import ImageState

from smpmgr.image_management import needs_test_mark

RUNNING: Final = bytes([0x11] * 32)
UPLOADED: Final = bytes([0x22] * 32)
OTHER: Final = bytes([0x33] * 32)


def app_server_states(*, running_slot: int, uploaded_slot: int) -> list[ImageState]:
    """The image states an application's SMP server reports after an upload."""

    return [
        ImageState(image=0, slot=running_slot, version="1.0.0", hash=RUNNING, active=True),
        ImageState(image=0, slot=uploaded_slot, version="1.0.1", hash=UPLOADED, active=False),
    ]


def serial_recovery_states() -> list[ImageState]:
    """The image states MCUboot's serial recovery reports: no image is active."""

    return [
        ImageState(slot=0, version="1.0.1", hash=UPLOADED, bootable=True),
        ImageState(slot=1, version="1.0.0", hash=RUNNING, bootable=True),
    ]


@pytest.mark.parametrize("slot", [0, 1])
@pytest.mark.parametrize("running_slot, uploaded_slot", [(0, 1), (1, 0)])
def test_app_server_marks_upload_whatever_slot(
    slot: int, running_slot: int, uploaded_slot: int
) -> None:
    images = app_server_states(running_slot=running_slot, uploaded_slot=uploaded_slot)

    assert needs_test_mark(images, UPLOADED, slot)


@pytest.mark.parametrize("slot", [0, 1])
def test_app_server_skips_running_image(slot: int) -> None:
    images = app_server_states(running_slot=0, uploaded_slot=1)

    assert not needs_test_mark(images, RUNNING, slot)


@pytest.mark.parametrize("slot, expected", [(0, False), (1, True)])
def test_serial_recovery_decides_by_slot(slot: int, expected: bool) -> None:
    assert needs_test_mark(serial_recovery_states(), UPLOADED, slot) is expected


@pytest.mark.parametrize("slot, expected", [(0, False), (1, True)])
def test_upload_not_found_decides_by_slot(slot: int, expected: bool) -> None:
    images = app_server_states(running_slot=0, uploaded_slot=1)

    assert needs_test_mark(images, OTHER, slot) is expected


@pytest.mark.parametrize("slot, expected", [(0, False), (1, True)])
def test_no_images_decides_by_slot(slot: int, expected: bool) -> None:
    assert needs_test_mark([], UPLOADED, slot) is expected
