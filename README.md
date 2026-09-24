# 🔭 TraceLens — Distributed Tracing & Observability Platform

A FastAPI service that ingests OpenTelemetry-shaped spans, builds the
trace tree, computes the **real critical path** (the chain of spans
that actually determines total latency -- not just the slowest single
span), and flags P99 latency outliers and error cascades.

---

## Run it yourself

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Or open `frontend/index.html` -- pre-filled with a 3-span trace where a
DB call gates the parent's completion.

## Critical path, computed correctly

A naive "critical path" implementation just returns the slowest span.
The real algorithm (`trace_builder.py`) descends from the root through
whichever child finishes **latest** (`start_time + duration`), since a
child that finishes early was never on the path gating completion --
this is what real trace-analysis tools (Jaeger) actually do, and it's
directly tested:

```python
def test_critical_path_follows_the_slower_child():
    # root has a 50ms auth child and a 200ms db child running in parallel
    path = compute_critical_path(tree)
    assert [s.span_id for s in path] == ["root", "slow_child"]
```

## A real percentile, not mean+stddev

`anomaly_detector.py`'s `percentile()` is a real linear-interpolation
percentile over sorted values -- latency distributions are heavily
right-skewed, so a mean+stddev "anomaly" check would either miss real
outliers or flag normal variance constantly. P99 is computed per
`(service, operation)` pair so a slow database call isn't compared
against a fast auth check.

## Error cascade detection

`detect_error_cascades()` walks parent-child chains looking for
**contiguous** error runs -- root fails, its child fails, that child's
child fails -- which is the signature of a root-cause failure
propagating up the call chain, distinct from an isolated single-span
error that self-recovered.

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

8 tests: tree construction correctly identifying root and children,
critical path correctly following the slower of two parallel children,
critical path duration matching the actual end time, percentile
matching known hand-computed values, latency anomaly correctly flagging
a real outlier and correctly staying silent on uniform durations, and
error cascade detection on a genuine 3-span failure chain vs. a healthy trace.

## Project layout

```
backend/
  app/
    models.py, trace_builder.py, anomaly_detector.py, main.py
  tests/
    test_tracelens.py
frontend/
  index.html
```

## Honest scope

In-memory trace storage (no persistent time-series backend), and a
straightforward percentile/cascade approach rather than the full
statistical anomaly detection a production APM tool (Datadog, Honeycomb)
would use. The critical-path algorithm and percentile computation are
both real and independently tested -- the reusable part that carries
over once real OTel collector ingestion and a real storage backend are added..
