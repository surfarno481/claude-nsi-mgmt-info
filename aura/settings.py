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

from pydantic import DirectoryPath, FilePath
from pydantic.networks import HttpUrl
from pydantic_settings import BaseSettings

#
# Settings
#


class Settings(BaseSettings):
    """Aura application settings."""

    SITE_TITLE: str = "AuRA - Demo"

    # host and port to bind to
    NSI_AURA_HOST: str = "127.0.0.1"
    NSI_AURA_PORT: int = 8000

    # certificate en key to authenticate against NSI control plane
    NSI_AURA_CERTIFICATE: FilePath = FilePath("aura-certificate.pem")
    NSI_AURA_PRIVATE_KEY: FilePath = FilePath("aura-private-key.pem")

    # override use of default CA bundle with certificates from a file or directory
    CA_CERTIFICATES: FilePath | DirectoryPath | None = None

    # requests certificate verification, only disable while debugging!
    VERIFY_REQUESTS: bool = True

    # database directory, may be relative or absolute
    DATABASE_URI: str = "sqlite:///db/aura.db"

    # directory containing static files, such as images and SOAP templates
    STATIC_DIRECTORY: DirectoryPath = DirectoryPath("static")

    # nsi-aura (external) URL (scheme, host, port, prefix)
    NSA_SCHEME: str = "http"
    NSA_HOST: str = "localhost"
    NSA_PORT: str = "8000"
    NSA_PATH_PREFIX: str = ""

    # NSI provider
    NSI_PROVIDER_URL: HttpUrl = HttpUrl("http://127.0.0.1:9000/nsi-v2/ConnectionServiceProvider")
    NSI_PROVIDER_ID: str = "urn:ogf:network:domain.example:2024:nsa"
    NSI_DDS_URL: HttpUrl = HttpUrl("http://dds.domain.example/dds/")

    # Logging
    SQL_LOGGING: bool = False
    LOG_LEVEL: str = "INFO"

    # ASGI root path prefix for reverse proxy with path stripping
    ROOT_PATH: str = ""

    # NOTE: HttpUrl class will automatically add trailing / when converting to str
    @property
    def NSA_BASE_URL(self) -> HttpUrl:
        """External base URL of this NSA."""
        return HttpUrl(f"{self.NSA_SCHEME}://{self.NSA_HOST}:{self.NSA_PORT}{self.NSA_PATH_PREFIX}")

    # Verify property for Requests:
    # False -> no verification
    # File path -> read CA certificates from file
    # Directory path -> read CA files from directory with symbolic links to files named by the hash values (c_rehash)
    # None -> verification with default Requests configured CA bundle
    @property
    def verify(self) -> str | bool | None:
        """Verify option for Requests calls."""
        return (str(self.CA_CERTIFICATES) if self.CA_CERTIFICATES else None) if self.VERIFY_REQUESTS else False


settings = Settings(_env_file="aura.env")
