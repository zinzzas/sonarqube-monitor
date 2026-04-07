"""관리 API `/api/admin/team-mapping` 및 JSON 저장 검증."""
from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.services.metrics_service as metrics_service


def _minimal_labels_file(path: Path) -> None:
    data = {
        "version": 1,
        "teamMapping": {
            "_note": "keep me",
            "precedence": [
                {
                    "teamId": "team_a",
                    "label": "A팀",
                    "when": {"modules": ["portal"], "match": "first"},
                }
            ],
            "fallback": {"teamId": "shared", "label": "공통"},
        },
        "maps": {"java_tree": {"tree": {}}},
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class AdminTeamMappingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._cfg = Path(self._tmp.name) / "module_segment_labels.json"
        _minimal_labels_file(self._cfg)
        patcher = patch(
            "app.config.load_module_segment_labels._CONFIG_PATH",
            self._cfg,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        from main import app

        self.client = TestClient(app)
        self.addCleanup(self._tmp.cleanup)

    def test_get_returns_team_mapping(self) -> None:
        r = self.client.get("/api/admin/team-mapping")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("teamMapping", body)
        tm = body["teamMapping"]
        self.assertEqual(tm["_note"], "keep me")
        self.assertEqual(len(tm["precedence"]), 1)
        self.assertEqual(tm["fallback"]["teamId"], "shared")

    def test_put_persists_and_preserves_note_and_maps(self) -> None:
        payload = {
            "precedence": [
                {
                    "teamId": "team_b",
                    "label": "B",
                    "when": {"modules": ["atm", "x"], "match": "any"},
                }
            ],
            "fallback": {"teamId": "fb", "label": "FB"},
        }
        r = self.client.put("/api/admin/team-mapping", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        raw = json.loads(self._cfg.read_text(encoding="utf-8"))
        self.assertIn("maps", raw)
        self.assertEqual(raw["version"], 1)
        tm = raw["teamMapping"]
        self.assertEqual(tm["_note"], "keep me")
        self.assertEqual(tm["precedence"][0]["teamId"], "team_b")
        self.assertEqual(tm["precedence"][0]["when"]["modules"], ["atm", "x"])
        self.assertEqual(tm["precedence"][0]["when"]["match"], "any")

    def test_put_clears_dashboard_response_cache(self) -> None:
        metrics_service._CACHE = {"stub": True}
        metrics_service._CACHE_TS = time.time()
        metrics_service._DASH_CACHE_PROJECT = "any"
        metrics_service._PROJECT_CACHE["proj"] = (time.time(), {}, [])
        metrics_service._PROJECT_CACHE_BHM["proj"] = (time.time(), {}, [])
        payload = {
            "precedence": [
                {
                    "teamId": "team_c",
                    "label": "C",
                    "when": {"modules": ["z"], "match": "first"},
                }
            ],
            "fallback": {"teamId": "shared", "label": "공통"},
        }
        r = self.client.put("/api/admin/team-mapping", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(metrics_service._CACHE)
        self.assertIsNone(metrics_service._DASH_CACHE_PROJECT)
        self.assertEqual(len(metrics_service._PROJECT_CACHE), 0)
        self.assertEqual(len(metrics_service._PROJECT_CACHE_BHM), 0)

    def test_put_rejects_empty_when(self) -> None:
        payload = {
            "precedence": [
                {"teamId": "a", "label": "", "when": {"modules": [], "match": "any"}},
            ],
            "fallback": {"teamId": "z", "label": ""},
        }
        r = self.client.put("/api/admin/team-mapping", json=payload)
        self.assertEqual(r.status_code, 422)

    def test_put_rejects_duplicate_team_id(self) -> None:
        payload = {
            "precedence": [
                {
                    "teamId": "dup",
                    "label": "1",
                    "when": {"modules": ["a"], "match": "first"},
                },
                {
                    "teamId": "dup",
                    "label": "2",
                    "when": {"modules": ["b"], "match": "first"},
                },
            ],
            "fallback": {"teamId": "z", "label": ""},
        }
        r = self.client.put("/api/admin/team-mapping", json=payload)
        self.assertEqual(r.status_code, 422)

    def test_bearer_required_when_token_set(self) -> None:
        from app.core.config import settings

        with patch.object(settings, "admin_team_mapping_token", "secret-token"):
            r = self.client.get("/api/admin/team-mapping")
            self.assertEqual(r.status_code, 401)
            r2 = self.client.get(
                "/api/admin/team-mapping",
                headers={"Authorization": "Bearer secret-token"},
            )
            self.assertEqual(r2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
