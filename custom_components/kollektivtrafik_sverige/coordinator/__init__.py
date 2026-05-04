# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Coordinator package for the Kollektivtrafik Sverige integration.

This package contains the modular components used by the main
KollektivtrafikSverigeCoordinator, including:

- parser:      Normalization of Trafiklab realtime API responses
- filters:     Line/direction filtering logic
- queue:       10-buffer queue and 5-exposed departure model
- polling:     Dynamic polling interval calculation

The main coordinator imports these modules to keep the codebase clean,
maintainable, and easy to extend.
"""
