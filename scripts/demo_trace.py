"""Demo pelacakan bocor: tiga penerima, satu menyebarkan, sistem menyebut nama.

Alur yang didemokan untuk video Bagian 8:
1. Materi yang sama dibagikan ke penerima 101, 102, 103; tiap berkas membawa
   sidik jari unik yang tidak terlihat mata.
2. Penerima 102 menyebarkan; berkas yang beredar dikompresi JPEG dan dipotong.
3. Penelusur menjalankan ekstraksi buta dan sistem menunjuk 102 sebagai sumber.

Jalankan:  python scripts/demo_trace.py [jalan/ke/citra.png]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fingerprint import attacks, core, keys, metrics, payload  # noqa: E402
from fingerprint.files import ensure_dir, read_image, write_image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "demo")
PENERIMA = [101, 102, 103]
PEMBOCOR = 102


def main() -> None:
    ensure_dir(OUT)
    secret = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))
    source = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "assets", "samples", "document.png")
    base = read_image(source)
    print(f"citra asal {source} {base.shape}  sidik jari {core.CELL}x{core.CELL} sel, "
          f"payload {payload.PAYLOAD_BITS} bit\n")

    for rid in PENERIMA:
        bits = payload.to_bits(payload.build_payload(rid, secret))
        marked = core.embed_bits(base, bits, secret)
        write_image(os.path.join(OUT, f"berkas_{rid}.png"), marked)
        check = core.extract_fingerprint(marked, secret)
        print(f"bagikan ke {rid}: PSNR {metrics.psnr(base, marked):5.2f} dB, "
              f"SSIM {metrics.ssim(base, marked):.4f}, terbaca {check.recipient_id} "
              f"({check.valid_cells}/{check.total_cells} sel)")

    leaked_bits = payload.to_bits(payload.build_payload(PEMBOCOR, secret))
    leaked = core.embed_bits(base, leaked_bits, secret)

    compressed = attacks.jpeg(leaked, 80)
    cropped, offset = attacks.crop_border(compressed, 0.05)
    scenes = [
        ("bocor_jpeg70", attacks.jpeg(leaked, 70)),
        ("bocor_kompres_crop", attacks.reanchor(cropped, leaked.shape, offset)),
    ]
    print()
    for label, copy in scenes:
        write_image(os.path.join(OUT, f"{label}.png"), copy)
        found = core.extract_fingerprint(copy, secret)
        verdict = "TIDAK DAPAT DITENTUKAN" if found.recipient_id is None else str(found.recipient_id)
        print(f"skenario {label}: identitas = {verdict}  "
              f"({found.valid_cells}/{found.total_cells} sel, {found.reason})")

    innocent = core.embed_bits(base, payload.to_bits(payload.build_payload(101, secret)), secret)
    foreign = core.extract_fingerprint(attacks.jpeg(innocent, 85), secret)
    print(f"\napel: berkas penerima 101 dibaca -> {foreign.recipient_id}, "
          f"tag HMAC {'valid' if foreign.ok else 'invalid'}")
    print(f"berkas demo ditulis ke {OUT}")


if __name__ == "__main__":
    main()
