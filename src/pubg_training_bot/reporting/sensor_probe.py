"""Stage 1 evidence: what the live Overwolf stream actually provides.

The probe answers questions the project has so far only assumed answers to:
does Training Mode expose XYZ at all, how often, how noisy is it when the
character is motionless, and what identifiers does the game actually report for
map, phase and view.

Nothing here interprets a missing signal charitably. If no position arrived, the
report says so and the stage fails.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .. import __version__
from ..domain.sensors import Vec3


@dataclass
class ProbeSample:
    """One polled observation."""

    at: float
    position: Vec3 | None
    location_age_s: float | None
    map_id: str | None
    phase: str
    view: str
    stance: str
    movement: str
    free_view: bool | None
    bridge_health: str


class IntervalStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = 0
    min_s: float | None = None
    p50_s: float | None = None
    p95_s: float | None = None
    max_s: float | None = None
    mean_s: float | None = None
    #: Bucket label -> count, for the human-readable histogram.
    histogram: dict[str, int] = Field(default_factory=dict)

    @property
    def implied_hz(self) -> float | None:
        if not self.p50_s:
            return None
        return round(1.0 / self.p50_s, 2)


class StationaryNoise(BaseModel):
    """Spread of reported position while the operator held still.

    This sets the floor for every node tolerance in every recorded route: a
    route node cannot be tighter than the sensor's own noise.
    """

    model_config = ConfigDict(extra="forbid")

    samples: int = 0
    window_s: float = 0.0
    max_xy_deviation_units: float | None = None
    p95_xy_deviation_units: float | None = None
    mean_xy_deviation_units: float | None = None
    z_range_units: float | None = None
    centroid: tuple[float, float, float] | None = None
    measured: bool = False
    detail: str = ""


class SensorProbeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    generated_at: str
    bot_version: str
    duration_s: float
    poll_hz: float

    #: True when the data came from the synthetic bridge rather than the game.
    #: A simulated run can never be a LIVE PASS, and every renderer says so.
    simulated: bool = False

    bridge_connected: bool = False
    session_id: str = ""
    frames_received: int = 0
    frames_rejected_duplicate: int = 0
    frames_sequence_gaps: int = 0
    frames_regressions: int = 0
    parse_warnings: list[dict[str, Any]] = Field(default_factory=list)
    feature_registration: dict[str, bool] = Field(default_factory=dict)

    position_updates: int = 0
    location_intervals: IntervalStats = Field(default_factory=IntervalStats)
    stationary_noise: StationaryNoise = Field(default_factory=StationaryNoise)

    observed_maps: list[str] = Field(default_factory=list)
    observed_phases: list[str] = Field(default_factory=list)
    observed_views: list[str] = Field(default_factory=list)

    total_path_length_units: float = 0.0
    bounding_box_units: dict[str, float] = Field(default_factory=dict)
    first_position: tuple[float, float, float] | None = None
    last_position: tuple[float, float, float] | None = None
    max_gap_s: float | None = None

    #: Explicit pass/fail against the Stage 1 acceptance criteria.
    acceptance: dict[str, bool] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.acceptance) and all(self.acceptance.values())


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def _histogram(values: list[float]) -> dict[str, int]:
    """Fixed buckets around the ~1 Hz working assumption, so the shape of the
    distribution is visible rather than just its percentiles."""
    edges = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, math.inf]
    labels = [
        "<0.25s",
        "0.25-0.5s",
        "0.5-0.75s",
        "0.75-1.0s",
        "1.0-1.5s",
        "1.5-2.0s",
        "2.0-3.0s",
        "3.0-5.0s",
        ">5s",
    ]
    counts = dict.fromkeys(labels, 0)
    for value in values:
        for i in range(len(labels)):
            if edges[i] <= value < edges[i + 1]:
                counts[labels[i]] += 1
                break
    return {k: v for k, v in counts.items() if v}


def interval_stats(intervals: list[float]) -> IntervalStats:
    if not intervals:
        return IntervalStats()
    return IntervalStats(
        count=len(intervals),
        min_s=round(min(intervals), 4),
        p50_s=round(_percentile(intervals, 0.50) or 0.0, 4),
        p95_s=round(_percentile(intervals, 0.95) or 0.0, 4),
        max_s=round(max(intervals), 4),
        mean_s=round(statistics.fmean(intervals), 4),
        histogram=_histogram(intervals),
    )


def stationary_noise(samples: list[ProbeSample], window_s: float) -> StationaryNoise:
    """Measure position spread over the first ``window_s`` seconds.

    The operator is asked to hold still for that window. Distinct positions are
    used rather than polls, so a high poll rate against a ~1 Hz sensor cannot
    inflate the sample count and make the noise look better characterised than
    it is.
    """
    if not samples or window_s <= 0:
        return StationaryNoise(detail="no stationary window requested")

    start = samples[0].at
    positions: list[Vec3] = []
    seen: set[tuple[float, float, float]] = set()
    for sample in samples:
        if sample.at - start > window_s:
            break
        if sample.position is None:
            continue
        key = sample.position.as_tuple()
        if key not in seen:
            seen.add(key)
            positions.append(sample.position)

    if len(positions) < 2:
        return StationaryNoise(
            samples=len(positions),
            window_s=window_s,
            measured=False,
            detail=(
                f"only {len(positions)} distinct position(s) in the stationary window; "
                "not enough to characterise noise"
            ),
        )

    cx = statistics.fmean(p.x for p in positions)
    cy = statistics.fmean(p.y for p in positions)
    cz = statistics.fmean(p.z for p in positions)
    deviations = [math.hypot(p.x - cx, p.y - cy) for p in positions]
    z_values = [p.z for p in positions]

    return StationaryNoise(
        samples=len(positions),
        window_s=window_s,
        max_xy_deviation_units=round(max(deviations), 4),
        p95_xy_deviation_units=round(_percentile(deviations, 0.95) or 0.0, 4),
        mean_xy_deviation_units=round(statistics.fmean(deviations), 4),
        z_range_units=round(max(z_values) - min(z_values), 4),
        centroid=(round(cx, 3), round(cy, 3), round(cz, 3)),
        measured=True,
    )


def build_report(
    *,
    samples: list[ProbeSample],
    observations: dict[str, Any],
    status: Any,
    duration_s: float,
    poll_hz: float,
    still_seconds: float,
    simulated: bool = False,
) -> SensorProbeReport:
    intervals = [float(v) for v in observations.get("position_intervals", [])]
    positions = [s.position for s in samples if s.position is not None]

    path_length = 0.0
    for a, b in zip(positions, positions[1:], strict=False):
        path_length += a.distance_2d(b)

    bbox: dict[str, float] = {}
    if positions:
        bbox = {
            "min_x": min(p.x for p in positions),
            "max_x": max(p.x for p in positions),
            "min_y": min(p.y for p in positions),
            "max_y": max(p.y for p in positions),
            "min_z": min(p.z for p in positions),
            "max_z": max(p.z for p in positions),
        }

    noise = stationary_noise(samples, still_seconds)
    stats = interval_stats(intervals)
    observed_maps = list(observations.get("observed_maps", []))
    observed_phases = list(observations.get("observed_phases", []))
    observed_views = list(observations.get("observed_views", []))
    warnings = list(observations.get("warnings", []))

    report = SensorProbeReport(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        bot_version=__version__,
        duration_s=round(duration_s, 2),
        poll_hz=poll_hz,
        simulated=simulated,
        bridge_connected=getattr(status, "messages_received", 0) > 0,
        frames_received=getattr(status, "messages_received", 0),
        frames_rejected_duplicate=getattr(status, "duplicates_dropped", 0),
        frames_sequence_gaps=getattr(status, "sequence_gaps", 0),
        parse_warnings=warnings,
        feature_registration=dict(getattr(status, "feature_registration", {}) or {}),
        position_updates=int(observations.get("position_updates", 0)),
        location_intervals=stats,
        stationary_noise=noise,
        observed_maps=observed_maps,
        observed_phases=observed_phases,
        observed_views=observed_views,
        total_path_length_units=round(path_length, 3),
        bounding_box_units={k: round(v, 3) for k, v in bbox.items()},
        first_position=positions[0].as_tuple() if positions else None,
        last_position=positions[-1].as_tuple() if positions else None,
        max_gap_s=stats.max_s,
    )

    report.acceptance = {
        "bridge connected": report.frames_received > 0,
        "feature registration reported": bool(report.feature_registration),
        "map observed": bool(observed_maps),
        "phase observed": bool(observed_phases),
        "view observed": bool(observed_views),
        "xyz updates arrived": report.position_updates > 0,
        "movement changed position": path_length > 0.0,
        "update cadence measured": stats.count > 0,
        "stationary baseline measured": noise.measured,
    }

    if simulated:
        report.notes.insert(
            0,
            "SIMULATED RUN. Data came from the synthetic bridge, not from PUBG. This "
            "exercises the pipeline only and is NOT evidence about the game; it can "
            "never count as a LIVE PASS for Stage 1.",
        )
    if not report.acceptance["xyz updates arrived"]:
        report.notes.append(
            "NO POSITION DATA. Training Mode did not deliver the 'location' feature. "
            "This is the project's top feasibility risk (R-002); it is recorded as a "
            "failure rather than worked around."
        )
    if warnings:
        report.notes.append(
            f"{len(warnings)} parse warning(s) preserved; raw payloads are in events.jsonl."
        )
    if stats.p50_s and stats.p50_s > 1.5:
        report.notes.append(
            f"Median location interval {stats.p50_s}s is slower than the ~1 Hz working "
            "assumption; freshness thresholds must be revised (D-009)."
        )
    return report


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def _html(report: SensorProbeReport, trace: list[ProbeSample]) -> str:
    points = [(s.position.x, s.position.y) for s in trace if s.position]
    svg = "<p><em>No position samples to plot.</em></p>"
    if len(points) >= 2:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        span_x = max(max_x - min_x, 1e-6)
        span_y = max(max_y - min_y, 1e-6)
        span = max(span_x, span_y)
        coords = " ".join(
            f"{20 + 460 * (x - min_x) / span:.1f},{480 - 460 * (y - min_y) / span:.1f}"
            for x, y in points
        )
        svg = (
            '<svg viewBox="0 0 500 500" width="500" height="500" '
            'style="background:#111;border:1px solid #333">'
            f'<polyline points="{coords}" fill="none" stroke="#4ea1ff" stroke-width="2"/>'
            f'<circle cx="{20 + 460 * (points[0][0] - min_x) / span:.1f}" '
            f'cy="{480 - 460 * (points[0][1] - min_y) / span:.1f}" r="5" fill="#5cd65c"/>'
            f'<circle cx="{20 + 460 * (points[-1][0] - min_x) / span:.1f}" '
            f'cy="{480 - 460 * (points[-1][1] - min_y) / span:.1f}" r="5" fill="#ff6b6b"/>'
            "</svg>"
            f"<p>green = first sample, red = last. Extent: X {min_x:.1f}..{max_x:.1f}, "
            f"Y {min_y:.1f}..{max_y:.1f} game units.</p>"
        )

    rows = "".join(
        f"<tr><td>{name}</td><td class='{'ok' if ok else 'bad'}'>"
        f"{'PASS' if ok else 'FAIL'}</td></tr>"
        for name, ok in report.acceptance.items()
    )
    hist = "".join(
        f"<tr><td>{bucket}</td><td>{count}</td><td>{'#' * min(60, count)}</td></tr>"
        for bucket, count in report.location_intervals.histogram.items()
    )
    features = "".join(
        f"<tr><td>{name}</td><td class='{'ok' if ok else 'bad'}'>{ok}</td></tr>"
        for name, ok in sorted(report.feature_registration.items())
    )
    warnings = (
        "".join(
            f"<li><code>{w.get('field')}</code>: {w.get('code')} - {w.get('detail', '')[:200]}</li>"
            for w in report.parse_warnings[:50]
        )
        or "<li>none</li>"
    )
    notes = "".join(f"<li>{n}</li>" for n in report.notes) or "<li>none</li>"

    noise = report.stationary_noise
    noise_html = (
        f"<p>distinct positions: {noise.samples} over {noise.window_s}s<br>"
        f"mean XY deviation: {noise.mean_xy_deviation_units} units<br>"
        f"P95 XY deviation: {noise.p95_xy_deviation_units} units<br>"
        f"max XY deviation: {noise.max_xy_deviation_units} units<br>"
        f"Z range: {noise.z_range_units} units</p>"
        if noise.measured
        else f"<p class='bad'>not measured: {noise.detail}</p>"
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Stage 1 sensor probe</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:2rem;background:#0d0d0d;color:#e6e6e6;max-width:1000px}}
 h1,h2{{border-bottom:1px solid #333;padding-bottom:.3rem}}
 table{{border-collapse:collapse;margin:1rem 0}} td,th{{border:1px solid #333;padding:.35rem .7rem}}
 .ok{{color:#5cd65c;font-weight:600}} .bad{{color:#ff6b6b;font-weight:600}}
 code{{background:#1b1b1b;padding:.1rem .3rem;border-radius:3px}}
 .verdict{{font-size:1.4rem;padding:.6rem 1rem;border-radius:6px;display:inline-block}}
 .sim{{background:#4a3800;border:1px solid #8a6a00;color:#ffd479;padding:.6rem 1rem;
       border-radius:6px;font-weight:600}}
</style></head><body>
<h1>Stage 1 - {"SIMULATED" if report.simulated else "live"} Overwolf sensor probe</h1>
<p>{report.generated_at} &middot; bot {report.bot_version} &middot;
   {report.duration_s}s at {report.poll_hz} Hz polling</p>
{
        '<p class="sim">SIMULATED RUN - synthetic bridge, not PUBG. '
        "This exercises the pipeline and is NOT evidence about the game. "
        "It can never count as a LIVE PASS.</p>"
        if report.simulated
        else ""
    }
<p class="verdict {"ok" if report.passed else "bad"}">
  {
        ("PIPELINE OK (SIMULATED)" if report.simulated else "LIVE PASS")
        if report.passed
        else "FAILED"
    }</p>

<h2>Acceptance</h2>
<table><tr><th>Criterion</th><th>Result</th></tr>{rows}</table>

<h2>Feature registration</h2>
<table><tr><th>Feature</th><th>Registered</th></tr>{
        features or "<tr><td colspan=2>none reported</td></tr>"
    }</table>

<h2>Position</h2>
<p>updates: {report.position_updates} &middot;
   path length: {report.total_path_length_units} units &middot;
   first: {report.first_position} &middot; last: {report.last_position}</p>
{svg}

<h2>Update interval</h2>
<p>median {report.location_intervals.p50_s}s
   (~{report.location_intervals.implied_hz} Hz) &middot;
   P95 {report.location_intervals.p95_s}s &middot;
   max {report.location_intervals.max_s}s</p>
<table><tr><th>Bucket</th><th>Count</th><th></th></tr>{hist}</table>

<h2>Stationary noise</h2>
{noise_html}

<h2>Observed identifiers</h2>
<p>maps: <code>{report.observed_maps or "none"}</code><br>
   phases: <code>{report.observed_phases or "none"}</code><br>
   views: <code>{report.observed_views or "none"}</code></p>

<h2>Parse warnings</h2><ul>{warnings}</ul>
<h2>Notes</h2><ul>{notes}</ul>
</body></html>"""


