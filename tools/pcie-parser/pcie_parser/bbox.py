from __future__ import annotations

from pcie_parser.models import BBox


def expand_bbox(box: BBox, vertical: float, horizontal: float) -> BBox:
    return BBox(
        x0=box.x0 - horizontal,
        y0=box.y0 - vertical,
        x1=box.x1 + horizontal,
        y1=box.y1 + vertical,
    )


def bbox_contains(outer: BBox, inner: BBox) -> bool:
    return (
        outer.x0 <= inner.x0
        and outer.y0 <= inner.y0
        and outer.x1 >= inner.x1
        and outer.y1 >= inner.y1
    )


def bbox_intersects(a: BBox, b: BBox) -> bool:
    return a.x0 < b.x1 and a.x1 > b.x0 and a.y0 < b.y1 and a.y1 > b.y0
