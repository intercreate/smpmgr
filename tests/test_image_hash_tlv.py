"""Tests for discovery of the MCUboot image hash TLV.

Regression coverage for https://github.com/intercreate/smpmgr/issues/109: NCS sysbuild
signs nRF54L / nRF54H / nRF71 images with SHA512, so a SHA256-only lookup rejects them.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Final, NamedTuple

import pytest
from smpclient.mcuboot import (
    IMAGE_HEADER_STRUCT,
    IMAGE_MAGIC,
    IMAGE_TLV,
    IMAGE_TLV_INFO_MAGIC,
    IMAGE_TLV_INFO_STRUCT,
    IMAGE_TLV_PROT_INFO_MAGIC,
    IMAGE_TLV_STRUCT,
    ImageInfo,
)
from typer.testing import CliRunner

from smpmgr.image_management import IMAGE_HASH_TLV_NAMES, IMAGE_HASH_TLVS, get_image_hash_tlv
from smpmgr.main import app

IMAGE_BODY: Final = bytes(range(64))


class TLV(NamedTuple):
    type: int
    value: bytes

    def __bytes__(self) -> bytes:
        return IMAGE_TLV_STRUCT.pack(self.type, len(self.value)) + self.value


class ImageHeaderFields(NamedTuple):
    magic: int
    load_addr: int
    hdr_size: int
    protect_tlv_size: int
    img_size: int
    flags: int
    ver_major: int
    ver_minor: int
    ver_revision: int
    ver_build_num: int

    def __bytes__(self) -> bytes:
        return IMAGE_HEADER_STRUCT.pack(*self)


KEYHASH_TLV: Final = TLV(type=IMAGE_TLV.KEYHASH, value=bytes(64))
ED25519_TLV: Final = TLV(type=IMAGE_TLV.ED25519, value=bytes(64))
SEC_CNT_TLV: Final = TLV(type=IMAGE_TLV.SEC_CNT, value=bytes(4))


def hash_tlv(algorithm: IMAGE_TLV) -> TLV:
    """A hash TLV holding digest-sized filler in place of a real MCUboot digest."""
    return TLV(type=algorithm, value=bytes(hashlib.new(algorithm.name).digest_size))


def ed25519_signed(algorithm: IMAGE_TLV) -> Sequence[TLV]:
    """The trailer NCS sysbuild writes for an ED25519 signed image."""
    return (KEYHASH_TLV, hash_tlv(algorithm), ED25519_TLV)


def tlv_region(magic: int, tlvs: Sequence[TLV]) -> bytes:
    entries = b"".join(map(bytes, tlvs))
    return IMAGE_TLV_INFO_STRUCT.pack(magic, IMAGE_TLV_INFO_STRUCT.size + len(entries)) + entries


def mcuboot_image(tlvs: Sequence[TLV], protected_tlvs: Sequence[TLV] = ()) -> bytes:
    """Assemble the smallest MCUboot image that carries `tlvs` in its trailer."""
    protected_region = (
        tlv_region(IMAGE_TLV_PROT_INFO_MAGIC, protected_tlvs) if protected_tlvs else b""
    )
    return (
        bytes(
            ImageHeaderFields(
                magic=IMAGE_MAGIC,
                load_addr=0,
                hdr_size=IMAGE_HEADER_STRUCT.size,
                protect_tlv_size=len(protected_region),
                img_size=len(IMAGE_BODY),
                flags=0,
                ver_major=1,
                ver_minor=2,
                ver_revision=3,
                ver_build_num=4,
            )
        )
        + IMAGE_BODY
        + protected_region
        + tlv_region(IMAGE_TLV_INFO_MAGIC, tlvs)
    )


def write_image(directory: Path, image: bytes) -> Path:
    path = directory / "zephyr.signed.bin"
    path.write_bytes(image)
    return path


def load_image_info(directory: Path, image: bytes) -> ImageInfo:
    """Parse `image` the way `smpmgr upgrade` parses the file it is given."""
    return ImageInfo.load_file(str(write_image(directory, image)))


@pytest.mark.parametrize("algorithm", IMAGE_HASH_TLVS)
def test_get_image_hash_tlv(algorithm: IMAGE_TLV, tmp_path: Path) -> None:
    """Whichever hash algorithm signed the image is the hash that is found."""

    tlv = get_image_hash_tlv(load_image_info(tmp_path, mcuboot_image(ed25519_signed(algorithm))))

    assert tlv is not None
    assert tlv.header.type == algorithm
    assert tlv.value == hash_tlv(algorithm).value


def test_get_image_hash_tlv_of_image_without_a_hash(tmp_path: Path) -> None:
    """An image carrying no hash TLV at all has no hash to mark."""

    assert get_image_hash_tlv(load_image_info(tmp_path, mcuboot_image((ED25519_TLV,)))) is None


def test_get_image_hash_tlv_takes_the_first_of_IMAGE_HASH_TLVS(tmp_path: Path) -> None:
    """The preference order of `IMAGE_HASH_TLVS` wins, not the order within the trailer."""

    tlv = get_image_hash_tlv(
        load_image_info(
            tmp_path, mcuboot_image((hash_tlv(IMAGE_TLV.SHA512), hash_tlv(IMAGE_TLV.SHA256)))
        )
    )

    assert tlv is not None
    assert tlv.header.type == IMAGE_HASH_TLVS[0]


def test_get_image_hash_tlv_of_image_with_a_protected_tlv_region(tmp_path: Path) -> None:
    """A protected TLV region precedes the trailer that carries the hash."""

    tlv = get_image_hash_tlv(
        load_image_info(
            tmp_path,
            mcuboot_image(ed25519_signed(IMAGE_TLV.SHA512), protected_tlvs=(SEC_CNT_TLV,)),
        )
    )

    assert tlv is not None
    assert tlv.header.type == IMAGE_TLV.SHA512


@pytest.mark.parametrize("algorithm", IMAGE_HASH_TLVS)
def test_upgrade_inspection_accepts_any_hash(algorithm: IMAGE_TLV, tmp_path: Path) -> None:
    """`upgrade` gets past image inspection and on to the transport, whatever the hash."""

    result = CliRunner().invoke(
        app, ["upgrade", str(write_image(tmp_path, mcuboot_image(ed25519_signed(algorithm))))]
    )

    assert result.exit_code == 1
    assert "Could not find" not in result.output
    assert "A transport option is required" in result.output


def test_upgrade_inspection_rejects_an_image_without_a_hash(tmp_path: Path) -> None:
    """`upgrade` names every hash TLV it searched for, so the user knows what was missing."""

    result = CliRunner().invoke(
        app, ["upgrade", str(write_image(tmp_path, mcuboot_image((ED25519_TLV,))))]
    )

    assert result.exit_code == 1
    assert f"Could not find an image hash TLV ({IMAGE_HASH_TLV_NAMES})" in result.output
    assert "SHA256/SHA384/SHA512" in result.output
