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

"""Tests for aura.nsi: HTTP communication functions (mocked)."""

from unittest.mock import MagicMock, patch

import pytest
import requests.exceptions


class TestNsiUtilGetXml:
    @patch("aura.nsi.session")
    def test_successful_get(self, mock_session):
        from aura.nsi import nsi_util_get_xml

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.content = b"<xml/>"
        mock_response.encoding = "utf-8"
        mock_session.get.return_value = mock_response

        result = nsi_util_get_xml("http://example.com/doc")
        assert result == b"<xml/>"

    @patch("aura.nsi.session")
    def test_connection_error_returns_none(self, mock_session):
        from aura.nsi import nsi_util_get_xml

        mock_session.get.side_effect = requests.exceptions.ConnectionError("fail")

        result = nsi_util_get_xml("http://example.com/doc")
        assert result is None

    @patch("aura.nsi.session")
    def test_non_200_returns_none(self, mock_session):
        from aura.nsi import nsi_util_get_xml

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.encoding = "utf-8"
        mock_response.content = b""
        mock_session.get.return_value = mock_response

        result = nsi_util_get_xml("http://example.com/doc")
        assert result is None

    @patch("aura.nsi.session")
    def test_wrong_content_type_returns_none(self, mock_session):
        from aura.nsi import nsi_util_get_xml

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.encoding = "utf-8"
        mock_response.content = b"<html/>"
        mock_session.get.return_value = mock_response

        result = nsi_util_get_xml("http://example.com/doc")
        assert result is None


class TestNsiUtilPostSoap:
    @patch("aura.nsi.session")
    def test_successful_post(self, mock_session):
        from aura.nsi import nsi_util_post_soap

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/xml;charset=utf-8"}
        mock_response.content = b"<soap:Envelope/>"
        mock_session.post.return_value = mock_response

        result = nsi_util_post_soap("http://example.com/nsi", b"<request/>")
        assert result == b"<soap:Envelope/>"

    @patch("aura.nsi.session")
    def test_non_xml_response_raises(self, mock_session):
        from aura.nsi import nsi_util_post_soap

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_session.post.return_value = mock_response

        with pytest.raises(Exception, match="did not return XML"):
            nsi_util_post_soap("http://example.com/nsi", b"<request/>")

    @patch("aura.nsi.session")
    def test_connection_error_propagates(self, mock_session):
        from aura.nsi import nsi_util_post_soap

        mock_session.post.side_effect = requests.exceptions.ConnectionError("fail")

        with pytest.raises(requests.exceptions.ConnectionError):
            nsi_util_post_soap("http://example.com/nsi", b"<request/>")

    @patch("aura.nsi.session")
    def test_non_200_raises(self, mock_session):
        from aura.nsi import nsi_util_post_soap

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_session.post.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            nsi_util_post_soap("http://example.com/nsi", b"<request/>")
