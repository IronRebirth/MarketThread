from .engine import BacktestExecutionResult
from .report import BacktestPerformanceReport, build_performance_report


class BacktestPerformanceReportService:
    def build_report(
        self,
        execution: BacktestExecutionResult,
    ) -> BacktestPerformanceReport:
        return build_performance_report(execution)
