# nsi-mgmt-info

The NSI Document Distribution Service proxy offers a REST API to retrieve
topologies, switching services, service termination points, and service
demarcation points from the combined topology documents found on the DDS.  The
information returned is a subset as needed by NSI ultimate Requester Agents
like the NSI Orchestrator, SENSE, and others.

## Project ANA-GRAM

This software is being developed by the 
[Advanced North-Atlantic Consortium](https://www.anaeng.global/), 
a cooperation between National Education and Research Networks (NRENs) and 
research partners to provide network connectivity for research and education 
across the North-Atlantic, as part of the ANA-GRAM project. 

The goal of the ANA-GRAM project is to federate the ANA trans-Atlantic links through
[Network Service Interface (NSI)](https://ogf.org/documents/GFD.237.pdf)-based automation.
This will enable the automated provisioning of L2 circuits spanning different domains 
between research parties on other sides of the Atlantic. The ANA-GRAM project is 
spearheaded by the ANA Platform & Requirements Working Group, under guidance of the 
ANA Engineering and ANA Planning Groups.  

<p align="center" width="50%">
    <img width="50%" src="/artwork/ana-logo-scaled-ab2.png">
</p>

## Prerequisites

- A valid client certificate and private key for mutual TLS authentication with the DDS server.
- Python 3.13+ (for running from source) or Docker.

## Configuration

All settings can be configured via environment variables or a `dds_proxy.env` file placed in the working directory. Environment variables take precedence over the env file.

| Variable | Default | Description |
|---|---|---|
| `DDS_BASE_URL` | `https://your-dds-server/dds` | Base URL of the upstream DDS server. |
| `DDS_CLIENT_CERT` | _(unset)_ | Path to the PEM-encoded client certificate used for mutual TLS with the DDS server. |
| `DDS_CLIENT_KEY` | _(unset)_ | Path to the PEM-encoded private key corresponding to the client certificate. |
| `DDS_CA_BUNDLE` | _(unset)_ | Path to a PEM file containing the CA certificates used to verify the DDS server. When set, replaces the system CA store entirely. |
| `CACHE_TTL_SECONDS` | `60` | How long (in seconds) the DDS response is cached before the next upstream fetch. |
| `HTTP_TIMEOUT_SECONDS` | `30.0` | Timeout (in seconds) for HTTP requests to the DDS server. |
| `LOG_LEVEL` | `INFO` | Logging verbosity. Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `DDS_PROXY_HOST` | `localhost` | Interface the server binds to. Set to `0.0.0.0` to accept connections on all interfaces. |
| `DDS_PROXY_PORT` | `8000` | TCP port the server listens on. |

A ready-to-use template is provided in `dds_proxy.env`. The application automatically reads this file from the working directory when it starts, so in most cases you only need to edit it in place.

If you want to maintain multiple configurations (e.g. for different environments), copy it and pass the copy explicitly via `docker run --env-file` or by exporting the variables in your shell:

```bash
cp dds_proxy.env production.env
# edit production.env

# Use with Docker:
docker run --env-file production.env ...

# Use in your shell (exports all non-comment lines as environment variables):
export $(grep -v '^#' production.env | xargs)
dds-proxy
```

Note that `docker run --env-file` expects plain `KEY=VALUE` lines — no `export` keyword, no quotes around values. The provided `dds_proxy.env` is already in this format.

## Running the Application

### From source with uv

Install dependencies and start the server:

```bash
uv sync
dds-proxy
```

The `dds-proxy` entry point starts a Uvicorn server using the host and port from your configuration. Make sure `dds_proxy.env` is present in the directory you run the command from, or export the required environment variables beforehand.

### With Python directly

If you have the package installed in your Python environment:

```bash
pip install .
dds-proxy
```

Or invoke Uvicorn manually, which lets you override host, port, and the number of workers:

```bash
uvicorn dds_proxy.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Note that when using `uvicorn` directly, `DDS_PROXY_HOST` and `DDS_PROXY_PORT` are ignored — pass them as CLI arguments instead.

### With Docker

A pre-built image is available on the GitHub Container Registry:

```
ghcr.io/workfloworchestrator/nsi-dds-proxy:0.1.0
```

Run it directly, mounting your certificate files and passing configuration via environment variables:

```bash
docker run --rm \
  -p 8000:8000 \
  -v /path/to/your/certs:/certs:ro \
  -e DDS_CLIENT_CERT=/certs/client-certificate.pem \
  -e DDS_CLIENT_KEY=/certs/client-private-key.pem \
  -e DDS_CA_BUNDLE=/certs/ca-bundle.pem \
  -e DDS_BASE_URL=https://your-dds-server/dds \
  ghcr.io/workfloworchestrator/nsi-dds-proxy:0.1.0
```

Or pass all settings via an env file:

```bash
docker run --rm \
  -p 8000:8000 \
  -v /path/to/your/certs:/certs:ro \
  --env-file production.env \
  ghcr.io/workfloworchestrator/nsi-dds-proxy:0.1.0
```

If you prefer to build the image yourself:

```bash
docker build -t nsi-dds-proxy .
```

### On Kubernetes

Store your client certificate and key in a Secret, then reference them in a Deployment:

```bash
kubectl create secret generic dds-proxy-certs \
  --from-file=client-certificate.pem=/path/to/client-certificate.pem \
  --from-file=client-private-key.pem=/path/to/client-private-key.pem \
  --from-file=ca-bundle.pem=/path/to/ca-bundle.pem
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nsi-dds-proxy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nsi-dds-proxy
  template:
    metadata:
      labels:
        app: nsi-dds-proxy
    spec:
      containers:
        - name: nsi-dds-proxy
          image: ghcr.io/workfloworchestrator/nsi-dds-proxy:0.1.0
          ports:
            - containerPort: 8000
          env:
            - name: DDS_BASE_URL
              value: "https://your-dds-server/dds"
            - name: DDS_PROXY_HOST
              value: "0.0.0.0"
            - name: DDS_CLIENT_CERT
              value: "/certs/client-certificate.pem"
            - name: DDS_CLIENT_KEY
              value: "/certs/client-private-key.pem"
            - name: DDS_CA_BUNDLE
              value: "/certs/ca-bundle.pem"
          volumeMounts:
            - name: certs
              mountPath: /certs
              readOnly: true
      volumes:
        - name: certs
          secret:
            secretName: dds-proxy-certs
---
apiVersion: v1
kind: Service
metadata:
  name: nsi-dds-proxy
spec:
  selector:
    app: nsi-dds-proxy
  ports:
    - port: 80
      targetPort: 8000
```

### With Helm chart

Using the same secret as above, and the `values.yaml` as below, add an `ingress` if needed,
and install with:

```shell
helm upgrade --install --namespace development --values values.yaml nsi-dds-proxy chart
```

```yaml
image:
  pullPolicy: IfNotPresent
  repository: ghcr.io/workfloworchestrator/nsi-dds-proxy
  tag: latest
env:
  CACHE_TTL_SECONDS: '60'
  DDS_BASE_URL: https://dds.your.domain/dds
  DDS_CA_BUNDLE: /certs/ca-bundle.pem
  DDS_CLIENT_CERT: /certs/client-certificate.pem
  DDS_CLIENT_KEY: /certs/client-private-key.pem
  DDS_PROXY_HOST: 0.0.0.0
  DDS_PROXY_PORT: '8000'
  HTTP_TIMEOUT_SECONDS: '30.0'
  LOG_LEVEL: INFO
livenessProbe:
  httpGet:
    path: /health
    port: 8000
readinessProbe:
  httpGet:
    path: /health
    port: 8000
resources:
  limits:
    cpu: 1000m
    memory: 128Mi
  requests:
    cpu: 10m
    memory: 64Mi
volumeMounts:
  - mountPath: /certs
    name: certs
    readOnly: true
volumes:
  - name: certs
    secret:
      optional: false
      secretName: dds-proxy-certs
```

## API Endpoints

### GET /topologies

Get a list of topologies found in DDS.

#### Response

```json
[
  {
    "id": "urn:ogf:network:example.domain.toplevel:2020:topology",
    "version": "2025-10-18 17:45 00:00",
    "name": "example.domain topology",
    "Lifetime": {
      "start": "2025-12-11T22:13:01+00:00",
      "end": "2025-12-18T22:13:01+00:00"
    },
  },
  ...
]
```

### GET /switching-services

Get a list of switching services found in all topologies found in DDS.

#### Response

```json
[
  {
    "id": "urn:ogf:network:example.domain.toplevel:2020:topology:switch:EVTS.ANA",
    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
    "labelSwapping": "true",
    "labelType": "http://schemas.ogf.org/nml/2012/10/ethernet#vlan",
    "topologyId": "urn:ogf:network:example.domain.toplevel:2020:topology"
  },
  ...
]
```

### GET /service-termination-points

Get a list of STP attached to all switching services found in all topologies.

#### Response

```json
[
  {
    "id": "urn:ogf:network:example.domain.toplevel:2020:topology:ps1",
    "name": "perfSONAR node 1",
    "capacity": 400000,
    "labelGroup": "2100-2400,3100-3400",
    "switchingServiceId": "urn:ogf:network:example.domain.toplevel:2020:topology:switch:EVTS.ANA"
  },
  ...
]
```

### GET /service-demarcation-points

Get a list of SDPs. Each SDP consists of a pair of matching STP attached to any
switching service found in all topologies.

```json
[
  {
    "stpAId": "urn:ogf:network:example.domain.toplevel:2020:topology:ps1",
    "stpZId": "urn:ogf:network:another.domain.toplevel:1999:topology:data-center-3"
  },
  ...
]
```
