"""Dynamic imports for optional Nexa extension packages (``nexa_ext.*``)."""

from app.services.extensions.loader import extension_loaded, get_extension

__all__ = ["extension_loaded", "get_extension"]
