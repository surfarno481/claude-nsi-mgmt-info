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

"""Tests for amiss.dds: DDS parsing functions."""

import base64
import zlib
from unittest.mock import patch

import pytest
from pydantic import HttpUrl

from amiss.dds import has_alias, strip_urn, to_dict, to_list, unzip
from amiss.model import SDP, STP


class TestStripUrn:
    @pytest.mark.parametrize(
        "urn,expected",
        [
            pytest.param("urn:ogf:network:surf.example:2024:net:port", "surf.example:2024:net:port", id="with-prefix"),
            pytest.param("surf.example:2024:net:port", "surf.example:2024:net:port", id="without-prefix"),
            pytest.param("urn:ogf:network:", "", id="only-prefix"),
        ],
    )
    def test_strip_urn(self, urn, expected):
        assert strip_urn(urn) == expected


class TestToDict:
    def test_with_list(self):
        collection = [{"id": "a", "val": 1}, {"id": "b", "val": 2}]
        assert to_dict("id", collection) == {"a": {"id": "a", "val": 1}, "b": {"id": "b", "val": 2}}

    def test_with_dict(self):
        collection = {"id": "a", "val": 1}
        assert to_dict("id", collection) == {"a": {"id": "a", "val": 1}}

    def test_with_unsupported_type(self):
        assert to_dict("id", "string") == {}


class TestToList:
    def test_basic(self):
        collection = [{"id": "a"}, {"id": "b"}]
        assert to_list("id", collection) == ["a", "b"]

    def test_single_element(self):
        assert to_list("key", [{"key": "value"}]) == ["value"]


class TestHasAlias:
    """has_alias now reports SDP membership via the isSdpMember flag."""

    def test_member(self, stp_factory):
        assert has_alias(stp_factory(isSdpMember=True)) is True

    def test_not_member(self, stp_factory):
        assert has_alias(stp_factory(isSdpMember=False)) is False


class TestUnzip:
    @staticmethod
    def _gzip_compress(data: bytes) -> bytes:
        """Compress data with gzip format (wbits=16+MAX_WBITS)."""
        compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
        return compressor.compress(data) + compressor.flush()

    def test_roundtrip(self):
        original = b"<topology>test</topology>"
        compressed = base64.b64encode(self._gzip_compress(original))
        doc = {"content": compressed.decode()}
        assert unzip(doc) == original

    def test_empty_content(self):
        original = b""
        compressed = base64.b64encode(self._gzip_compress(original))
        doc = {"content": compressed.decode()}
        assert unzip(doc) == original


def _patch_dds_session(db_session):
    """Route amiss.dds.Session (Session() and Session.begin()) to the test db_session."""
    mock = patch("amiss.dds.Session")
    mock_session_cls = mock.start()
    mock_session_cls.return_value.__enter__ = lambda _: db_session
    mock_session_cls.return_value.__exit__ = lambda *_: None
    mock_session_cls.begin.return_value.__enter__ = lambda _: db_session
    mock_session_cls.begin.return_value.__exit__ = lambda *_: None
    db_session.commit = lambda: None
    return mock


def _stp_dict(id="urn:ogf:network:example:2024:topo:ps1", name="node 1", labelGroup="100-200"):
    return {
        "id": id,
        "name": name,
        "capacity": 400000,
        "labelGroup": labelGroup,
        "switchingServiceId": "urn:ogf:network:example:2024:topo:switch:EVTS.ANA",
    }


class TestGetDdsProxyStps:
    @patch("amiss.dds.nsi_util_get_json")
    def test_appends_path_and_empty_queryparams(self, mock_get_json):
        from amiss.dds import get_dds_proxy_stps

        mock_get_json.return_value = b"[]"
        result = get_dds_proxy_stps(HttpUrl("http://proxy.example/dds-proxy/"))

        called_url, called_params = mock_get_json.call_args.args
        assert str(called_url) == "http://proxy.example/dds-proxy/service-termination-points"
        assert called_params == {}
        assert result == b"[]"

    @patch("amiss.dds.nsi_util_get_json")
    def test_handles_base_url_without_trailing_slash(self, mock_get_json):
        from amiss.dds import get_dds_proxy_stps

        get_dds_proxy_stps(HttpUrl("http://proxy.example/dds-proxy"))
        called_url, _ = mock_get_json.call_args.args
        assert str(called_url) == "http://proxy.example/dds-proxy/service-termination-points"

    @patch("amiss.dds.nsi_util_get_json")
    def test_returns_none_when_request_fails(self, mock_get_json):
        from amiss.dds import get_dds_proxy_stps

        mock_get_json.return_value = None
        assert get_dds_proxy_stps(HttpUrl("http://proxy.example/")) is None


