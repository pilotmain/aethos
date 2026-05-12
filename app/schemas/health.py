# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    app: str
    env: str
