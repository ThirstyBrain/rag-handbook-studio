"""Test child: applies the real rlimits, then tries to allocate far more memory than allowed (POSIX)."""

import json
import sys

from rag_service.features.extraction.child import _apply_posix_limits
from rag_service.features.extraction.model import ExtractionLimits

request = json.loads(sys.stdin.buffer.readline())
_apply_posix_limits(ExtractionLimits.from_json(json.dumps(request["limits"])))
try:
    blob = bytearray(2 * 1024 * 1024 * 1024)
except MemoryError:
    sys.stdout.write(json.dumps({"ok": False, "reason": "resource_limit"}))
else:
    sys.stdout.write(
        json.dumps(
            {"ok": True, "extractor": "hog", "blocks": [["paragraph", str(len(blob)), 0, None]]}
        )
    )
