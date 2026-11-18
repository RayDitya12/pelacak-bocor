"""Uji cepat ketahanan untuk memilih subband, delta, dan batas langkah.

Pakai:
    python scripts/probe_robustness.py                  # sapu semua kombinasi
    python scripts/probe_robustness.py LL 0.25          # satu kombinasi saja
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from fingerprint import attacks, core, keys, metrics, payload  # noqa: E402
from fingerprint.files import read_image  # noqa: E402

SECRET = bytes.fromhex('11'*32)
BITS = payload.to_bits(payload.build_payload(42, SECRET))
IMAGE = "assets/samples/document.png"

PROBES = [
    ("bersih", lambda i: i),
    ("jpeg90", lambda i: attacks.jpeg(i, 90)),
    ("jpeg70", lambda i: attacks.jpeg(i, 70)),
    ("jpeg50", lambda i: attacks.jpeg(i, 50)),
    ("noise5", lambda i: attacks.gaussian_noise(i, 5)),
    ("noise15", lambda i: attacks.gaussian_noise(i, 15)),
    ("blur7", lambda i: attacks.blur(i, 7)),
    ("rsz0.5", lambda i: attacks.resize(i, 0.5)),
    ("bri+40", lambda i: attacks.brightness(i, 40)),
    ("con1.3", lambda i: attacks.contrast(i, 1.3)),
]


def probe(subband: str, delta: float) -> None:
    image = read_image(IMAGE)
    marked = core.embed_bits(image, BITS, SECRET, delta, subband)
    head = f"--- {subband} delta={delta} psnr={metrics.psnr(image, marked):.2f} " \
           f"ssim={metrics.ssim(image, marked):.4f} ---"
    print(head)
    for name, fn in PROBES:
        res = core.extract_fingerprint(fn(marked), SECRET, delta, subband)
        print(f"  {name:8s} id={str(res.recipient_id):>5s} sel={res.valid_cells:2d}/"
              f"{res.total_cells:2d} BER={res.mean_ber(BITS):.3f}")


def main() -> None:
    if len(sys.argv) >= 3:
        probe(sys.argv[1], float(sys.argv[2]))
        return
    for subband in ("LL", "LH", "HL"):
        for delta in (0.15, 0.30, 0.60):
            probe(subband, delta)


if __name__ == "__main__":
    main()
