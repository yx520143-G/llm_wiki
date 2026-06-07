from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ObjectType = Literal["figure", "table", "equation"]
ObjectOccurrence = Literal["actual", "reference"]
WarningSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def as_list(self) -> list[float]:
        return [self.x0, self.y0, self.x1, self.y1]


@dataclass(frozen=True)
class ParagraphAnchor:
    id: str
    page: int
    bbox: BBox
    hash: str


@dataclass(frozen=True)
class ObjectRef:
    object_id: str
    path: str
    occurrence: ObjectOccurrence


@dataclass
class SectionNode:
    spec_version: str
    section_number: str
    title: str
    level: int
    page_start: int
    page_end: int
    toc_path: list[str]
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)
    object_refs: list[ObjectRef] = field(default_factory=list)
    paragraph_anchors: list[ParagraphAnchor] = field(default_factory=list)
    body_markdown: str = ""
    slug: str = ""
    content_hash: str = ""

    @property
    def section_id(self) -> str:
        return f"{self.spec_version}:section:{self.section_number}"


@dataclass
class SourceObject:
    spec_version: str
    object_type: ObjectType
    object_number: str
    title: str
    listed_page: int
    page: int | None
    bbox: BBox | None
    section_id: str | None
    listed_in: str
    slug: str = ""
    asset_paths: dict[str, str] = field(default_factory=dict)
    caption_hash: str = ""
    content_hash: str = ""
    status: str = "resolved"

    @property
    def object_id(self) -> str:
        return f"{self.spec_version}:{self.object_type}:{self.object_number}"


@dataclass(frozen=True)
class TextSpan:
    text: str
    page: int
    bbox: BBox
    block: int
    line: int
    span: int


@dataclass(frozen=True)
class TableCell:
    text: str
    rowspan: int
    colspan: int
    page: int
    bbox: BBox
    hash: str


@dataclass(frozen=True)
class ParseWarning:
    severity: WarningSeverity
    code: str
    message: str
    page: int | None = None
    section_id: str | None = None
    object_id: str | None = None
