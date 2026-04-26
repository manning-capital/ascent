"""Topological sort for feed deployment order.

Feeds declare parents via ``depends_on``. The deployer registers parents
before children so that ``FeedDependency`` rows can reference existing
``Feed`` rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ascent.feeds.base import Feed


def _topological_sort_feeds(feed_classes: list[type[Feed]]) -> list[type[Feed]]:
    ref_to_cls = {cls.ref(): cls for cls in feed_classes}
    in_degree = {cls.ref(): 0 for cls in feed_classes}
    dependents: dict[str, list[str]] = {cls.ref(): [] for cls in feed_classes}
    for cls in feed_classes:
        if cls.depends_on:
            for parent_cls in cls.depends_on:
                parent_ref = parent_cls.ref()
                if parent_ref in ref_to_cls:
                    in_degree[cls.ref()] += 1
                    dependents[parent_ref].append(cls.ref())
    queue = [ref for ref, deg in in_degree.items() if deg == 0]
    result: list[type[Feed]] = []
    while queue:
        ref = queue.pop(0)
        result.append(ref_to_cls[ref])
        for child_ref in dependents[ref]:
            in_degree[child_ref] -= 1
            if in_degree[child_ref] == 0:
                queue.append(child_ref)
    if len(result) != len(feed_classes):
        raise ValueError("Circular dependency detected among feeds")
    return result
