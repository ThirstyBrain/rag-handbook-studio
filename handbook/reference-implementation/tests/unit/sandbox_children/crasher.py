"""Test child: dies without an answer (killed, out of memory, segfault)."""

import os

os._exit(3)
