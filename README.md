# nsi-mgmt-info

The NSI Management Information Service offers an interface to obtain information that ANA manangement 
needs for decision making. In other words, this service makes available and visualizes data effectively to enable strategic and engineering decision-making processes. The nsi-mgmt-info service uses information from the NSI-Orchestrator and other ANA-NSI 
components to generate useful overviews and statistics.
  
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

- A valid client certificate and private key for mutual TLS authentication with the ANA-NSI components.
- Python 3.13+ (for running from source) or Docker.

## Configuration

All settings can be configured via environment variables or a `mgmtinfo_proxy.env` file placed in the working directory. Environment variables take precedence over the env file.

| Variable | Default | Description |
|---|---|---|
| `MGMTINFO_BASE_URL` | `https://your-orchestrator-server/mgmt` | Base URL of the upstream WFO server. |
| `MGMTINFO_CLIENT_CERT` | _(unset)_ | Path to the PEM-encoded client certificate used for mutual TLS with the MGMTINFO server. |
| `MGMTINFO_CLIENT_KEY` | _(unset)_ | Path to the PEM-encoded private key corresponding to the client certificate. |
| `MGMTINFO_CA_BUNDLE` | _(unset)_ | Path to a PEM file containing the CA certificates used to verify the MGMTINFO server. When set, replaces the system CA store entirely. |
| `CACHE_TTL_SECONDS` | `60` | How long (in seconds) the MGMTINFO response is cached before the next upstream fetch. |
| `HTTP_TIMEOUT_SECONDS` | `30.0` | Timeout (in seconds) for HTTP requests to the MGMTINFO server. |
| `LOG_LEVEL` | `INFO` | Logging verbosity. Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `MGMTINFO_PROXY_HOST` | `localhost` | Interface the server binds to. Set to `0.0.0.0` to accept connections on all interfaces. |
| `MGMTINFO_PROXY_PORT` | `8000` | TCP port the server listens on. |

A ready-to-use template is provided in `mgmtinfo_proxy.env`. The application automatically reads this file from the working directory when it starts, so in most cases you only need to edit it in place.

If you want to maintain multiple configurations (e.g. for different environments), copy it and pass the copy explicitly via `docker run --env-file` or by exporting the variables in your shell:

```bash
cp mgmtinfo_proxy.env production.env
# edit production.env

# Use with Docker:
docker run --env-file production.env ...

# Use in your shell (exports all non-comment lines as environment variables):
export $(grep -v '^#' production.env | xargs)
mgmt-info
```

Note that `docker run --env-file` expects plain `KEY=VALUE` lines — no `export` keyword, no quotes around values. The provided `mgmtinfo_proxy.env` is already in this format.

## Running the Application

### From source with uv

Install dependencies and start the server:

```bash
uv sync
mgmt-info
```

The `mgmt-info` entry point starts a Uvicorn server using the host and port from your configuration. Make sure `mgmtinfo_proxy.env` is present in the directory you run the command from, or export the required environment variables beforehand.

### With Python directly

If you have the package installed in your Python environment:

```bash
pip install .
mgmt-info
```

Or invoke Uvicorn manually, which lets you override host, port, and the number of workers:

```bash
uvicorn mgmtinfo_proxy.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Note that when using `uvicorn` directly, `MGMTINFO_PROXY_HOST` and `MGMTINFO_PROXY_PORT` are ignored — pass them as CLI arguments instead.

### With Docker

A pre-built image is available on the GitHub Container Registry:

```
ghcr.io/workfloworchestrator/nsi-mgmt-info:0.1.0
```

Run it directly, mounting your certificate files and passing configuration via environment variables:

```bash
docker run --rm \
  -p 8000:8000 \
  -v /path/to/your/certs:/certs:ro \
  -e MGMTINFO_CLIENT_CERT=/certs/client-certificate.pem \
  -e MGMTINFO_CLIENT_KEY=/certs/client-private-key.pem \
  -e MGMTINFO_CA_BUNDLE=/certs/ca-bundle.pem \
  -e MGMTINFO_BASE_URL=https://your-dds-server/dds \
  ghcr.io/workfloworchestrator/nsi-mgmt-info:0.1.0
```

Or pass all settings via an env file:

```bash
docker run --rm \
  -p 8000:8000 \
  -v /path/to/your/certs:/certs:ro \
  --env-file production.env \
  ghcr.io/workfloworchestrator/nsi-mgmt-info:0.1.0
```

If you prefer to build the image yourself:

```bash
docker build -t nsi-mgmt-info .
```

### On Kubernetes

Store your client certificate and key in a Secret, then reference them in a Deployment:

```bash
kubectl create secret generic mgmt-info-certs \
  --from-file=client-certificate.pem=/path/to/client-certificate.pem \
  --from-file=client-private-key.pem=/path/to/client-private-key.pem \
  --from-file=ca-bundle.pem=/path/to/ca-bundle.pem
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nsi-mgmt-info
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nsi-mgmt-info
  template:
    metadata:
      labels:
        app: nsi-mgmt-info
    spec:
      containers:
        - name: nsi-mgmt-info
          image: ghcr.io/workfloworchestrator/nsi-mgmt-info:0.1.0
          ports:
            - containerPort: 8000
          env:
            - name: MGMTINFO_BASE_URL
              value: "https://your-wfo-server/mgmt"
            - name: MGMTINFO_PROXY_HOST
              value: "0.0.0.0"
            - name: MGMTINFO_CLIENT_CERT
              value: "/certs/client-certificate.pem"
            - name: MGMTINFO_CLIENT_KEY
              value: "/certs/client-private-key.pem"
            - name: MGMTINFO_CA_BUNDLE
              value: "/certs/ca-bundle.pem"
          volumeMounts:
            - name: certs
              mountPath: /certs
              readOnly: true
      volumes:
        - name: certs
          secret:
            secretName: mgmt-info-certs
---
apiVersion: v1
kind: Service
metadata:
  name: nsi-mgmt-info
spec:
  selector:
    app: nsi-mgmt-info
  ports:
    - port: 80
      targetPort: 8000
```

### With Helm chart

Using the same secret as above, and the `values.yaml` as below, add an `ingress` if needed,
and install with:

```shell
helm upgrade --install --namespace development --values values.yaml nsi-mgmt-info chart
```

```yaml
image:
  pullPolicy: IfNotPresent
  repository: ghcr.io/workfloworchestrator/nsi-mgmt-info
  tag: latest
env:
  CACHE_TTL_SECONDS: '60'
  MGMTINFO_BASE_URL: https://nsi-orchestrator.your.domain/mgmt
  MGMTINFO_CA_BUNDLE: /certs/ca-bundle.pem
  MGMTINFO_CLIENT_CERT: /certs/client-certificate.pem
  MGMTINFO_CLIENT_KEY: /certs/client-private-key.pem
  MGMTINFO_PROXY_HOST: 0.0.0.0
  MGMTINFO_PROXY_PORT: '8000'
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
      secretName: mgmt-info-certs
```

