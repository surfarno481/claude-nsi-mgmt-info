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

"""Tests for ROOT_PATH configuration.

Verifies that the FastAPI app respects the ROOT_PATH setting so that
it works correctly behind a reverse proxy with a path prefix (e.g. /aura),
including FastUI prebuilt_html parameters for the React SPA and that
image paths, form submit URLs, and search URLs are correctly prefixed.
"""

import pytest
from fastapi.testclient import TestClient

from aura.settings import Settings


@pytest.fixture()
def test_app():
    """Create the FastAPI app for testing."""
    from aura import app

    return app


@pytest.fixture()
def app_with_root_path(test_app):
    """Temporarily set ROOT_PATH on settings (without setting root_path on the app).

    We intentionally do NOT set app.root_path because Starlette's get_route_path()
    assumes scope["path"] contains root_path as a prefix. When a reverse proxy
    strips the prefix before forwarding, this breaks StaticFiles mounts by
    double-counting the mount path in the file lookup.
    """
    from aura.settings import settings

    original_settings_root = settings.ROOT_PATH
    settings.ROOT_PATH = "/aura"
    test_app.openapi_schema = None
    yield test_app
    settings.ROOT_PATH = original_settings_root
    test_app.openapi_schema = None


class TestRootPathConfig:
    def test_default_root_path_is_empty(self):
        settings = Settings.model_construct()
        assert settings.ROOT_PATH == ""

    def test_root_path_from_env(self, monkeypatch):
        monkeypatch.setenv("ROOT_PATH", "/aura")
        settings = Settings()
        assert settings.ROOT_PATH == "/aura"


