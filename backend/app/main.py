from typing import List, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import Span
from app.trace_builder import build_tree, compute_critical_path, critical_path_duration_ms
from app.anomaly_detector import detect_latency_anomalies, detect_error_cascades

app = FastAPI(title="TraceLens", description="Distributed tracing & observability platform.", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_spans_by_trace: Dict[str, List[Span]] = {}


@app.post("/ingest")
def ingest(spans: List[Span]):
    for s in spans:
        _spans_by_trace.setdefault(s.trace_id, []).append(s)
    return {"ingested": len(spans), "traces_known": len(_spans_by_trace)}


@app.get("/traces")
def list_traces():
    return list(_spans_by_trace.keys())


@app.get("/analyze/{trace_id}")
def analyze(trace_id: str):
    spans = _spans_by_trace.get(trace_id)
    if not spans:
        raise HTTPException(status_code=404, detail="unknown trace_id")

    tree = build_tree(spans)
    critical_path = compute_critical_path(tree)
    total_duration = critical_path_duration_ms(critical_path)
    latency_anomalies = detect_latency_anomalies(spans)
    error_cascades = detect_error_cascades(tree)

    return {
        "trace_id": trace_id,
        "span_count": len(spans),
        "total_duration_ms": round(total_duration, 2),
        "critical_path": [
            {"span_id": s.span_id, "service_name": s.service_name, "operation_name": s.operation_name,
             "duration_ms": s.duration_ms}
            for s in critical_path
        ],
        "latency_anomalies": [a.__dict__ for a in latency_anomalies],
        "error_cascades": [c.__dict__ for c in error_cascades],
    }


@app.post("/reset")
def reset():
    _spans_by_trace.clear()
    return {"status": "cleared"}


@app.get("/health")
def health():
    return {"status": "ok"}
