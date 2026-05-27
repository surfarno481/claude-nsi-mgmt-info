# Copyright 2024-2026 SURF.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the /healthcheck endpoint."""

from fastapi.testclient import TestClient


class TestHealthcheck:
    def test_returns_200_healthy(self, test_app):
        client = TestClient(test_app)
        response = client.get("/healthcheck")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