class TestGetDdsProxySdps:
    @patch("amiss.dds.nsi_util_get_json")
    def test_appends_path_and_empty_queryparams(self, mock_get_json):
        from amiss.dds import get_dds_proxy_sdps

        mock_get_json.return_value = b"[]"
        result = get_dds_proxy_sdps(HttpUrl("http://proxy.example/dds-proxy/"))

        called_url, called_params = mock_get_json.call_args.args
        assert str(called_url) == "http://proxy.example/dds-proxy/service-demarcation-points"
        assert called_params == {}
        assert result == b"[]"

    @patch("amiss.dds.nsi_util_get_json")
    def test_handles_base_url_without_trailing_slash(self, mock_get_json):
        from amiss.dds import get_dds_proxy_sdps

        get_dds_proxy_sdps(HttpUrl("http://proxy.example/dds-proxy"))
        called_url, _ = mock_get_json.call_args.args
        assert str(called_url) == "http://proxy.example/dds-proxy/service-demarcation-points"

    @patch("amiss.dds.nsi_util_get_json")
    def test_returns_none_when_request_fails(self, mock_get_json):
        from amiss.dds import get_dds_proxy_sdps

        mock_get_json.return_value = None
        assert get_dds_proxy_sdps(HttpUrl("http://proxy.example/")) is None


class TestDdsProxyJsonToStps:
    def test_maps_fields_and_strips_urn(self):
        from amiss.dds import dds_proxy_json_to_stps

        stps = dds_proxy_json_to_stps([_stp_dict(id="urn:ogf:network:example:2024:topo:ps1", name="node 1", labelGroup="100-200")])

        assert len(stps) == 1
        stp = stps[0]
        assert stp.stpId == "example:2024:topo:ps1"
        assert stp.vlanRange == "100-200"
        assert stp.description == "node 1"
        assert stp.isSdpMember is False
        assert stp.active is True

    def test_skips_entry_missing_key(self):
        from amiss.dds import dds_proxy_json_to_stps

        bad = _stp_dict()
        del bad["labelGroup"]
        stps = dds_proxy_json_to_stps([bad, _stp_dict(id="urn:ogf:network:example:2024:topo:ps2", name="ok")])

        assert [s.stpId for s in stps] == ["example:2024:topo:ps2"]


class TestDdsProxyJsonToSdps:
    def test_persists_sdp_and_flags_stps(self, db_session, stp_factory):
        from amiss.dds import dds_proxy_json_to_sdps

        stp_a = stp_factory(stpId="example:2024:topo:ps1", vlanRange="100-200", description="A")
        stp_z = stp_factory(stpId="example:2024:topo:ps2", vlanRange="300-400", description="Z")
        db_session.add(stp_a)
        db_session.add(stp_z)
        db_session.flush()

        mock = _patch_dds_session(db_session)
        try:
            dds_proxy_json_to_sdps(
                [{"stpAId": "urn:ogf:network:example:2024:topo:ps1", "stpZId": "urn:ogf:network:example:2024:topo:ps2"}]
            )

            sdp = db_session.query(SDP).one()
            assert {sdp.stpAId, sdp.stpZId} == {stp_a.id, stp_z.id}
            assert sdp.vlanRange == stp_a.vlanRange
            assert sdp.description == "A <-> Z"
            assert db_session.query(STP).filter(STP.id == stp_a.id).one().isSdpMember is True
            assert db_session.query(STP).filter(STP.id == stp_z.id).one().isSdpMember is True
        finally:
            mock.stop()

    def test_idempotent_no_duplicate_sdp(self, db_session, stp_factory):
        from amiss.dds import dds_proxy_json_to_sdps

        db_session.add(stp_factory(stpId="example:2024:topo:ps1", description="A"))
        db_session.add(stp_factory(stpId="example:2024:topo:ps2", description="Z"))
        db_session.flush()
        pairs = [{"stpAId": "urn:ogf:network:example:2024:topo:ps1", "stpZId": "urn:ogf:network:example:2024:topo:ps2"}]

        mock = _patch_dds_session(db_session)
        try:
            dds_proxy_json_to_sdps(pairs)
            dds_proxy_json_to_sdps(pairs)
            assert db_session.query(SDP).count() == 1
        finally:
            mock.stop()

    def test_skips_pair_when_stp_missing(self, db_session, stp_factory):
        from amiss.dds import dds_proxy_json_to_sdps

        db_session.add(stp_factory(stpId="example:2024:topo:ps1", description="A"))
        db_session.flush()

        mock = _patch_dds_session(db_session)
        try:
            dds_proxy_json_to_sdps(
                [{"stpAId": "urn:ogf:network:example:2024:topo:ps1", "stpZId": "urn:ogf:network:example:2024:topo:missing"}]
            )
            assert db_session.query(SDP).count() == 0
        finally:
            mock.stop()
