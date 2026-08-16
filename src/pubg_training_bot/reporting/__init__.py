"""Evidence generation: stage reports now, run bundles and HTML reports later."""

from .stage_report import PytestSummary, StageReport, generate_stage_report

__all__ = ["PytestSummary", "StageReport", "generate_stage_report"]
