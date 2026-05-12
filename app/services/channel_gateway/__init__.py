# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Channel Gateway package.

Keep this module lightweight. Do not import router, governance, or modules
that depend on audit_service here, because audit_service imports
``channel_gateway.audit_integration`` and loading this package would
otherwise run before ``audit_service`` is fully initialized (circular import
with e.g. ``telegram_bot`` → ``audit_service`` → this package).
"""
