# Docker Deployment

Haiun provides two standalone Docker Compose modes:

- **Simple mode** runs the application directly on port `8765`.
- **Production mode** publishes Nginx on port `80` and provides Grafana, Loki,
  Prometheus, and Alloy monitoring. Grafana is available only on
  `127.0.0.1:3000`.

Production mode is sized for a small server with 2 vCPUs and 2 GiB of RAM.
The stack does not terminate TLS; place an existing TLS proxy or load balancer
in front of Nginx.

## Prerequisites

- Docker Engine 28 or newer
- Docker Compose 2.40 or newer

Create the local environment file and protect it because it contains the
Grafana administrator password:

```bash
cp .env.docker.example .env
chmod 600 .env
```

`.env` is ignored by Git. Do not commit it.

## Optional build proxy

Docker builds use no proxy by default. The default values are:

```dotenv
HAIUN_BUILD_NETWORK=default
HAIUN_HTTP_PROXY=
HAIUN_HTTPS_PROXY=
HAIUN_NO_PROXY=localhost,127.0.0.1
```

To use a proxy running on the Docker host at port `7890`, set these values in
`.env`:

```dotenv
HAIUN_BUILD_NETWORK=host
HAIUN_HTTP_PROXY=http://127.0.0.1:7890
HAIUN_HTTPS_PROXY=http://127.0.0.1:7890
HAIUN_NO_PROXY=localhost,127.0.0.1
```

For a proxy reachable through the normal Docker build network, keep
`HAIUN_BUILD_NETWORK=default` and use the proxy's reachable hostname or IP.
Proxy values are passed as Docker's standard build proxy arguments and are not
stored as runtime environment variables in the Haiun image.

The Python package index is separately configurable:

```dotenv
HAIUN_PYPI_INDEX_URL=https://pypi.org/simple
```

The default is official PyPI. Change it only when your network requires a
different public package index.

## Application configuration

Create the normal Haiun configuration described in the main README and keep it
private on the host:

```bash
cp config/config.example.toml config/config.toml
chmod 600 config/config.toml
```

The file is mounted read-only and is never copied into the image. At container
startup, a small root bootstrap securely copies a regular `0600` configuration
file into container-private tmpfs, sets the copy to `10001:10001` and `0400`,
clears supplementary groups, and permanently drops to UID/GID `10001` before
starting Haiun. The host file is not modified.

## Simple mode

Start Haiun directly on port `8765`:

```bash
docker compose -f compose.simple.yml up -d --build
docker compose -f compose.simple.yml ps
curl http://127.0.0.1:8765/api/health
```

Override the host port with `HAIUN_SIMPLE_PORT` in `.env` if needed.

Stop the service without deleting application data:

```bash
docker compose -f compose.simple.yml down
```

## Production mode

### Grafana password

Set a strong password directly in `.env`. This command replaces the blank
example value without printing the generated password:

```bash
sed -i '/^GRAFANA_ADMIN_PASSWORD=/d' .env
printf 'GRAFANA_ADMIN_PASSWORD=%s\n' "$(openssl rand -base64 32)" >> .env
chmod 600 .env
```

The password is provided to Grafana as an environment variable, as requested.
Users with Docker daemon access can inspect container environments, so Docker
access must be treated as privileged administrator access.

### TLS proxy and trusted client addresses

Production Nginx binds host port `80`. Restrict that port with the server
firewall so only the existing TLS proxy or load balancer can connect. The
Docker stack does not issue certificates or terminate public TLS.

The default trusted-proxy configuration trusts only loopback and RFC1918
networks. If the TLS proxy connects from other documented source networks,
create an override:

```bash
cp deploy/nginx/trusted-proxies.default.conf config/trusted-proxies.conf
```

Edit the copied file to contain only the proxy's real source networks, then set:

```dotenv
HAIUN_TRUSTED_PROXIES_FILE=./config/trusted-proxies.conf
```

