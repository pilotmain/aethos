# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Dynamic imports for optional Nexa extension packages (``nexa_ext.*``)."""

from app.services.extensions.loader import extension_loaded, get_extension

__all__ = ["extension_loaded", "get_extension"]
