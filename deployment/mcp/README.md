# MCP Docker Compose Deployment

This deployment builds and runs the `mcp_consumption` server as a Docker
container. Runtime configuration is read from environment variables in
`deployment/mcp/.env`.

> Security note: this deployment copies the local OCI API-key configuration into
> the image at build time under `/home/app/.oci`. This is convenient for native
> Linux testing, but the resulting image contains credentials. Keep the image on
> trusted hosts only, do not push it to registries, and rebuild it whenever the
> OCI keys rotate.

## Files

- `Dockerfile`: builds the MCP server image.
- `docker-compose.yml`: runs the MCP server on streamable HTTP.
- `.env.sample`: environment template for the deployment.
- `oci/`: local staging folder for the content of `$HOME/.oci`; ignored by Git.

## 1. Prepare Environment

Run commands from the repository root:

```bash
cd deployment/mcp
cp .env.sample .env
```

Edit `deployment/mcp/.env` and set all values for the target environment:

```bash
MCP_IMAGE_TAG=latest
MCP_CONTAINER_NAME=oci-cloud-consumption-mcp
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_PUBLISHED_PORT=8000
MCP_PATH=/mcp

OCI_REGION=eu-frankfurt-1
OCI_AUTH_TYPE=API_KEY
OCI_CONFIG_PROFILE=DEFAULT
```

Required OCI variables:

- `OCI_REGION`: region used by the OCI SDK. The application intentionally does
  not read the region from the OCI profile.
- `OCI_AUTH_TYPE`: use `API_KEY` for copied `$HOME/.oci` credentials.
- `OCI_CONFIG_PROFILE`: profile name from `/home/app/.oci/config`.

## 2. Copy OCI Credentials

From `deployment/mcp`, copy the host OCI configuration into the local staging
folder:

```bash
mkdir -p oci
cp -a "$HOME/.oci/." oci/
find oci -type d -exec chmod 700 {} \;
find oci -type f -exec chmod 600 {} \;
```

The Docker build copies this folder to `/home/app/.oci` inside the image.

Check `oci/config` before building. If a profile uses `key_file`, prefer a path
that resolves inside the container, for example:

```ini
key_file=~/.oci/oci_api_key.pem
```

or:

```ini
key_file=/home/app/.oci/oci_api_key.pem
```

## 3. Build And Start

From `deployment/mcp`:

```bash
docker compose build --no-cache
docker compose up -d
```

Check status and logs:

```bash
docker compose ps
docker compose logs -f mcp-consumption
```

The server listens on:

```text
http://localhost:8000/mcp
```

If you change `MCP_PUBLISHED_PORT` or `MCP_PATH`, adjust the URL accordingly.

## 4. Smoke Test

Verify that the container is running and the TCP health check is healthy:

```bash
docker compose ps
```

List the tools exposed by the MCP server:

```bash
python list_tools.py http://127.0.0.1:8000/mcp
```

From another machine, replace the host with the Linux server address:

```bash
python deployment/mcp/list_tools.py http://PROXIMA_IP:8000/mcp
```

For a client running on the same Linux host, use this MCP connection:

```json
{
  "servers": [
    {
      "name": "consumption",
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "streamable_http",
      "enabled": true
    }
  ]
}
```

To call OCI successfully, the selected profile must have permissions for OCI
Usage API and Identity compartment listing.

## 5. Stop Or Rebuild

Stop the server:

```bash
docker compose down
```

After changing `.env`, restart:

```bash
docker compose up -d
```

After changing OCI credentials in `oci/`, rebuild because credentials are copied
into the image:

```bash
docker compose build --no-cache
docker compose up -d
```

## 6. Production Notes

`Design.md` requires JWT authentication and authorization for MCP access. The
current Python MCP server does not yet enforce JWT tokens, so expose this
container only on trusted networks or behind an authenticated reverse proxy until
the application-level JWT layer is implemented.
