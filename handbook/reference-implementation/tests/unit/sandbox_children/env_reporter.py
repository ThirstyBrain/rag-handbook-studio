"""Test child: answers with the names and values of its environment and its working directory."""

import json
import os
import sys

sys.stdin.buffer.read()
sys.stdout.write(
    json.dumps(
        {
            "ok": True,
            "extractor": "env-reporter",
            "blocks": [
                ["paragraph", json.dumps({"env": dict(os.environ), "cwd": os.getcwd()}), 0, None]
            ],
        }
    )
)
