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

"""Tests for aura.dds: DDS parsing functions."""

import base64
import zlib
from unittest.mock import patch

import pytest
from sqlalchemy import or_, update

from aura.dds import has_alias, strip_urn, to_dict, to_list, topology_to_stps, unzip, update_sdps
from aura.model import SDP, STP
from tests.data.topology_samples import MINIMAL_TOPOLOGY, MOXY_TOPOLOGY


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
    @pytest.mark.parametrize(
        "inbound,outbound,expected",
        [
            pytest.param("alias_in", "alias_out", True, id="both-present"),
            pytest.param(None, "alias_out", False, id="inbound-none"),
            pytest.param("alias_in", None, False, id="outbound-none"),
            pytest.param(None, None, False, id="both-none"),
        ],
    )
    def test_has_alias(self, inbound, outbound, expected, stp_factory):
        stp = stp_factory(inboundAlias=inbound, outboundAlias=outbound)
        assert has_alias(stp) == expected


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


class TestTopologyToStps:
    def test_parses_moxy_topology(self):
        stps = topology_to_stps(MOXY_TOPOLOGY)
        assert len(stps) == 4
        stp_ids = {stp.stpId for stp in stps}
        assert "moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1" in stp_ids
        assert "moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1" in stp_ids
        assert "moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1" in stp_ids
        assert "moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2" in stp_ids

    def test_parses_vlan_ranges(self):
        stps = topology_to_stps(MOXY_TOPOLOGY)
        stp_by_id = {stp.stpId: stp for stp in stps}
        assert stp_by_id["moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1"].vlanRange == "3762-3769"
        assert stp_by_id["moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1"].vlanRange == "147"

    def test_parses_aliases_on_link_ports(self):
        stps = topology_to_stps(MOXY_TOPOLOGY)
        stp_by_id = {stp.stpId: stp for stp in stps}
        link1 = stp_by_id["moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1"]
        assert link1.inboundAlias == "surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-1:out"
        assert link1.outboundAlias == "surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-1:in"

    def test_no_aliases_on_endpoint_ports(self):
        stps = topology_to_stps(MOXY_TOPOLOGY)
        stp_by_id = {stp.stpId: stp for stp in stps}
        hpc = stp_by_id["moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1"]
        assert hpc.inboundAlias is None
        assert hpc.outboundAlias is None

    def test_parses_descriptions(self):
        stps = topology_to_stps(MOXY_TOPOLOGY)
        stp_by_id = {stp.stpId: stp for stp in stps}
        assert stp_by_id["moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1"].description == "High Performance Cluster in Canada"

    def test_all_stps_active(self):
        stps = topology_to_stps(MOXY_TOPOLOGY)
        assert all(stp.active for stp in stps)

    def test_missing_bidirectional_port_returns_empty(self):
        assert topology_to_stps({"id": "test"}) == []

    def test_missing_relation_returns_empty(self):
        topology = {"id": "test", "BidirectionalPort": []}
        assert topology_to_stps(topology) == []

    def test_minimal_topology(self):
        stps = topology_to_stps(MINIMAL_TOPOLOGY)
        assert len(stps) == 1
        assert stps[0].stpId == "test:2024:net:port-1"
        assert stps[0].vlanRange == "100-200"


