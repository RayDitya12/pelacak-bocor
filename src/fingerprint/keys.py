"""Pembuatan dan penyimpanan kunci master sistem fingerprint.

Kunci master dipakai untuk tiga hal sekaligus:
1. Menurunkan tag autentikasi per penerima (HMAC-SHA256).
2. Menurunkan seed penempatan blok airamen, sehingga posisi sisipan tidak
   dapat ditebak pihak yang tidak memegang kunci.
3. Memverifikasi keaslian sidik jari saat ekstraksi.

Kunci tidak pernah ikut tersimpan di dalam berkas yang disebarluaskan.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

KEY_SIZE = 32
DEFAULT_KEY_FILE = os.path.join("keys", "master.key")


def generate_key() -> bytes:
    """Bangkitkan kunci master acak sepanjang KEY_SIZE byte."""
    return secrets.token_bytes(KEY_SIZE)


def save_key(secret: bytes, path: str = DEFAULT_KEY_FILE) -> str:
    """Simpan kunci master sebagai heksadesimal. Direktori dibuat bila belum ada."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="ascii") as fh:
        fh.write(secret.hex() + "\n")
    return path


def load_key(path: str = DEFAULT_KEY_FILE) -> bytes:
    """Baca kunci master dari berkas heksadesimal."""
    with open(path, "r", encoding="ascii") as fh:
        return bytes.fromhex(fh.read().strip())


def load_or_create_key(path: str = DEFAULT_KEY_FILE) -> bytes:
    """Kembalikan kunci yang sudah ada, atau buat baru bila berkas belum ada."""
    if os.path.exists(path):
        return load_key(path)
    secret = generate_key()
    save_key(secret, path)
    return secret


def derive_seed(secret: bytes, label: str) -> int:
    """Turunkan seed PRNG penentu tata letak blok dari kunci master dan label."""
    digest = hmac.new(secret, label.encode("ascii"), hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big")
