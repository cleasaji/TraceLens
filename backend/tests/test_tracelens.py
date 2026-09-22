import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import Span
from app.trace_builder import build_tree, compute_critical_path, critical_path_duration_ms
from app.anomaly_detector import percentile, detect_latency_anomalies, detect_error_cascades


def make_span(span_id, parent_id, service, op, start, duration, status="ok"):
    return Span(trace_id="t1", span_id=span_id, parent_span_id=parent_id, service_name=service,
               operation_name=op, start_time_ms=start, duration_ms=duration, status=status)


def diamond_trace():
    return [
        make_span("root", None, "gateway", "handle_request", 0, 250),
        make_span("fast_child", "root", "auth", "verify_token", 0, 50),
        make_span("slow_child", "root", "db", "query", 0, 200),
    ]


def test_build_tree_identifies_root_and_children():
    tree = build_tree(diamond_trace())
    assert tree.root_id == "root"
    assert set(tree.children_of["root"]) == {"fast_child", "slow_child"}


def test_critical_path_follows_the_slower_child():
    tree = build_tree(diamond_trace())
    path = compute_critical_path(tree)
    span_ids = [s.span_id for s in path]
    assert span_ids == ["root", "slow_child"]


def test_critical_path_duration_matches_root_to_last_span_end():
    tree = build_tree(diamond_trace())
    path = compute_critical_path(tree)
    duration = critical_path_duration_ms(path)
    assert duration == 200.0


def test_percentile_matches_known_values():
    values = [10, 20, 30, 40, 50]
    assert percentile(values, 50) == 30
    assert percentile(values, 0) == 10
    assert percentile(values, 100) == 50


def test_latency_anomaly_flags_true_outlier():
    spans = [make_span(f"s{i}", None, "api", "get_user", 0, 100) for i in range(10)]
    spans.append(make_span("outlier", None, "api", "get_user", 0, 5000))
    anomalies = detect_latency_anomalies(spans)
    assert any(a.span_id == "outlier" for a in anomalies)


def test_latency_anomaly_not_flagged_for_uniform_durations():
    spans = [make_span(f"s{i}", None, "api", "get_user", 0, 100) for i in range(10)]
    assert detect_latency_anomalies(spans) == []


def test_error_cascade_detects_contiguous_error_chain():
    spans = [
        make_span("root", None, "gateway", "handle", 0, 300, status="error"),
        make_span("mid", "root", "service-a", "call", 0, 200, status="error"),
        make_span("leaf", "mid", "service-b", "query", 0, 100, status="error"),
    ]
    tree = build_tree(spans)
    cascades = detect_error_cascades(tree, min_chain_length=2)
    assert len(cascades) == 1
    assert cascades[0].span_ids == ["root", "mid", "leaf"]


def test_error_cascade_none_for_healthy_trace():
    tree = build_tree(diamond_trace())
    assert detect_error_cascades(tree) == []
