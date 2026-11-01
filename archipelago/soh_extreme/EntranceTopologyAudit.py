"""Pure consistency checks between the final AP region graph and entrance slot map.

This catches disconnected/retargeted edges in the generator. It does not
establish that OoT's native collision, actor locks, or room geometry agree with
Archipelago's model; those require playable client integration tests.
"""
from __future__ import annotations


def validate_edges(expected: dict[int, tuple[str, str]],
                   actual: dict[int, tuple[str, str | None]]) -> None:
    """Require every routed physical source to have exactly its intended AP edge."""
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    if missing or extra:
        raise ValueError(f"physical sources missing={missing[:12]}, extra={extra[:12]}")
    for source_id in sorted(expected):
        if actual[source_id] != expected[source_id]:
            raise ValueError(
                f"endpoint {source_id}: installed {actual[source_id]!r}; "
                f"expected {expected[source_id]!r}"
            )
