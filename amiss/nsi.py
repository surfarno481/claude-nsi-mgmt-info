# Copyright 2024-2025 SURF.
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

import requests
import requests.exceptions
import structlog
from pydantic import HttpUrl
from urllib3.util.retry import Retry

from amiss.settings import settings

logger = structlog.get_logger(__name__)


#
# Library
#

requests_session_adapter = requests.adapters.HTTPAdapter(max_retries=Retry(connect=3, backoff_factor=0.1))
session = requests.Session()
session.mount("http://", requests_session_adapter)
session.mount("https://", requests_session_adapter)


def nsi_util_get_json(url: HttpUrl, queryparams: dict) -> bytes | None:
    """Fetch JSON from a proxy endpoint; return the raw response body as bytes, or None on failure."""
    log = logger.bind()

    log.debug("SENDING HTTP REQUEST FOR JSON", url=str(url))
    try:
        # Append queries to URL, assume caller did proper escaping.
        fullurl = str(url)
        if len(queryparams) > 0:
            fullurl += "?"
        for k, v in queryparams.items():
            qstr = str(k) + "=" + str(v)
            fullurl += "&" + qstr

        r = session.get(
            fullurl,
            verify=settings.verify,
            cert=(str(settings.NSI_AMISS_CERTIFICATE), str(settings.NSI_AMISS_PRIVATE_KEY)),
        )
    except requests.exceptions.ConnectionError as e:
        log.warning("cannot get JSON document", url=str(url), error=str(e))
        return None

    if r.status_code != 200:
        log.warning(f"{url} returned {r.status_code} with message {r.reason}")
        return None
    if (content_type := r.headers["content-type"].lower()) != "application/json":
        log.warning(f"{url} did not return application/json but {content_type}")
        return None
    return r.content