def write_probe_bundle(
    out_dir: Path,
    report: SensorProbeReport,
    samples: list[ProbeSample],
    frames: list[dict[str, Any]],
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out_dir / "sensor-probe.json",
        "html": out_dir / "report.html",
        "events": out_dir / "events.jsonl",
        "trace": out_dir / "position-trace.csv",
    }
    paths["json"].write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    paths["html"].write_text(_html(report, samples), encoding="utf-8")
    with paths["events"].open("w", encoding="utf-8") as handle:
        for frame in frames:
            handle.write(json.dumps(frame, default=str) + "\n")
    with paths["trace"].open("w", encoding="utf-8") as handle:
        handle.write("t,x,y,z,location_age_s,map,phase,view,stance,movement,free_view\n")
        for s in samples:
            x, y, z = s.position.as_tuple() if s.position else ("", "", "")
            handle.write(
                f"{s.at:.3f},{x},{y},{z},{s.location_age_s or ''},{s.map_id or ''},"
                f"{s.phase},{s.view},{s.stance},{s.movement},{s.free_view}\n"
            )
    return paths


__all__ = [
    "IntervalStats",
    "ProbeSample",
    "SensorProbeReport",
    "StationaryNoise",
    "build_report",
    "interval_stats",
    "stationary_noise",
    "write_probe_bundle",
]
