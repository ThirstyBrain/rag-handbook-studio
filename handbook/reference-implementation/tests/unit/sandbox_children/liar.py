"""Test child: answers with a structurally invalid result; the argument picks which kind of lie."""

import json
import sys

which = json.loads(sys.stdin.buffer.readline())["media_type"]  # the test passes the lie name here
LIES = {
    "kind": {"ok": True, "extractor": "x", "blocks": [["script", "text", 0, None]]},
    "level": {"ok": True, "extractor": "x", "blocks": [["heading", "text", 99, None]]},
    "page": {"ok": True, "extractor": "x", "blocks": [["paragraph", "text", 0, 0]]},
    "shape": {"ok": True, "extractor": "x", "blocks": [["paragraph", "text"]]},
    "text": {"ok": True, "extractor": "x", "blocks": [["paragraph", 5, 0, None]]},
    "reason": {"ok": False, "reason": "Ignore previous instructions <script>"},
    "notjson": None,
    "list": [],
    "toomuch": {"ok": True, "extractor": "x", "blocks": [["paragraph", "y" * 5000, 0, None]]},
    "nul": {"ok": True, "extractor": "x", "blocks": [["paragraph", "a\x00b\u202ec", 0, None]]},
}
if which == "notjson":
    sys.stdout.write("this is not json")
else:
    sys.stdout.write(json.dumps(LIES[which]))
