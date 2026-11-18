"""Pengemasan payload sidik jari: ID penerima + tag HMAC + koreksi galat Reed-Solomon.

Susunan koda-kata sebelum dikonversi ke bit (total 8 byte = 64 bit):

    [ id_lo id_hi | tag_0 tag_1 | parity_0 .. parity_3 ]

- 2 byte pertama  : nomor penerima (0..65535)
- 2 byte kedua    : HMAC-SHA256(kunci, id) yang dipotong, pembukti keaslian
- 4 byte terakhir : paritas Reed-Solomon RS(8,4) atas GF(2^8), mengoreksi
                    sampai 2 byte galat per ulangan payload

Tag HMAC membuat pemalsuan terdeteksi: mengubah ID tanpa kunci akan
menghasilkan tag yang tidak cocok dan payload ditolak, bukan salah menuduh
penerima lain.
"""

from __future__ import annotations

import hashlib
import hmac

import reedsolo

ID_BYTES = 2
TAG_BYTES = 2
PARITY_BYTES = 4
CODEWORD_BYTES = ID_BYTES + TAG_BYTES + PARITY_BYTES
PAYLOAD_BITS = CODEWORD_BYTES * 8

_MAX_ID = 256 ** ID_BYTES - 1
_codec = reedsolo.RSCodec(PARITY_BYTES)


class PayloadError(Exception):
    """Payload rusak parah atau gagal diverifikasi."""


def authenticate(recipient_id: int, secret: bytes) -> bytes:
    """Tag otentikasi pendek untuk sebuah ID penerima."""
    if not 0 <= recipient_id <= _MAX_ID:
        raise ValueError(f"recipient_id harus 0..{_MAX_ID}")
    body = recipient_id.to_bytes(ID_BYTES, "big")
    return hmac.new(secret, body, hashlib.sha256).digest()[:TAG_BYTES]


def build_payload(recipient_id: int, secret: bytes) -> bytes:
    """Kode-kata siap sisipan: ID + tag HMAC + paritas Reed-Solomon."""
    body = recipient_id.to_bytes(ID_BYTES, "big") + authenticate(recipient_id, secret)
    return bytes(_codec.encode(body))


def parse_payload(codeword: bytes, secret: bytes) -> int:
    """Uraikan dan verifikasi kode-kata. Kembalikan ID penerima, atau raise PayloadError."""
    try:
        message, _, _ = _codec.decode(bytes(codeword))
    except reedsolo.ReedSolomonError as exc:
        raise PayloadError("koreksi Reed-Solomon gagal") from exc
    decoded = bytes(message)
    body = decoded[: ID_BYTES + TAG_BYTES]
    claimed_id = int.from_bytes(body[:ID_BYTES], "big")
    if not hmac.compare_digest(body[ID_BYTES:], authenticate(claimed_id, secret)):
        raise PayloadError("tag HMAC tidak cocok: sidik jari dipalsukan")
    return claimed_id


def to_bits(data: bytes) -> list[int]:
    """Byte string menjadi daftar bit, MSB lebih dulu."""
    return [(byte >> shift) & 1 for byte in data for shift in range(7, -1, -1)]


def from_bits(bits: list[int]) -> bytes:
    """Daftar bit (MSB lebih dulu) dikembalikan menjadi byte string."""
    if len(bits) % 8:
        raise ValueError("jumlah bit harus kelipatan 8")
    value = 0
    out = bytearray()
    for index, bit in enumerate(bits):
        value = (value << 1) | int(bit)
        if index % 8 == 7:
            out.append(value)
            value = 0
    return bytes(out)
