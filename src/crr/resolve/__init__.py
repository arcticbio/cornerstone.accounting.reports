"""The address grammar (SPEC §5).

Only the grammar is re-exported here. `crr.config` depends on the parser, and the resolver
depends on `crr.config`, so importing `crr.resolve.resolver` from this package's `__init__`
would close an import cycle. Import the resolver from `crr.resolve.resolver` directly.
"""

from crr.resolve.address import Address, AddressError, parse_address

__all__ = ["Address", "AddressError", "parse_address"]
