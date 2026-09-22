"""
Builds a trace tree from a flat list of spans and computes the
critical path -- the chain of spans that actually determines total
trace latency. At each node, the critical path descends into whichever
child span finishes LATEST (start_time + duration), since siblings
that finish earlier aren't what's gating the parent's completion --
this is the standard approach real trace-analysis tools (Jaeger's
critical-path analyzer) use.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.models import Span


@dataclass(frozen=True)
class TraceTree:
    spans_by_id: Dict[str, Span]
    children_of: Dict[str, List[str]]
    root_id: Optional[str]


def build_tree(spans: List[Span]) -> TraceTree:
    spans_by_id = {s.span_id: s for s in spans}
    children_of: Dict[str, List[str]] = {}
    root_id = None

    for s in spans:
        if s.parent_span_id and s.parent_span_id in spans_by_id:
            children_of.setdefault(s.parent_span_id, []).append(s.span_id)
        else:
            root_id = s.span_id

    return TraceTree(spans_by_id=spans_by_id, children_of=children_of, root_id=root_id)


def _end_time(span: Span) -> float:
    return span.start_time_ms + span.duration_ms


def compute_critical_path(tree: TraceTree) -> List[Span]:
    if tree.root_id is None:
        return []

    path = []
    current_id = tree.root_id
    while current_id is not None:
        current = tree.spans_by_id[current_id]
        path.append(current)
        children = tree.children_of.get(current_id, [])
        if not children:
            break
        current_id = max(children, key=lambda cid: _end_time(tree.spans_by_id[cid]))

    return path


def critical_path_duration_ms(path: List[Span]) -> float:
    if not path:
        return 0.0
    return _end_time(path[-1]) - path[0].start_time_ms
