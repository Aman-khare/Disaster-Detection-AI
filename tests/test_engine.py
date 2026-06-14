from __future__ import annotations

import unittest

from crisismind.engine import CrisisMindService
from crisismind.reporting import EmergencyPDFBuilder


class CrisisMindEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CrisisMindService(prefer_mcp=True)

    def test_flood_analysis_returns_actionable_outputs(self) -> None:
        report = self.service.analyze({"scenario_id": "raipur-flood"})
        self.assertGreaterEqual(report.risk_assessment.risk_score, 70)
        self.assertEqual(report.risk_assessment.status, "ELEVATED ALERT")
        self.assertGreaterEqual(len(report.safe_zones), 3)
        self.assertGreaterEqual(len(report.evacuation_routes), 3)
        self.assertIn("population_at_risk", report.dashboard_metrics.model_dump().keys())

    def test_heatwave_guidance_includes_hydration(self) -> None:
        report = self.service.analyze({"scenario_id": "raipur-heatwave"})
        combined = " ".join(report.precautionary_measures.during_disaster).lower()
        self.assertIn("water", combined)

    def test_pdf_builder_returns_pdf_bytes(self) -> None:
        report = self.service.analyze({"scenario_id": "raipur-cyclone"})
        pdf_bytes = EmergencyPDFBuilder().build_pdf(report)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 3000)

    def test_mcp_registry_reports_connected_servers(self) -> None:
        report = self.service.analyze({"scenario_id": "raipur-flood"})
        self.assertEqual(self.service.registry_mode, "mcp")
        self.assertEqual(len(report.integration_status), 3)
        self.assertTrue(all(item.connected for item in report.integration_status))


if __name__ == "__main__":
    unittest.main()
