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

"""Tests for aura.functional: expand_ranges() and to_ranges()."""

import pytest

from aura.functional import expand_ranges, to_ranges


class TestExpandRanges:
    @pytest.mark.parametrize(
        "ranges,inclusive,expected",
        [
            pytest.param([], False, [], id="empty-list-exclusive"),
            pytest.param([], True, [], id="empty-list-inclusive"),
            pytest.param([[1]], False, [1], id="single-value"),
            pytest.param([[1], [2], [3]], False, [1, 2, 3], id="multiple-single-values"),
            pytest.param([[1, 5]], False, [1, 2, 3, 4], id="range-exclusive"),
            pytest.param([[1, 5]], True, [1, 2, 3, 4, 5], id="range-inclusive"),
            pytest.param([[10, 12]], False, [10, 11], id="short-range-exclusive"),
            pytest.param([[10, 12]], True, [10, 11, 12], id="short-range-inclusive"),
            pytest.param([[1], [2], [10, 12]], True, [1, 2, 10, 11, 12], id="mixed-values-and-ranges"),
            pytest.param([[100], [1, 4]], True, [1, 2, 3, 4, 100], id="unsorted-input"),
            pytest.param([[1, 5], [3, 7]], True, [1, 2, 3, 4, 5, 6, 7], id="overlapping-ranges"),
            pytest.param([[1], [1]], False, [1], id="duplicate-values"),
            pytest.param([[5, 3]], False, [], id="reversed-range-exclusive"),
            pytest.param([[-5, -1]], True, [-5, -4, -3, -2, -1], id="negative-inclusive"),
            pytest.param([[-2, 2]], True, [-2, -1, 0, 1, 2], id="crossing-zero"),
            pytest.param([[0, 3]], True, [0, 1, 2, 3], id="starting-at-zero"),
            pytest.param([[0]], False, [0], id="single-zero"),
            pytest.param([[1, 1]], True, [1], id="single-element-range-inclusive"),
            pytest.param([[1, 1]], False, [], id="single-element-range-exclusive"),
        ],
    )
    def test_expand_ranges(self, ranges, inclusive, expected):
        assert expand_ranges(ranges, inclusive=inclusive) == expected

    @pytest.mark.parametrize(
        "bad_input,match",
        [
            pytest.param([[]], "Expected 1 or 2 element", id="empty-inner-list"),
            pytest.param([[1, 2, 3]], "Expected 1 or 2 element", id="three-element-list"),
            pytest.param([[1, 2, 3, 4]], "Expected 1 or 2 element", id="four-element-list"),
        ],
    )
    def test_expand_ranges_invalid_length(self, bad_input, match):
        with pytest.raises(ValueError, match=match):
            expand_ranges(bad_input)


class TestToRanges:
    @pytest.mark.parametrize(
        "input_iter,expected_ranges",
        [
            pytest.param(
                [2, 3, 4, 5, 7, 8, 9, 45, 46, 47, 49, 51, 53, 54, 55, 56, 57, 58, 59, 60, 61],
                [range(2, 6), range(7, 10), range(45, 48), range(49, 50), range(51, 52), range(53, 62)],
                id="mixed-ranges-from-docstring",
            ),
            pytest.param([1], [range(1, 2)], id="single-value"),
            pytest.param([1, 2, 3], [range(1, 4)], id="consecutive"),
            pytest.param([1, 3, 5], [range(1, 2), range(3, 4), range(5, 6)], id="non-consecutive"),
            pytest.param([], [], id="empty"),
            pytest.param([-5, -4, -3, 0, 1], [range(-5, -2), range(0, 2)], id="negative-numbers"),
            pytest.param([1, 1000000], [range(1, 2), range(1000000, 1000001)], id="large-gap"),
        ],
    )
    def test_to_ranges(self, input_iter, expected_ranges):
        assert list(to_ranges(input_iter)) == expected_ranges

    def test_generator_input(self):
        result = list(to_ranges(x for x in [1, 2, 3, 5]))
        assert result == [range(1, 4), range(5, 6)]
