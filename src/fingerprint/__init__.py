"""Sistem sidik jari forensik (forensic fingerprinting) untuk pelacakan kebocoran materi digital.

Berbeda dengan watermark biasa yang memberi tanda identik ke semua salinan,
setiap penerima mendapat sidik jari unik sehingga salinan yang bocor dapat
ditelusuri ke siapa penerimanya.
"""

from .core import DEFAULT_DELTA, ExtractionResult, embed_bits, extract_fingerprint
from .keys import generate_key, load_or_create_key, load_key, save_key
from .payload import PAYLOAD_BITS, build_payload, parse_payload

__all__ = [
    "DEFAULT_DELTA",
    "ExtractionResult",
    "PAYLOAD_BITS",
    "build_payload",
    "embed_bits",
    "extract_fingerprint",
    "generate_key",
    "load_key",
    "load_or_create_key",
    "parse_payload",
    "save_key",
]
