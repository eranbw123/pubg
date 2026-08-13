"""Command line interface.

Stdlib ``argparse`` on purpose: the CLI is an operator tool, not a product
surface, and every dependency added here has to be installed before the doctor
can tell you what is missing.

Commands available at Stage 0::

    pubg-bot doctor [--json] [--out DIR]
    pubg-bot stage status [--json] [--write-docs]
    pubg-bot stage set --stage NN --status STATUS [--notes ...] [--blocker ...]
    pubg-bot stage report --stage NN [--tests-passed N] [--tests-failed N] ...
    pubg-bot schemas export [--check]
    pubg-bot safety scan [--json]
    pubg-bot version

Commands that would touch the game do not exist yet; they are introduced by the
stage that makes them real.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .. import __version__
from ..actuation.registry import list_actuators, live_actuator_available
from ..config.paths import default_paths
from ..diagnostics.doctor import run_doctor, write_doctor_report
from ..reporting.stage_report import PytestSummary, generate_stage_report
from ..safety import scan_source
from ..schema_export import export_schemas
from ..stages import (
    STAGES,
    StageStatus,
    current_stage,
    gate_check,
    load_state,
    render_status_markdown,
    set_status,
    write_status_doc,
)

EXIT_OK = 0
EXIT_FAILED_CHECK = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pubg-bot",
        description="PUBG Training Mode teach-and-repeat bot (Windows-only MVP).",
    )
    parser.add_argument("--version", action="version", version=f"pubg-training-bot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Report environment readiness (read-only).")
    doctor.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    doctor.add_argument("--out", help="Directory to write doctor.json and doctor.txt into.")
    doctor.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any check fails (default: only usage errors fail).",
    )

    stage = sub.add_parser("stage", help="Stage-gate state and reports.")
    stage_sub = stage.add_subparsers(dest="stage_command", required=True)

    status = stage_sub.add_parser("status", help="Show stage-gate status.")
    status.add_argument("--json", action="store_true")
    status.add_argument(
        "--write-docs", action="store_true", help="Regenerate docs/stage-status.md."
    )

    setter = stage_sub.add_parser("set", help="Record a stage status transition.")
    setter.add_argument("--stage", required=True)
    setter.add_argument("--status", required=True, choices=[s.value for s in StageStatus])
    setter.add_argument("--notes", default="")
    setter.add_argument("--blocker", default="")
    setter.add_argument("--evidence", nargs="*", default=None)

    report = stage_sub.add_parser("report", help="Generate reports/stages/stage-NN/.")
    report.add_argument("--stage", required=True)
    report.add_argument("--tests-passed", type=int, default=0)
    report.add_argument("--tests-failed", type=int, default=0)
    report.add_argument("--tests-errors", type=int, default=0)
    report.add_argument("--tests-skipped", type=int, default=0)
    report.add_argument("--tests-ran", action="store_true")
    report.add_argument("--tests-command", default="")
    report.add_argument(
        "--check",
        action="append",
        default=None,
        metavar="NAME=pass|fail",
        help="Record an automated check result; repeatable.",
    )
    report.add_argument("--open-question", action="append", default=None)

    schemas = sub.add_parser("schemas", help="JSON Schema files for the persisted contracts.")
    schemas_sub = schemas.add_subparsers(dest="schemas_command", required=True)
    export = schemas_sub.add_parser("export", help="Write schemas/ from the pydantic models.")
    export.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit non-zero if committed schemas are stale.",
    )

    probe = sub.add_parser("probe", help="Live, read-only feasibility probes.")
    probe_sub = probe.add_subparsers(dest="probe_command", required=True)
    sensors = probe_sub.add_parser(
        "sensors", help="Stage 1: measure what the live Overwolf stream provides."
    )
    sensors.add_argument("--duration", type=float, default=120.0, help="Seconds to record.")
    sensors.add_argument(
        "--still", type=float, default=20.0, help="Opening seconds spent motionless."
    )
    sensors.add_argument("--poll-hz", type=float, default=10.0)
    sensors.add_argument("--port", type=int, default=None)
    sensors.add_argument("--token", default=None, help="Session token; generated if omitted.")
    sensors.add_argument("--connect-timeout", type=float, default=180.0)

    safety = sub.add_parser("safety", help="Scope lock and live-input interlock.")
    safety_sub = safety.add_subparsers(dest="safety_command", required=True)
    scan = safety_sub.add_parser("scan", help="Scan the source tree for out-of-scope techniques.")
    scan.add_argument("--json", action="store_true")

    sub.add_parser("version", help="Print the version.")
    return parser


# --------------------------------------------------------------------------- #
# Command implementations
# --------------------------------------------------------------------------- #
def cmd_doctor(args: argparse.Namespace) -> int:
    paths = default_paths()
    report = run_doctor(paths)
    if args.out:
        from pathlib import Path

        written = write_doctor_report(report, Path(args.out))
        print(f"wrote {written['json']}")
        print(f"wrote {written['text']}")
    if args.json:
        print(report.to_json())
    elif not args.out:
        print(report.to_text())
    if args.strict and report.blocking_failures:
        return EXIT_FAILED_CHECK
    return EXIT_OK


def cmd_stage_status(args: argparse.Namespace) -> int:
    paths = default_paths()
    state = load_state(paths)
    if args.write_docs:
        target = write_status_doc(paths, state)
        print(f"wrote {target}")
    if args.json:
        payload = {
            "active_stage": current_stage(state).stage_id,
            "stages": [
                {
                    "stage_id": spec.stage_id,
                    "title": spec.title,
                    "requires_live_game": spec.requires_live_game,
                    "status": str(state.record(spec.stage_id).status),
                    "accepted_at": state.record(spec.stage_id).accepted_at,
                    "blocker": state.record(spec.stage_id).blocker,
                }
                for spec in STAGES
            ],
        }
        print(json.dumps(payload, indent=2))
    elif not args.write_docs:
        print(render_status_markdown(state))
    return EXIT_OK


def cmd_stage_set(args: argparse.Namespace) -> int:
    status = StageStatus(args.status)
    if status is StageStatus.ACCEPTED:
        allowed, why = gate_check(args.stage)
        if not allowed:
            print(f"refusing to accept stage {args.stage}: {why}", file=sys.stderr)
            return EXIT_FAILED_CHECK
    state = set_status(
        args.stage,
        status,
        notes=args.notes,
        blocker=args.blocker,
        evidence=args.evidence,
    )
    write_status_doc(state=state)
    print(f"stage {args.stage} -> {status}")
    return EXIT_OK


def cmd_stage_report(args: argparse.Namespace) -> int:
    checks: dict[str, str] = {}
    for entry in args.check or []:
        if "=" not in entry:
            print(f"--check expects NAME=pass|fail, got {entry!r}", file=sys.stderr)
            return EXIT_USAGE
        name, _, result = entry.partition("=")
        checks[name.strip()] = result.strip()

    tests = PytestSummary(
        passed=args.tests_passed,
        failed=args.tests_failed,
        errors=args.tests_errors,
        skipped=args.tests_skipped,
        ran=args.tests_ran or args.tests_passed > 0,
        command=args.tests_command,
    )
    report, out_dir = generate_stage_report(
        args.stage,
        automated_checks=checks,
        tests=tests,
        open_questions=args.open_question or [],
    )
    print(f"wrote {out_dir}")
    print(f"automated result: {'AUTOMATED PASS' if report.automated_pass else 'FAILED'}")
    return EXIT_OK if report.automated_pass else EXIT_FAILED_CHECK


def cmd_schemas_export(args: argparse.Namespace) -> int:
    _, drifted = export_schemas(check_only=args.check)
    if args.check:
        if drifted:
            print("schemas are stale: " + ", ".join(drifted), file=sys.stderr)
            print("run: pubg-bot schemas export", file=sys.stderr)
            return EXIT_FAILED_CHECK
        print("schemas up to date")
        return EXIT_OK
    print(f"exported {len(list(default_paths().schemas_dir.glob('*.schema.json')))} schema files")
    if drifted:
        print("updated: " + ", ".join(drifted))
    return EXIT_OK


def cmd_probe_sensors(args: argparse.Namespace) -> int:
    from ..config.loader import load_config
    from ..probe import ProbeOptions, run_sensor_probe

    paths = default_paths()
    config = load_config(paths=paths)
    options = ProbeOptions(
        duration_s=args.duration,
        poll_hz=args.poll_hz,
        still_seconds=args.still,
        connect_timeout_s=args.connect_timeout,
        host=config.bridge.host,
        port=args.port if args.port is not None else config.bridge.port,
        token=args.token or config.bridge.session_token,
    )
    report, out_dir = run_sensor_probe(options, paths=paths)

    print()
    for name, ok in report.acceptance.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    for note in report.notes:
        print(f"  note: {note}")
    print()
    print(f"STAGE 01 PROBE: {'AUTOMATED PASS' if report.passed else 'FAILED'}")
    print(f"evidence: {out_dir}")
    return EXIT_OK if report.passed else EXIT_FAILED_CHECK


def cmd_safety_scan(args: argparse.Namespace) -> int:
    report = scan_source()
    if args.json:
        payload = report.model_dump(mode="json")
        payload["live_input_possible"] = report.live_input_possible
        payload["ok"] = report.ok
        print(json.dumps(payload, indent=2))
    else:
        print(report.summary())
        print("registered actuators:")
        for descriptor in list_actuators():
            print(f"  - {descriptor.key}: live={descriptor.live} ({descriptor.description})")
        print(f"live actuator available: {live_actuator_available()}")
        for finding in report.forbidden_findings:
            print(f"  FORBIDDEN {finding.file}:{finding.line} {finding.code}")
        for finding in report.input_findings:
            print(f"  INPUT     {finding.file}:{finding.line} {finding.code}")
    return EXIT_OK if report.ok else EXIT_FAILED_CHECK


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "stage":
        if args.stage_command == "status":
            return cmd_stage_status(args)
        if args.stage_command == "set":
            return cmd_stage_set(args)
        if args.stage_command == "report":
            return cmd_stage_report(args)
    if args.command == "probe" and args.probe_command == "sensors":
        return cmd_probe_sensors(args)
    if args.command == "schemas":
        return cmd_schemas_export(args)
    if args.command == "safety":
        return cmd_safety_scan(args)
    if args.command == "version":
        print(__version__)
        return EXIT_OK

    parser.error(f"unhandled command {args.command!r}")
    return EXIT_USAGE  # pragma: no cover - argparse exits


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
