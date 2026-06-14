from __future__ import annotations

import json
import threading
import unittest
from urllib import request

from crisismind.engine import CrisisMindService
from crisismind.server import make_server


class CrisisMindServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = make_server(host="127.0.0.1", port=0, service=CrisisMindService(prefer_mcp=True))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_health_endpoint(self) -> None:
        with request.urlopen(f"{self.base_url}/api/health") as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["registry_mode"], "mcp")

    def test_integrations_endpoint(self) -> None:
        with request.urlopen(f"{self.base_url}/api/integrations") as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["mode"], "mcp")
        self.assertEqual(len(payload["servers"]), 3)
        self.assertTrue(all(server["connected"] for server in payload["servers"]))

    def test_analyze_endpoint(self) -> None:
        payload = self._post_json("/api/analyze", {"scenario_id": "raipur-flood"})
        report = payload["report"]
        self.assertEqual(report["request"]["scenario_id"], "raipur-flood")
        self.assertGreaterEqual(report["risk_assessment"]["risk_score"], 70)
        self.assertTrue(all(server["connected"] for server in report["integration_status"]))

    def test_report_endpoint_returns_pdf(self) -> None:
        body = json.dumps({"scenario_id": "raipur-cyclone"}).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/report",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as response:
            pdf_bytes = response.read()
            content_type = response.headers.get("Content-Type")
        self.assertEqual(content_type, "application/pdf")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
