"""
Two real detectors over span data: a P99 latency outlier check computed
from an actual sorted-list percentile (not a mean+stdev approximation,
since latency distributions are heavily right-skewed), and error-cascade
detection that walks parent-child chains for contiguous error runs.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.models import Span
from app.trace_builder import TraceTree


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = (p / 100) * (len(s) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return s[int(rank)]
    weight = rank - lower
    return s[lower] * (1 - weight) + s[upper] * weight


@dataclass(frozen=True)
class LatencyAnomaly:
    span_id: str
    service_name: str
    operation_name: str
    duration_ms: float
    baseline_p99_ms: float


def detect_latency_anomalies(spans: List[Span]) -> List[LatencyAnomaly]:
    by_op: Dict[Tuple[str, str], List[Span]] = defaultdict(list)
    for s in spans:
        by_op[(s.service_name, s.operation_name)].append(s)

    anomalies = []
    for (service, operation), op_spans in by_op.items():
        durations = [s.duration_ms for s in op_spans]
        if len(durations) < 4:
            continue
        p99 = percentile(durations, 99)
        for s in op_spans:
            if s.duration_ms > p99 and s.duration_ms > durations[0] * 1.01:
                anomalies.append(LatencyAnomaly(
                    span_id=s.span_id, service_name=service, operation_name=operation,
                    duration_ms=s.duration_ms, baseline_p99_ms=round(p99, 2),
                ))

    return anomalies


@dataclass(frozen=True)
class ErrorCascade:
    span_ids: List[str]
    services: List[str]


def detect_error_cascades(tree: TraceTree, min_chain_length: int = 2) -> List[ErrorCascade]:
    cascades = []

    def walk(span_id: str, chain: List[str]):
        span = tree.spans_by_id[span_id]
        if span.status == "error":
            chain = chain + [span_id]
        else:
            if len(chain) >= min_chain_length:
                cascades.append(ErrorCascade(
                    span_ids=chain, services=[tree.spans_by_id[i].service_name for i in chain],
                ))
            chain = []

        children = tree.children_of.get(span_id, [])
        if not children and len(chain) >= min_chain_length:
            cascades.append(ErrorCascade(
                span_ids=chain, services=[tree.spans_by_id[i].service_name for i in chain],
            ))
        for child_id in children:
            walk(child_id, chain)

    if tree.root_id:
        walk(tree.root_id, [])

    return cascades
