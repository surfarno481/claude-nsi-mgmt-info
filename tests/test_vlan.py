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

"""Tests for aura.vlan: VlanRanges class and DB-dependent functions."""

from unittest.mock import MagicMock, patch

import pytest

from aura.vlan import VlanRanges


class TestVlanRangesConstructor:
    @pytest.mark.parametrize(
        "val,expected_str",
        [
            pytest.param("4,10-12,11-14", "4,10-14", id="overlapping-string"),
            pytest.param("4, 11 - 14, 10-  12", "4,10-14", id="whitespace-string"),
            pytest.param("4,10-14", "4,10-14", id="clean-string"),
            pytest.param("1,2,3,4,5-10,8", "1-10", id="merge-to-single-range"),
            pytest.param("100", "100", id="single-vlan-string"),
            pytest.param("", "", id="empty-string"),
            pytest.param("  ", "", id="whitespace-only"),
            pytest.param(None, "", id="none"),
            pytest.param(42, "42", id="integer"),
            pytest.param([4, 10, 11, 12, 13, 14], "4,10-14", id="list-of-ints"),
            pytest.param([[4], [10, 12], [11, 14]], "4,10-14", id="list-of-lists"),
            pytest.param([(4, 4), (10, 14)], "4,10-14", id="list-of-tuples"),
            pytest.param({1, 2, 3}, "1-3", id="set-of-ints"),
        ],
    )
    def test_constructor_valid(self, val, expected_str):
        assert str(VlanRanges(val)) == expected_str

    @pytest.mark.parametrize(
        "val",
        [
            pytest.param("not-a-number", id="non-numeric-string"),
            pytest.param("abc", id="alpha-string"),
        ],
    )
    def test_constructor_invalid_string(self, val):
        with pytest.raises(ValueError, match="could not be converted"):
            VlanRanges(val)

    def test_constructor_out_of_range_high(self):
        with pytest.raises(ValueError, match="out of range"):
            VlanRanges("5000")

    def test_constructor_out_of_range_negative(self):
        with pytest.raises(ValueError, match="could not be converted"):
            VlanRanges("-1")


class TestVlanRangesSetOps:
    @pytest.mark.parametrize(
        "left,right,expected",
        [
            pytest.param("1-10", "5-8", "1-4,9-10", id="sub-middle"),
            pytest.param("1-10", "1-3", "4-10", id="sub-start"),
            pytest.param("1-10", "8-10", "1-7", id="sub-end"),
            pytest.param("1-10", "1-10", "", id="sub-everything"),
            pytest.param("1-10", "20-30", "1-10", id="sub-disjoint"),
        ],
    )
    def test_sub(self, left, right, expected):
        assert VlanRanges(left) - VlanRanges(right) == VlanRanges(expected)

    @pytest.mark.parametrize(
        "left,right,expected",
        [
            pytest.param("10-20", "20-30", "20", id="and-single-overlap"),
            pytest.param("1-5", "6-10", "", id="and-disjoint"),
            pytest.param("1-10", "5-15", "5-10", id="and-partial-overlap"),
        ],
    )
    def test_and(self, left, right, expected):
        assert (VlanRanges(left) & VlanRanges(right)) == VlanRanges(expected)

    @pytest.mark.parametrize(
        "left,right,expected",
        [
            pytest.param("10-20", "20-30", "10-30", id="or-adjacent"),
            pytest.param("1-5", "10-15", "1-5,10-15", id="or-disjoint"),
        ],
    )
    def test_or(self, left, right, expected):
        assert (VlanRanges(left) | VlanRanges(right)) == VlanRanges(expected)

    @pytest.mark.parametrize(
        "left,right,expected",
        [
            pytest.param("10-20", "20-30", "10-19,21-30", id="xor-single-overlap"),
        ],
    )
    def test_xor(self, left, right, expected):
        assert (VlanRanges(left) ^ VlanRanges(right)) == VlanRanges(expected)

    def test_sub_int(self):
        assert VlanRanges("1-5") - 3 == VlanRanges("1-2,4-5")


class TestVlanRangesDunderMethods:
    def test_contains_present(self):
        vr = VlanRanges("10-20,30-40")
        assert 15 in vr
        assert 35 in vr

    def test_contains_absent(self):
        vr = VlanRanges("10-20,30-40")
        assert 25 not in vr

    def test_iter(self):
        assert list(VlanRanges("1-3,5")) == [1, 2, 3, 5]

    @pytest.mark.parametrize(
        "val,expected_len",
        [
            pytest.param("1-10", 10, id="range"),
            pytest.param("", 0, id="empty-string"),
            pytest.param(None, 0, id="none"),
        ],
    )
    def test_len(self, val, expected_len):
        assert len(VlanRanges(val)) == expected_len

    def test_repr(self):
        assert repr(VlanRanges("1-10")) == "VlanRanges([(1, 10)])"

    def test_eq_same_content(self):
        a = VlanRanges("1-10")
        b = VlanRanges([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert a == b

    def test_eq_different_content(self):
        assert VlanRanges("1-10") != VlanRanges("1-9")

    def test_eq_different_type(self):
        assert VlanRanges("1-10") != "not a VlanRanges"

    def test_hash_equal_objects(self):
        a = VlanRanges("1-10")
        b = VlanRanges([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert hash(a) == hash(b)

    def test_isdisjoint_true(self):
        assert VlanRanges("1-5").isdisjoint(VlanRanges("6-10"))

    def test_isdisjoint_false(self):
        assert not VlanRanges("1-5").isdisjoint(VlanRanges("5-10"))

    def test_union_multiple(self):
        result = VlanRanges("10-20").union(VlanRanges("20-30"), {1, 2, 3, 4})
        assert result == VlanRanges("1-4,10-30")

    def test_to_list_of_tuples(self):
        assert VlanRanges("10-12,8").to_list_of_tuples() == [(8, 8), (10, 12)]

    def test_to_list_of_tuples_empty(self):
        assert VlanRanges(None).to_list_of_tuples() == []


class TestVlanRangesDbFunctions:
    @patch("aura.vlan.Session")
    def test_all_vlan_ranges(self, mock_session_cls):
        from aura.vlan import all_vlan_ranges

        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter.return_value.scalar.return_value = "100-200"

        result = all_vlan_ranges(1)
        assert result == VlanRanges("100-200")

    @patch("aura.vlan.Session")
    def test_in_use_vlan_ranges(self, mock_session_cls):
        from aura.vlan import in_use_vlan_ranges

        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.scalars.return_value.all.return_value = [100, 101]

        result = in_use_vlan_ranges(1)
        assert result == VlanRanges([100, 101])

    @patch("aura.vlan.free_vlan_ranges.__module__", new="aura.vlan")
    @patch("aura.vlan.in_use_vlan_ranges")
    @patch("aura.vlan.all_vlan_ranges")
    def test_free_vlan_ranges(self, mock_all, mock_in_use):
        from aura.vlan import free_vlan_ranges

        mock_all.return_value = VlanRanges("100-110")
        mock_in_use.return_value = VlanRanges([105])

        result = free_vlan_ranges(1)
        assert result == VlanRanges("100-104,106-110")