Never trust `0.0.0.0/0`; direct clients could otherwise spoof their source IP.

### Start and access the stack

```bash
docker compose -f compose.production.yml up -d --build
docker compose -f compose.production.yml ps
curl http://127.0.0.1/api/health
```

Only these host ports are published:

- Nginx: `80:80`
- Grafana: `127.0.0.1:3000:3000`

Access Grafana through an SSH tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 user@server
```

Open `http://127.0.0.1:3000`, sign in as `admin`, and use the password stored
in `.env`.

Stop production without deleting named volumes:

```bash
docker compose -f compose.production.yml down
```

## Monitoring

Grafana provisions three dashboards:

- **Haiun API Overview** — request rate, 5xx rate, p50/p95/p99 latency,
  in-progress requests, and busiest normalized routes.
- **Haiun Access Sources** — client IPs, referrer hosts, user agents, recent
  requests, slow requests, and failed requests.
- **Haiun Backend Runtime** — Python CPU, resident memory, garbage collection,
  uptime, Haiun scrape health, and monitoring-service scrape health.

API access records exclude request bodies, query strings, cookies,
authorization headers, and referrer paths/queries/fragments. No IP geolocation
is performed. Host-wide exporters, cAdvisor, and Alertmanager are not enabled.
Logs and metrics are retained for 30 days; Prometheus also has a `512 MB`
storage cap.

Useful diagnostics:

```bash
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=200 nginx haiun alloy loki prometheus grafana
docker stats --no-stream
docker compose -f compose.production.yml exec prometheus \
  wget -qO- http://127.0.0.1:9090/-/ready
docker compose -f compose.production.yml exec grafana \
  wget -qO- http://127.0.0.1:3000/api/health
```

## Resource limits

Production uses one Uvicorn worker and these memory limits:

| Service | Limit |
| --- | ---: |
| Haiun | 768 MiB |
| Grafana | 192 MiB |
| Loki | 192 MiB |
| Prometheus | 192 MiB |
| Alloy | 96 MiB |
| Nginx | 64 MiB |

This fits a lightly loaded 2 GiB server, but leaves limited headroom. A 2 GiB
swap file can provide emergency protection:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
swapon --show
```

Swap is not a substitute for CPU or RAM. Use at least 4 GiB RAM if analysis
concurrency, traffic, dashboard use, or retained data grows materially. Follow
your distribution's documentation before adding the swap file to `/etc/fstab`.

## Backup and restore

Stop production before backing up the application data volume. The command
securely replaces any existing archive and creates the new file with mode
`0600`:

```bash
docker compose -f compose.production.yml down
docker run --rm \
  -v haiun-data:/data:ro \
  -v "$PWD":/backup \
  alpine:3.22 \
  sh -c 'umask 077; rm -f /backup/haiun-data.tar.gz; tar -czf /backup/haiun-data.tar.gz -C /data .'
```

If `HAIUN_DATA_VOLUME` changes the volume name, use the configured name in the
backup and restore commands.

Restore into an empty named volume:

```bash
docker volume create haiun-data
docker run --rm \
  -v haiun-data:/data \
  -v "$PWD":/backup:ro \
  alpine:3.22 \
  tar -xzf /backup/haiun-data.tar.gz -C /data
```

## Upgrade

```bash
git pull --ff-only
docker compose -f compose.production.yml build --pull
docker compose -f compose.production.yml up -d
```

## Verification

Validate configuration without starting services:

```bash
docker compose -f compose.simple.yml config
GRAFANA_ADMIN_PASSWORD=configuration-check \
  docker compose -f compose.production.yml config
```

Run all image, configuration, and isolated smoke checks:

```bash
scripts/check_docker_deploy.sh all
```

The production smoke requires host ports `80` and `3000` to be free. It uses
isolated temporary configuration, passwords, network names, and volume names,
and removes them when complete.