class TestUpdateSdps:
    @staticmethod
    def _make_sdp_pair(db_session):
        """Insert a pair of STPs that form an SDP (mutual aliases) and return them."""
        stp_a = STP(
            stpId="east.example:2024:net:to-west-1",
            inboundPort="east.example:2024:net:to-west-1:in",
            outboundPort="east.example:2024:net:to-west-1:out",
            inboundAlias="west.example:2024:net:to-east-1:out",
            outboundAlias="west.example:2024:net:to-east-1:in",
            vlanRange="100-200",
            description="To West 1",
            active=True,
        )
        stp_z = STP(
            stpId="west.example:2024:net:to-east-1",
            inboundPort="west.example:2024:net:to-east-1:in",
            outboundPort="west.example:2024:net:to-east-1:out",
            inboundAlias="east.example:2024:net:to-west-1:out",
            outboundAlias="east.example:2024:net:to-west-1:in",
            vlanRange="100-200",
            description="To East 1",
            active=True,
        )
        db_session.add(stp_a)
        db_session.add(stp_z)
        db_session.flush()
        return stp_a, stp_z

    @staticmethod
    def _make_three_network_topology(db_session):
        """Create a 3-network hub topology (west <-> center <-> east) with 2 links per side.

        Returns all STPs. The center network connects to both west and east.
        This mirrors the real production topology from the logs.
        """
        # West network: 2 endpoints + 2 links to center
        west_endpoint = STP(
            stpId="west.example:2024:net:london-1",
            vlanRange="3000-3999", description="London", active=True,
        )
        west_link1 = STP(
            stpId="west.example:2024:net:to-east-1",
            inboundPort="west.example:2024:net:to-east-1:in",
            outboundPort="west.example:2024:net:to-east-1:out",
            inboundAlias="center.example:2024:net:to-west-1:out",
            outboundAlias="center.example:2024:net:to-west-1:in",
            vlanRange="1000-1999", description="To Center 1", active=True,
        )
        west_link2 = STP(
            stpId="west.example:2024:net:to-east-2",
            inboundPort="west.example:2024:net:to-east-2:in",
            outboundPort="west.example:2024:net:to-east-2:out",
            inboundAlias="center.example:2024:net:to-west-2:out",
            outboundAlias="center.example:2024:net:to-west-2:in",
            vlanRange="1000-1999", description="To Center 2", active=True,
        )

        # East network: 2 endpoints + 2 links to center
        east_endpoint = STP(
            stpId="east.example:2024:net:berlin-1",
            vlanRange="3000-3999", description="Berlin", active=True,
        )
        east_link1 = STP(
            stpId="east.example:2024:net:to-west-1",
            inboundPort="east.example:2024:net:to-west-1:in",
            outboundPort="east.example:2024:net:to-west-1:out",
            inboundAlias="center.example:2024:net:to-east-1:out",
            outboundAlias="center.example:2024:net:to-east-1:in",
            vlanRange="2000-2999", description="To Center 1", active=True,
        )
        east_link2 = STP(
            stpId="east.example:2024:net:to-west-2",
            inboundPort="east.example:2024:net:to-west-2:in",
            outboundPort="east.example:2024:net:to-west-2:out",
            inboundAlias="center.example:2024:net:to-east-2:out",
            outboundAlias="center.example:2024:net:to-east-2:in",
            vlanRange="2000-2999", description="To Center 2", active=True,
        )

        # Center network: 2 endpoints + 4 links (2 to west, 2 to east)
        center_endpoint = STP(
            stpId="center.example:2024:net:amsterdam-1",
            vlanRange="3000-3999", description="Amsterdam", active=True,
        )
        center_to_west1 = STP(
            stpId="center.example:2024:net:to-west-1",
            inboundPort="center.example:2024:net:to-west-1:in",
            outboundPort="center.example:2024:net:to-west-1:out",
            inboundAlias="west.example:2024:net:to-east-1:out",
            outboundAlias="west.example:2024:net:to-east-1:in",
            vlanRange="1000-1999", description="To West 1", active=True,
        )
        center_to_west2 = STP(
            stpId="center.example:2024:net:to-west-2",
            inboundPort="center.example:2024:net:to-west-2:in",
            outboundPort="center.example:2024:net:to-west-2:out",
            inboundAlias="west.example:2024:net:to-east-2:out",
            outboundAlias="west.example:2024:net:to-east-2:in",
            vlanRange="1000-1999", description="To West 2", active=True,
        )
        center_to_east1 = STP(
            stpId="center.example:2024:net:to-east-1",
            inboundPort="center.example:2024:net:to-east-1:in",
            outboundPort="center.example:2024:net:to-east-1:out",
            inboundAlias="east.example:2024:net:to-west-1:out",
            outboundAlias="east.example:2024:net:to-west-1:in",
            vlanRange="2000-2999", description="To East 1", active=True,
        )
        center_to_east2 = STP(
            stpId="center.example:2024:net:to-east-2",
            inboundPort="center.example:2024:net:to-east-2:in",
            outboundPort="center.example:2024:net:to-east-2:out",
            inboundAlias="east.example:2024:net:to-west-2:out",
            outboundAlias="east.example:2024:net:to-west-2:in",
            vlanRange="2000-2999", description="To East 2", active=True,
        )

        all_stps = [
            west_endpoint, west_link1, west_link2,
            east_endpoint, east_link1, east_link2,
            center_endpoint, center_to_west1, center_to_west2,
            center_to_east1, center_to_east2,
        ]
        for stp in all_stps:
            db_session.add(stp)
        db_session.flush()
        return all_stps

    @staticmethod
    def _patch_session(db_session):
        """Create a patch context that routes aura.dds.Session to the test db_session."""
        mock = patch("aura.dds.Session")
        mock_session_cls = mock.start()
        mock_session_cls.return_value.__enter__ = lambda _: db_session
        mock_session_cls.return_value.__exit__ = lambda *_: None
        mock_session_cls.begin.return_value.__enter__ = lambda _: db_session
        mock_session_cls.begin.return_value.__exit__ = lambda *_: None
        db_session.commit = lambda: None
        return mock

    def test_mark_sdp_inactive_uses_python_and_instead_of_sqlalchemy_and(self, db_session):
        """Bug on line 232: uses Python `and` instead of SQLAlchemy `&`.

        Because bool(BinaryExpression) is False in this SQLAlchemy version,
        Python's `and` short-circuits and returns the first operand, dropping
        the stpZId condition entirely. This generates:
            WHERE stpAId = ?          (wrong - missing stpZId)
        instead of:
            WHERE stpAId = ? AND stpZId = ?   (correct)
        """
        stp_a, stp_z = self._make_sdp_pair(db_session)

        # Python `and` short-circuits on the falsy BinaryExpression, returning only the first clause
        python_and_clause = SDP.stpAId == stp_a.id and SDP.stpZId == stp_z.id
        sqlalchemy_and_clause = (SDP.stpAId == stp_a.id) & (SDP.stpZId == stp_z.id)

        python_sql = str(python_and_clause.compile(compile_kwargs={"literal_binds": True}))
        sqla_sql = str(sqlalchemy_and_clause.compile(compile_kwargs={"literal_binds": True}))

        # The Python `and` drops the stpZId condition (wrong)
        assert "stpzid" not in python_sql.lower(), (
            f"Python `and` should have lost the stpZId condition, but got: {python_sql}"
        )
        # SQLAlchemy `&` correctly checks both columns
        assert "stpaid" in sqla_sql.lower() and "stpzid" in sqla_sql.lower(), (
            f"SQLAlchemy `&` should check both columns, but got: {sqla_sql}"
        )

    def test_duplicate_sdps_detected_by_one_or_none(self, db_session):
        """If duplicate SDPs exist in the database (corruption), one_or_none()
        correctly signals this by raising MultipleResultsFound.

        This is intentional — duplicates should never be created by the code,
        but if they exist (e.g., from a past bug or manual data entry),
        the error surfaces immediately rather than silently using wrong data.
        """
        stp_a, stp_z = self._make_sdp_pair(db_session)

        mock = self._patch_session(db_session)
        try:
            update_sdps()
            assert db_session.query(SDP).count() == 1

            # Manually insert a duplicate to simulate database corruption
            duplicate_sdp = SDP(
                stpAId=stp_a.id,
                stpZId=stp_z.id,
                vlanRange=stp_a.vlanRange,
                description=f"{stp_a.description} <-> {stp_z.description}",
            )
            db_session.add(duplicate_sdp)
            db_session.flush()

            from sqlalchemy.exc import MultipleResultsFound

            with pytest.raises(MultipleResultsFound):
                update_sdps()
        finally:
            mock.stop()

    def test_update_sdps_no_duplicates_across_runs(self, db_session):
        """Running update_sdps() multiple times must not create duplicate SDPs."""
        self._make_sdp_pair(db_session)

        mock = self._patch_session(db_session)
        try:
            for i in range(3):
                update_sdps()
                sdp_count = db_session.query(SDP).count()
                assert sdp_count == 1, f"Expected 1 SDP after run {i + 1}, got {sdp_count}"
        finally:
            mock.stop()

    def test_update_sdps_finds_sdp_regardless_of_stp_order(self, db_session):
        """An SDP(A, Z) must be found even when the STP pair is discovered in
        reverse order (Z, A) on a subsequent run. The or_ query covers both
        orderings, so no duplicate should be created."""
        stp_a, stp_z = self._make_sdp_pair(db_session)

        mock = self._patch_session(db_session)
        try:
            # First run creates SDP with (stp_a, stp_z) ordering
            update_sdps()
            assert db_session.query(SDP).count() == 1
            sdp = db_session.query(SDP).one()
            original_a, original_z = sdp.stpAId, sdp.stpZId

            # Manually insert a reversed SDP to simulate what would happen
            # if the code created (Z, A) instead of finding existing (A, Z)
            reversed_sdp = SDP(
                stpAId=original_z,
                stpZId=original_a,
                vlanRange=stp_a.vlanRange,
                description="reversed",
            )
            db_session.add(reversed_sdp)
            db_session.flush()

            # one_or_none() should detect the (A,Z)/(Z,A) duplicate via the or_ query
            from sqlalchemy.exc import MultipleResultsFound

            with pytest.raises(MultipleResultsFound):
                update_sdps()
        finally:
            mock.stop()
