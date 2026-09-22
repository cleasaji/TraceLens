"""
Span schema modeled on OpenTelemetry's core fields (trace_id, span_id,
parent_span_id, service/operation name, start time, duration, status) --
the format a real tracing SDK (Jaeger, Zipkin, OTel) actually emits.
"""

from typing import Dict, Optional
from pydantic import BaseModel


class Span(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    service_name: str
    operation_name: str
    start_time_ms: float
    duration_ms: float
    status: str = "ok"
    tags: Dict[str, str] = {}