class TestRootPathOpenApi:
    def test_openapi_available_without_root_path(self, test_app):
        client = TestClient(test_app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["openapi"]

    def test_openapi_available_with_root_path(self, app_with_root_path):
        client = TestClient(app_with_root_path)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["openapi"]


class TestRootPathRoutes:
    def test_routes_work_with_root_path(self, app_with_root_path):
        """ROOT_PATH must not change route matching — API paths stay the same."""
        client = TestClient(app_with_root_path)
        assert client.get("/healthcheck").status_code == 200
        assert client.get("/api/").status_code == 200

    def test_healthcheck_works_without_root_path(self, test_app):
        client = TestClient(test_app)
        assert client.get("/healthcheck").status_code == 200

    def test_static_files_work_with_root_path(self, app_with_root_path):
        """Static files must be served correctly when ROOT_PATH is set.

        This verifies the fix for a Starlette get_route_path() incompatibility:
        when root_path is set on the FastAPI app AND a reverse proxy strips the
        prefix, StaticFiles mounts break because the mount path gets double-counted
        in the file lookup (e.g. static/static/file.png instead of static/file.png).
        The fix is to NOT set root_path on the FastAPI app.
        """
        client = TestClient(app_with_root_path)
        resp = client.get("/static/ANA-website-footer.png")
        assert resp.status_code == 200

    def test_static_files_work_without_root_path(self, test_app):
        """Static files must work in the default (no ROOT_PATH) case."""
        client = TestClient(test_app)
        resp = client.get("/static/ANA-website-footer.png")
        assert resp.status_code == 200


class TestRootPathPrebuiltHtml:
    def test_html_landing_without_root_path(self, test_app):
        """Without ROOT_PATH, prebuilt_html uses defaults."""
        client = TestClient(test_app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_html_landing_with_root_path(self, app_with_root_path):
        """With ROOT_PATH, prebuilt_html receives api_root_url and api_path_strip."""
        client = TestClient(app_with_root_path)
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        # The prebuilt HTML should reference the prefixed API URL
        assert "/aura/api" in html

    def test_html_landing_no_prefix_in_default(self, test_app):
        """Without ROOT_PATH, the HTML should not contain path prefix references."""
        client = TestClient(test_app)
        resp = client.get("/")
        html = resp.text
        # api_path_strip should not appear in the default case
        assert "api_path_strip" not in html


def find_values(obj, key):
    """Recursively find all values for a given key in a nested dict/list structure."""
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                results.append(v)
            results.extend(find_values(v, key))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(find_values(item, key))
    return results


class TestRootPathImageUrls:
    def test_home_images_without_root_path(self, test_app):
        """Without ROOT_PATH, image src paths start with /static/."""
        client = TestClient(test_app)
        resp = client.get("/api/")
        assert resp.status_code == 200
        srcs = find_values(resp.json(), "src")
        static_srcs = [s for s in srcs if "/static/" in s]
        assert len(static_srcs) > 0
        for src in static_srcs:
            assert src.startswith("/static/")
            assert not src.startswith("/aura/static/")

    def test_home_images_with_root_path(self, app_with_root_path):
        """With ROOT_PATH, image src paths start with /aura/static/."""
        client = TestClient(app_with_root_path)
        resp = client.get("/api/")
        assert resp.status_code == 200
        srcs = find_values(resp.json(), "src")
        static_srcs = [s for s in srcs if "/static/" in s]
        assert len(static_srcs) > 0
        for src in static_srcs:
            assert src.startswith("/aura/static/")


class TestRootPathFormUrls:
    def test_reservation_form_urls_without_root_path(self, test_app):
        """Without ROOT_PATH, form submit and search URLs start with /api/."""
        client = TestClient(test_app)
        resp = client.get("/api/reservations/new")
        assert resp.status_code == 200
        data = resp.json()
        submit_urls = find_values(data, "submitUrl")
        assert any("/api/reservations/create" in u for u in submit_urls)
        for u in submit_urls:
            assert not u.startswith("/aura/")

    def test_reservation_form_urls_with_root_path(self, app_with_root_path):
        """With ROOT_PATH, form submit URLs are prefixed with /aura."""
        client = TestClient(app_with_root_path)
        resp = client.get("/api/reservations/new")
        assert resp.status_code == 200
        data = resp.json()
        submit_urls = find_values(data, "submitUrl")
        assert any("/aura/api/reservations/create" in u for u in submit_urls)

    def test_search_urls_without_root_path(self, test_app):
        """Without ROOT_PATH, search URLs start with /api/."""
        client = TestClient(test_app)
        resp = client.get("/api/reservations/new")
        assert resp.status_code == 200
        body = resp.text
        assert "/api/reservations/endpoints" in body
        assert "/aura/api/reservations/endpoints" not in body


class TestRootPathFieldGenerators:
    """Test that field generator functions use ROOT_PATH.

    Note: generate_stp_field/generate_sdp_field are called at class definition
    time for ReservationInputForm, so in production ROOT_PATH must be set before
    import. These tests verify the functions themselves produce correct URLs.
    """

    def test_stp_field_search_url_with_root_path(self):
        from aura.frontend.reservations import generate_stp_field
        from aura.settings import settings

        original = settings.ROOT_PATH
        try:
            settings.ROOT_PATH = "/aura"
            field = generate_stp_field("test")
            search_url = field.json_schema_extra["search_url"]
            assert search_url == "/aura/api/reservations/endpoints"
        finally:
            settings.ROOT_PATH = original

    def test_stp_field_search_url_without_root_path(self):
        from aura.frontend.reservations import generate_stp_field
        from aura.settings import settings

        original = settings.ROOT_PATH
        try:
            settings.ROOT_PATH = ""
            field = generate_stp_field("test")
            search_url = field.json_schema_extra["search_url"]
            assert search_url == "/api/reservations/endpoints"
        finally:
            settings.ROOT_PATH = original

    def test_sdp_field_search_url_with_root_path(self):
        from aura.frontend.reservations import generate_sdp_field
        from aura.settings import settings

        original = settings.ROOT_PATH
        try:
            settings.ROOT_PATH = "/aura"
            field = generate_sdp_field("test")
            search_url = field.json_schema_extra["search_url"]
            assert search_url == "/aura/api/reservations/demarcation_points"
        finally:
            settings.ROOT_PATH = original

    def test_sdp_field_search_url_without_root_path(self):
        from aura.frontend.reservations import generate_sdp_field
        from aura.settings import settings

        original = settings.ROOT_PATH
        try:
            settings.ROOT_PATH = ""
            field = generate_sdp_field("test")
            search_url = field.json_schema_extra["search_url"]
            assert search_url == "/api/reservations/demarcation_points"
        finally:
            settings.ROOT_PATH = original
