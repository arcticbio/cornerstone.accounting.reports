"""Continuous intake (SPEC §18): decide, per property-month, what the folders hold and whether
to build. Everything in this package except `reconcile` is pure — no I/O, no clock — so every
rule in §18 is testable without Drive, a model or a timer."""
