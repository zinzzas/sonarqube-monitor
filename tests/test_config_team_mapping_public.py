"""공개 팀 매핑 API — 이슈 목록 클라이언트가 서버 규칙과 동기화."""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from main import app


class ConfigTeamMappingPublicTests(unittest.TestCase):
    def test_get_team_mapping_public_ok(self) -> None:
        client = TestClient(app)
        r = client.get("/api/config/team-mapping")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertIn("teamMapping", data)
        self.assertIsInstance(data["teamMapping"], dict)


if __name__ == "__main__":
    unittest.main()
