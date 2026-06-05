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

"""Tests for amiss.exception: Exception hierarchy."""

import pytest

from amiss.exception import AmissBaseError, AmissNsiError


class TestExceptions:
    @pytest.mark.parametrize(
        "exc_cls,message",
        [
            pytest.param(AmissBaseError, "test message", id="base-error"),
            pytest.param(AmissNsiError, "nsi error", id="nsi-error"),
            pytest.param(AmissBaseError, "", id="empty-message"),
            pytest.param(AmissNsiError, "unicode: \u00e9\u00e0\u00fc", id="unicode-message"),
        ],
    )
    def test_message_preserved(self, exc_cls, message):
        e = exc_cls(message)
        assert str(e) == message

    def test_amiss_base_error_is_exception(self):
        assert isinstance(AmissBaseError("x"), Exception)

    def test_amiss_nsi_error_inherits_base(self):
        e = AmissNsiError("x")
        assert isinstance(e, AmissBaseError)
        assert isinstance(e, Exception)

    def test_amiss_nsi_error_catchable_as_base(self):
        with pytest.raises(AmissBaseError):
            raise AmissNsiError("test")
