"""Test child: writes unbounded output (a runaway or compromised parser)."""

import sys

chunk = b"x" * 65536
while True:
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()
