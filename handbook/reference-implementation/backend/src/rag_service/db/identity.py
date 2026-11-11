"""The verified identity that scopes every database transaction.

It is produced by authentication (component 13) from a validated token, never from request payloads or
model output. Values are validated here because they are written into database settings.
"""

from __future__ import annotations

import json
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SAFE = re.compile(r"^[A-Za-z0-9._:@/-]{1,128}$")
MAX_GROUPS = 64


class Identity(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    user_id: str
    groups: tuple[str, ...] = Field(default=(), max_length=MAX_GROUPS)

    @field_validator("user_id")
    @classmethod
    def _user_id_safe(cls, value: str) -> str:
        if not _SAFE.fullmatch(value):
            raise ValueError("user_id must match [A-Za-z0-9._:@/-]{1,128}")
        return value

    @field_validator("groups")
    @classmethod
    def _groups_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for group in value:
            if not _SAFE.fullmatch(group):
                raise ValueError("each group must match [A-Za-z0-9._:@/-]{1,128}")
        return tuple(sorted(set(value)))

    def groups_json(self) -> str:
        return json.dumps(list(self.groups))
