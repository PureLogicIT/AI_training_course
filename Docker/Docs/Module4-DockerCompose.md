# Module 4: Docker Compose
> Subject: Docker | Difficulty: Intermediate | Estimated Time: 240 minutes

## Objective

After completing this module, you will be able to explain what Docker Compose is and when to use it instead of raw `docker` CLI commands. You will write a complete `compose.yaml` file using all top-level elements (services, volumes, networks, configs, secrets), configure individual services with image or build context, port mappings, environment variables, env files, restart policies, and health checks. You will use `depends_on` with condition-based ordering so services start only when their dependencies are genuinely ready. You will manage the full Compose CLI — `up`, `down`, `ps`, `logs`, `exec`, `build`, `pull`, `restart`, and `scale` — and understand what each does at the container level. You will use Compose profiles to selectively activate services, Compose Watch (`develop.watch`) to enable live file-sync during development, and multiple compose files with `compose.override.yaml` and the `-f` flag to separate development and production configurations. You will also manage secrets and configs in Compose in a way that avoids embedding sensitive data in environment variables.

## Prerequisites

- Completed Module 1: Basics — comfortable with `docker run`, `docker ps`, `docker exec`, Dockerfile authoring, and the fundamentals of `compose.yaml`
- Completed Module 2: Volumes — familiar with named volumes, bind mounts, and how volume declarations work in `compose.yaml`
- Completed Module 3: Networking — familiar with user-defined bridge networks, DNS-based service discovery, and how networks are declared in `compose.yaml`
- Docker Engine 27 or later installed (verify with `docker --version`; current stable release is Docker Engine 29.3.1)
- A text editor and a terminal

## Key Concepts

### What Docker Compose Is and When to Use It

Docker Compose is a tool for defining and running multi-container Docker applications using a single declarative YAML file. Instead of constructing a long chain of `docker run` commands with manually coordinated volume mounts, port bindings, environment variables, and network flags, you describe your entire application stack once in `compose.yaml`, then start, stop, or rebuild the whole thing with one command.

The Docker Compose plugin (`docker compose`) is built into the Docker CLI. The legacy standalone binary (`docker-compose` v1) was deprecated in 2023 and is no longer maintained. All commands in this module use the plugin form: `docker compose <subcommand>`.

**Use Compose when:**
- Your application requires two or more containers that need to communicate (web server + database, API + cache + worker, etc.)
- You want to version-control the complete environment definition alongside your application code
- You want teammates to replicate your local environment by cloning the repository and running a single command
- You need repeatable, throw-away environments for integration tests in CI/CD

**Use raw `docker` CLI commands when:**
- You are running a single, standalone container with no dependencies
- You are doing quick exploration or debugging and do not need a persistent configuration
- You are writing low-level automation scripts that manipulate individual containers directly

### The `compose.yaml` File Structure

The Compose Specification defines a file format for describing multi-container applications. Docker Compose accepts `compose.yaml` (preferred), `compose.yml`, `docker-compose.yaml`, and `docker-compose.yml` (the last two for backward compatibility). Place the file at the root of your project directory.

The top-level sections are:

| Section | Purpose |
|---|---|
| `services` | Required. Defines each container that makes up the application. |
| `volumes` | Optional. Declares named volumes that services can mount. |
| `networks` | Optional. Declares custom networks for services to join. |
| `configs` | Optional. Declares non-sensitive configuration data to mount as files. |
| `secrets` | Optional. Declares sensitive data (passwords, tokens, keys) to mount securely. |

A fully annotated skeleton showing every top-level section:

```yaml
# compose.yaml

services:
  web:
    image: nginx:1.27-alpine
    ports:
      - "8080:80"

  api:
    build: ./api
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/appdb
    depends_on:
      db:
        condition: service_healthy
    networks:
      - backend

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: appdb
    volumes:
      - pg-data:/var/lib/postgresql/data
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

volumes:
  pg-data:

networks:
  backend:

configs:
  nginx_conf:
    file: ./nginx.conf

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

### Service Configuration

Each entry under `services` defines one logical container. The key options are:

#### `image` vs `build`

Use `image` to pull a pre-built image from a registry. Use `build` to build an image from a Dockerfile when `docker compose up` runs.

```yaml
services:
  cache:
    image: redis:7.4-alpine       # pull from Docker Hub

  api:
    build: ./api                  # build from ./api/Dockerfile

  worker:
    build:
      context: ./worker           # directory containing Dockerfile
      dockerfile: Dockerfile.prod # non-default Dockerfile name
      args:
        BUILD_ENV: production     # build arguments passed to ARG instructions
```

#### `ports`

Maps host ports to container ports. The short form is `"HOST:CONTAINER"`. Use quotes to prevent YAML from parsing port numbers as base-60 integers.

```yaml
ports:
  - "3000:3000"           # all host interfaces
  - "127.0.0.1:5432:5432" # bind only on localhost (recommended for databases)
  - "8080-8082:8080-8082" # port range
```

#### `environment` and `env_file`

`environment` sets environment variables directly in the compose file. Use the map form for readability:

```yaml
environment:
  NODE_ENV: production
  LOG_LEVEL: warn
  DATABASE_URL: postgresql://user:pass@db:5432/appdb
```

Or the list form (useful when values contain colons):

```yaml
environment:
  - NODE_ENV=production
  - DATABASE_URL=postgresql://user:pass@db:5432/appdb
```

`env_file` loads variables from one or more external files, keeping secrets out of `compose.yaml`:

```yaml
env_file:
  - .env              # always loaded
  - .env.local        # loaded only if it exists (use path: and required: false)
```

#### `depends_on` with Condition

The basic `depends_on: [db]` form only waits for the dependency container to start — it does not wait until the process inside the container is ready to accept connections. Use the long form with `condition` to express real readiness:

```yaml
depends_on:
  db:
    condition: service_healthy    # wait until healthcheck passes
  migrations:
    condition: service_completed_successfully  # wait until a one-shot job exits 0
  cache:
    condition: service_started    # only wait for container start (default)
```

The three condition values:

| Condition | What it waits for |
|---|---|
| `service_started` | The dependency container has started (default). Does not verify the process inside is ready. |
| `service_healthy` | The dependency's `healthcheck` has passed. The dependency must define a `healthcheck` block. |
| `service_completed_successfully` | The dependency container has exited with code 0. Use for one-off migration or seed scripts. |

#### `healthcheck`

Defines a command Compose runs inside the container to determine whether it is healthy. If the command exits with code 0, the container is healthy; any non-zero exit code is unhealthy.

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U myuser -d mydb"]
  interval: 10s       # how often to run the check
  timeout: 5s         # how long to wait for a response before declaring failure
  retries: 5          # consecutive failures before declaring unhealthy
  start_period: 30s   # grace period before failures count (container startup time)
  start_interval: 5s  # how often to check during the start_period (Docker 25+)
```

The `test` field accepts:
- `["CMD", "command", "arg1"]` — runs the command directly without a shell
- `["CMD-SHELL", "shell command"]` — runs via `/bin/sh -c`
- `["NONE"]` — disables a healthcheck inherited from the base image

#### `restart`

Governs what Docker does when a container exits:

| Policy | Behaviour |
|---|---|
| `no` | Never restart (default). |
| `always` | Always restart regardless of exit code. Restarts on daemon startup too. |
| `on-failure` | Restart only if the container exits with a non-zero code. |
| `on-failure:3` | Restart on failure, but no more than 3 times. |
| `unless-stopped` | Always restart unless explicitly stopped with `docker compose stop`. |

For production services, `unless-stopped` is usually the right choice. For development, `no` is fine. Never use `always` for a service that is expected to exit (like a one-shot migration).

### Volumes in Compose

Volumes declared under the top-level `volumes` key are named volumes managed by Docker. Services reference them by name:

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pg-data:/var/lib/postgresql/data   # named volume
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # bind mount

volumes:
  pg-data:                   # Docker-managed; Docker chooses the host path
```

To use an existing volume created outside Compose (for example, by another project), mark it as `external`:

```yaml
volumes:
  shared-logs:
    external: true
```

### Networks in Compose

When you do not declare any networks, Compose creates a single default network for the project and attaches all services to it. Services can reach each other by their service name. This default is sufficient for most applications. Define explicit networks when you need isolation — for example, a frontend network visible to a proxy and a backend network that the database must not be reachable from the proxy on.

```yaml
services:
  proxy:
    image: nginx:1.27-alpine
    networks:
      - frontend

  api:
    build: ./api
    networks:
      - frontend
      - backend

  db:
    image: postgres:16-alpine
    networks:
      - backend   # proxy cannot reach db directly

networks:
  frontend:
  backend:
```

To connect a service to a network created outside Compose, use `external: true`:

```yaml
networks:
  shared-infra:
    external: true
```

### Environment Variables and `.env` Files

Compose reads a `.env` file in the same directory as `compose.yaml` automatically. Variables defined there are available for **variable substitution** inside `compose.yaml`, not inside the container environment.

```
# .env
POSTGRES_VERSION=16-alpine
API_PORT=3000
```

```yaml
# compose.yaml — uses substitution syntax ${VARIABLE}
services:
  db:
    image: postgres:${POSTGRES_VERSION}
  api:
    ports:
      - "${API_PORT}:3000"
```

**Variable substitution vs container environment variables — these are different things:**

- Variables in `.env` feed into `compose.yaml` at parse time via `${VAR}` substitution.
- Variables under `environment:` or `env_file:` in a service definition are injected into the running container.

You can combine both: use `.env` for Compose-level configuration (image tags, ports) and `env_file: .env.app` for application-level settings injected into the container.

**Precedence** for variable substitution (highest to lowest):
1. Shell environment variables in the terminal where `docker compose` runs
2. Values set with `--env-file` flag on the CLI
3. Values from the `.env` file in the project directory
4. Defaults defined in `compose.yaml` with `${VAR:-default}`

### Compose Profiles

Profiles let you mark certain services as optional so they only start when explicitly requested. Core services have no profile and always start. Supporting services — a database admin UI, a mock email server, a profiling sidecar — are assigned one or more profile names.

```yaml
services:
  api:
    build: ./api              # no profile: always starts

  db:
    image: postgres:16-alpine # no profile: always starts

  pgadmin:
    image: dpage/pgadmin4:8
    profiles: [tools]         # only starts when the "tools" profile is active

  mailpit:
    image: axllent/mailpit:latest
    profiles: [tools]

  k6:
    image: grafana/k6:latest
    profiles: [perf]          # only starts when the "perf" profile is active
```

Activate profiles with `--profile` or the `COMPOSE_PROFILES` environment variable:

```bash
# Start core services + tools profile
docker compose --profile tools up -d

# Start core services + multiple profiles
docker compose --profile tools --profile perf up -d

# Using an environment variable
COMPOSE_PROFILES=tools docker compose up -d

# Start everything, including all profiles
docker compose --profile "*" up -d
```

Profile names must match the pattern `[a-zA-Z0-9][a-zA-Z0-9_.-]+`.

### Compose Watch for Live Development

Compose Watch eliminates the need for external file-watching tools during development. It monitors your source files for changes and automatically syncs them to running containers or triggers rebuilds — without stopping and restarting the entire stack.

Configure it under the `develop.watch` key of a service:

```yaml
services:
  api:
    build: ./api
    develop:
      watch:
        - path: ./api/src          # watch this directory on the host
          target: /app/src         # sync to this path in the container
          action: sync             # copy changed files without restarting

        - path: ./api/package.json # watch package.json
          action: rebuild          # rebuild the image if it changes

        - path: ./api/config
          target: /app/config
          action: sync+restart     # sync and then restart the container

        - path: ./api/src
          target: /app/src
          action: sync+exec        # sync and run a command (Docker Compose 2.32+)
          exec:
            command: ["node", "--run", "test:watch"]
          ignore:
            - "**/*.test.js"       # ignore test files from triggering this rule
```

The available actions:

| Action | Effect | Best for |
|---|---|---|
| `sync` | Copies changed files into the container without restarting. | Interpreted languages (Python, Node, Ruby) with a running file-watcher inside the container. |
| `rebuild` | Rebuilds the image and recreates the container. | Compiled languages or when dependencies change. |
| `restart` | Restarts the container without rebuilding (Compose 2.32+). | Config file changes that require a process restart. |
| `sync+restart` | Syncs files then restarts the container (Compose 2.23+). | Applications that must restart to pick up changes. |
| `sync+exec` | Syncs files then runs a command in the container (Compose 2.32+). | Running test suites or build steps inside a running container. |

Start Compose with watch mode enabled:

```bash
docker compose up --watch
```

Or start normally and enable watch separately:

```bash
docker compose up -d
docker compose watch
```

### Overriding with Multiple Compose Files

Compose supports layering multiple files on top of each other. This is the standard pattern for separating development-specific settings (bind mounts, debug ports, verbose logging) from the shared base configuration.

**Default behavior:** Compose automatically reads `compose.yaml` and `compose.override.yaml` if both files exist. `compose.override.yaml` is merged on top of `compose.yaml`.

**Explicit override with `-f`:**

```bash
# Development (uses compose.yaml + compose.override.yaml automatically)
docker compose up -d

# Production (explicit files; compose.override.yaml is not auto-applied)
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

**Merge behavior:**

- **Scalar values** (`image`, `command`, `restart`): the later file's value replaces the earlier one.
- **Lists** (`ports`, `dns`): entries are concatenated.
- **Maps** (`environment`, `labels`, `volumes`): keys are merged; a key in the later file overrides the same key in the earlier file.

**Example structure:**

```yaml
# compose.yaml — shared base configuration
services:
  api:
    build: ./api
    environment:
      NODE_ENV: production
      DATABASE_URL: postgresql://user:${DB_PASSWORD}@db:5432/appdb
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    volumes:
      - pg-data:/var/lib/postgresql/data

volumes:
  pg-data:
```

```yaml
# compose.override.yaml — development additions (auto-applied)
services:
  api:
    environment:
      NODE_ENV: development       # overrides the base value
      LOG_LEVEL: debug
    volumes:
      - ./api/src:/app/src        # bind-mount source for live editing
    ports:
      - "9229:9229"               # Node.js debug port

  db:
    ports:
      - "127.0.0.1:5432:5432"    # expose db locally for dev tools
```

```yaml
# compose.prod.yaml — production hardening
services:
  api:
    environment:
      NODE_ENV: production
      LOG_LEVEL: warn
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
```

### Secrets and Configs in Compose

#### Secrets

Secrets are for sensitive data: database passwords, API keys, TLS private keys. Compose mounts secrets into containers as read-only files under `/run/secrets/<secret_name>`. They are never baked into the image, never appear in `docker inspect` environment output, and are held in memory (not written to the container filesystem layer).

Declare secrets at the top level and grant them to services:

```yaml
services:
  api:
    image: myapp:1.0.0
    secrets:
      - db_password      # accessible at /run/secrets/db_password
      - api_key

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password  # convention used by official images
    secrets:
      - db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt   # contents of this file become the secret

  api_key:
    environment: API_KEY              # value of this host env var becomes the secret
```

Read the secret inside the container:

```bash
# The application reads /run/secrets/db_password at runtime
cat /run/secrets/db_password
```

Many official Docker images (PostgreSQL, MySQL, MariaDB) support the `_FILE` suffix convention: set `POSTGRES_PASSWORD_FILE=/run/secrets/db_password` and the image reads the password from the file automatically.

#### Configs

Configs are for non-sensitive configuration files (nginx.conf, application.properties, feature flags) that you want to inject into containers without baking them into the image. Unlike secrets, configs are not encrypted and may be inspected.

```yaml
services:
  proxy:
    image: nginx:1.27-alpine
    configs:
      - source: nginx_conf
        target: /etc/nginx/nginx.conf  # where to mount inside the container
        mode: 0440                     # file permissions (octal)

configs:
  nginx_conf:
    file: ./config/nginx.conf
```

### Compose CLI Reference

The full set of Compose CLI commands follows the pattern `docker compose [COMMAND] [OPTIONS] [SERVICE...]`. When no service name is given, the command applies to all services.

| Command | What it does |
|---|---|
| `docker compose up` | Creates networks and volumes, builds or pulls images, starts all services. |
| `docker compose up -d` | Same as above, but detached (returns the terminal). |
| `docker compose up --build` | Forces a rebuild of images before starting. |
| `docker compose up --watch` | Starts services and enables Compose Watch. |
| `docker compose down` | Stops and removes containers and networks. Volumes are preserved. |
| `docker compose down -v` | Also removes named volumes declared in `compose.yaml`. |
| `docker compose down --rmi all` | Also removes images built for services. |
| `docker compose ps` | Lists containers in the current project with status and ports. |
| `docker compose ps -a` | Lists all containers including stopped ones. |
| `docker compose logs` | Prints stdout/stderr from all services. |
| `docker compose logs -f` | Follows (tails) logs in real time. |
| `docker compose logs -f api` | Follows logs for the `api` service only. |
| `docker compose exec api /bin/sh` | Opens an interactive shell in a running `api` container. |
| `docker compose exec api env` | Prints environment variables in the running container. |
| `docker compose build` | Builds (or rebuilds) images for all services with a `build:` key. |
| `docker compose build api` | Builds only the `api` service image. |
| `docker compose pull` | Pulls the latest images for services that use `image:`. |
| `docker compose restart` | Restarts running containers without recreating them. |
| `docker compose stop` | Stops containers without removing them. |
| `docker compose start` | Starts stopped containers. |
| `docker compose run api pytest` | Runs a one-off command in a new container of the `api` service. |
| `docker compose up --scale worker=3` | Starts 3 instances of the `worker` service. |
| `docker compose config` | Validates and prints the resolved `compose.yaml` (with substitutions applied). |

**`exec` vs `run`:** `exec` connects to an already-running container; `run` creates a new container. Use `exec` to inspect or debug a live service; use `run` for one-off tasks like running migrations or a test suite.

### Production vs Development Compose Patterns

The key differences between a development and production Compose setup:

| Concern | Development | Production |
|---|---|---|
| Source code | Bind-mounted (`./src:/app/src`) for live editing | Code baked into the image; no bind mount |
| Build | `build: ./api` — image built from local source | Image pulled from a registry with a pinned digest or tag |
| Ports | Database ports exposed on `localhost` for tools | Database ports not exposed; accessed only through the application |
| Environment | Verbose logging, debug flags on | Reduced logging, no debug flags |
| Restart policy | `no` or omitted | `unless-stopped` |
| Resource limits | Omitted (use whatever is available) | `deploy.resources.limits` set to prevent runaway consumption |
| Secrets | `.env` file or plaintext in `compose.override.yaml` | Secrets from a vault, CI/CD injected, or `secrets:` with restricted files |
| Health checks | Optional | Required for every stateful service |

A minimal but complete production-ready stack example:

```yaml
# compose.prod.yaml
services:
  api:
    image: registry.example.com/myapp/api:1.4.2   # pinned tag from registry
    restart: unless-stopped
    environment:
      NODE_ENV: production
      LOG_LEVEL: warn
    secrets:
      - db_password
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 128M
    networks:
      - frontend
      - backend

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: appuser
      POSTGRES_DB: appdb
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - backend

  proxy:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    configs:
      - source: nginx_conf
        target: /etc/nginx/nginx.conf
    networks:
      - frontend

volumes:
  pg-data:

networks:
  frontend:
  backend:

secrets:
  db_password:
    file: /run/secrets/db_password   # injected by CI/CD or secrets manager

configs:
  nginx_conf:
    file: ./config/nginx.prod.conf
```

## Best Practices

1. **Always use `compose.yaml` (not `docker-compose.yml`) and commit it to version control alongside your application code.** The file is the authoritative description of your development environment. Every team member and CI job should be able to run `docker compose up -d` from a fresh clone and have a working stack.

2. **Use the long form of `depends_on` with `condition: service_healthy` for stateful dependencies like databases.** The short form `depends_on: [db]` only waits for the container process to start, not for PostgreSQL or MySQL to finish initializing. Without a health-check condition, your application container will almost certainly try to connect before the database is ready and crash.

3. **Never put plaintext secrets in `compose.yaml` or `.env` files that are committed to version control.** Use the `secrets:` top-level element with `file:` pointing to paths outside the repository, or inject secrets via CI/CD environment variables. Always add `.env`, `*.secret`, and `secrets/` to `.gitignore`.

4. **Separate development and production configuration using `compose.override.yaml` and `compose.prod.yaml` rather than a single file with environment-specific conditionals.** The base `compose.yaml` holds shared definitions. `compose.override.yaml` adds development conveniences (bind mounts, exposed ports, debug flags). `compose.prod.yaml` adds production hardening (resource limits, tighter restart policies, registry-pinned images). This keeps each file readable and independently reviewable.

5. **Use `env_file` to load application environment variables and `.env` substitution for Compose-level variables like image tags and port numbers.** Keeping the two uses of environment variables separate prevents confusion about which variables end up inside the container and which are consumed by the Compose parser.

6. **Set `restart: unless-stopped` on every long-running production service.** This ensures services recover automatically from crashes and restart after the host reboots. Avoid `restart: always` for one-shot containers (migrations, seed scripts) — it causes an infinite restart loop when the container exits with code 0.

7. **Use Compose profiles for optional services instead of commenting out blocks in `compose.yaml`.** Profiles provide a clean, version-controlled mechanism for enabling debugging tools, database admin UIs, or performance profiling services without modifying the compose file.

8. **Run `docker compose config` before committing a new `compose.yaml` to validate syntax and resolve variable substitutions.** This catches YAML mistakes, unset variables, and merge errors before they fail in CI.

9. **Use `docker compose down -v` only in development scripts where you explicitly want to destroy volumes.** In production, `docker compose down` preserves volumes by default — which is correct. Accidentally running `down -v` against a production database volume destroys all data.

10. **Pin image tags in production and use `docker compose pull` in your deployment pipeline to update them.** Never use `:latest` in `compose.yaml` for production services — you lose control of which version is running when Docker pulls a newer image on the next `up`.

## Use Cases

### Use Case 1: Full-Stack Application for Local Development

A development team builds a React SPA, a Node.js REST API, a PostgreSQL database, and a Redis cache. There are four developers, each on a different OS.

- **Problem:** Each developer has to manually start and configure four services in the correct order, with the correct environment variables and network connections. New team members take an hour to get started.
- **Concepts applied:** `compose.yaml` with `services`, `build`, `depends_on` with `service_healthy`, `healthcheck`, `networks`, `volumes`; Compose Watch with `sync` action for the API and React dev server; `compose.override.yaml` for bind mounts
- **Expected outcome:** Any developer runs `docker compose up --watch` to get the entire stack running. File changes in `./api/src` are synced live into the API container. The React dev server hot-reloads via its own internal watcher. A new developer can be productive within five minutes of cloning the repository.

### Use Case 2: CI/CD Integration Testing

A CI pipeline must start a PostgreSQL database, run database migrations, then run the full integration test suite against a live database — and clean up everything after the test run.

- **Problem:** Tests that hit a real database require the database to be fully initialized before the test runner starts. The CI server must not leak containers or volumes between test runs.
- **Concepts applied:** `depends_on` with `condition: service_completed_successfully` for the migration service; `condition: service_healthy` for the database; `docker compose run --rm` for the test runner; `docker compose down -v` for cleanup
- **Expected outcome:** The CI pipeline runs `docker compose -f compose.yaml -f compose.ci.yaml up -d`, waits for migrations to complete, runs tests with `docker compose run --rm api npm test`, then tears everything down with `docker compose down -v`. Each run starts from a clean state.

### Use Case 3: Selective Tooling for Developers

A backend service defines its core stack (API + database) and optional tooling (pgAdmin, Mailpit for email testing, Swagger UI). Most developers only need the core stack. A subset needs the tooling while debugging.

- **Problem:** The `compose.yaml` file has grown to include many optional services. Starting everything is slow and wastes resources. Commenting and uncommenting services to toggle them creates noisy diffs.
- **Concepts applied:** `profiles` assigned to optional services; `--profile tools` flag to opt in; `COMPOSE_PROFILES` environment variable for per-developer defaults
- **Expected outcome:** `docker compose up -d` starts only the API and database. `docker compose --profile tools up -d` adds the admin tools. Each developer sets `COMPOSE_PROFILES` in their shell profile if they want tools always on.

### Use Case 4: Production Deployment on a Single Host

A small SaaS product runs on a single cloud VM: an Nginx reverse proxy, a Node.js API (two replicas), and a PostgreSQL database. The database password must not appear in any file committed to source control.

- **Problem:** The production environment needs resource limits, restart policies, health checks, and a secure secret, none of which are appropriate in the development `compose.yaml`.
- **Concepts applied:** `compose.prod.yaml` as a production-only overlay; `secrets:` with file injected by the CI/CD system; `deploy.resources` for CPU and memory limits; `deploy.replicas` for two API instances; `restart: unless-stopped`; `healthcheck` on every service; `networks` to isolate the database from the proxy
- **Expected outcome:** Deployment is `docker compose -f compose.yaml -f compose.prod.yaml up -d`. The database password is read from `/run/secrets/db_password`, which is written by the CI/CD system before deployment and never appears in any repository file. The API scales to two replicas automatically.

## Hands-on Examples

### Example 1: Build and Run a Three-Tier Application Stack

You will write a `compose.yaml` for a Python Flask API, a PostgreSQL database, and a Redis cache. The database will have a health check and the API will wait for the database to be genuinely ready.

1. Create a project directory.

```bash
mkdir compose-three-tier
cd compose-three-tier
```

2. Create `app.py`.

```python
# app.py
import os
import psycopg2
import redis
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_URL = os.environ.get("DATABASE_URL", "postgresql://appuser:apppass@db:5432/appdb")
REDIS_HOST = os.environ.get("REDIS_HOST", "cache")

r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

def get_db_connection():
    return psycopg2.connect(DB_URL)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM visits;")
        db_count = cur.fetchone()[0]
        cur.close()
        conn.close()

        cache_count = r.incr("visits")

        body = f"DB visits: {db_count} | Cache visits: {cache_count}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

if __name__ == "__main__":
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS visits (id SERIAL PRIMARY KEY, ts TIMESTAMPTZ DEFAULT NOW());")
    conn.commit()
    cur.close()
    conn.close()
    print("Listening on port 5000")
    HTTPServer(("0.0.0.0", 5000), Handler).serve_forever()
```

3. Create `requirements.txt`.

```
psycopg2-binary==2.9.10
redis==5.2.1
```

4. Create `Dockerfile`.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5000
CMD ["python", "app.py"]
```

5. Create `compose.yaml`.

```yaml
services:
  api:
    build: .
    ports:
      - "5000:5000"
    environment:
      DATABASE_URL: postgresql://appuser:apppass@db:5432/appdb
      REDIS_HOST: cache
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started
    restart: on-failure
    networks:
      - app-net

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: apppass
      POSTGRES_DB: appdb
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - app-net

  cache:
    image: redis:7.4-alpine
    networks:
      - app-net

volumes:
  pg-data:

networks:
  app-net:
```

6. Start the stack.

```bash
docker compose up -d
```

Expected output:
```
[+] Running 5/5
 ✔ Network compose-three-tier_app-net    Created
 ✔ Volume "compose-three-tier_pg-data"   Created
 ✔ Container compose-three-tier-db-1     Healthy
 ✔ Container compose-three-tier-cache-1  Started
 ✔ Container compose-three-tier-api-1    Started
```

Note that the `api` container starts only after `db` reports `Healthy`, not just `Started`. This is the `condition: service_healthy` guarantee.

7. Verify the services are running.

```bash
docker compose ps
```

Expected output:
```
NAME                          IMAGE                        COMMAND                  SERVICE   STATUS    PORTS
compose-three-tier-api-1      compose-three-tier-api       "python app.py"          api       running   0.0.0.0:5000->5000/tcp
compose-three-tier-cache-1    redis:7.4-alpine             "docker-entrypoint.s…"   cache     running   6379/tcp
compose-three-tier-db-1       postgres:16-alpine           "docker-entrypoint.s…"   db        running   5432/tcp
```

8. Test the application.

```bash
curl http://localhost:5000
curl http://localhost:5000
curl http://localhost:5000
```

Expected output:
```
DB visits: 0 | Cache visits: 1
DB visits: 0 | Cache visits: 2
DB visits: 0 | Cache visits: 3
```

9. View logs from all services.

```bash
docker compose logs -f
```

Press `Ctrl+C` to stop following logs.

10. Open a shell inside the API container to inspect the environment.

```bash
docker compose exec api /bin/sh
```

Inside the container, run:

```bash
env | grep DATABASE
```

Expected output:
```
DATABASE_URL=postgresql://appuser:apppass@db:5432/appdb
```

Type `exit` to leave the container.

11. Tear down the stack, preserving the database volume.

```bash
docker compose down
```

12. Tear down the stack and delete all volumes.

```bash
docker compose down -v
```

---

### Example 2: Development vs Production Configuration with Compose Override

You will take the stack from Example 1 and add a `compose.override.yaml` for development (bind-mount source code, expose the database port) and a `compose.prod.yaml` for production (resource limits, no exposed database port).

1. Still inside the `compose-three-tier` directory from Example 1.

2. Create `compose.override.yaml`.

```yaml
# compose.override.yaml — applied automatically in development
services:
  api:
    volumes:
      - ./app.py:/app/app.py  # bind-mount source for live development
    environment:
      LOG_LEVEL: debug

  db:
    ports:
      - "127.0.0.1:5432:5432"  # expose to localhost for DB tools like pgAdmin
```

3. Create `compose.prod.yaml`.

```yaml
# compose.prod.yaml — apply explicitly in production
services:
  api:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 256M
        reservations:
          cpus: '0.10'
          memory: 64M

  db:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
```

4. Verify that the development configuration (auto-merged) is what you expect.

```bash
docker compose config
```

The output shows the fully resolved YAML with `compose.override.yaml` merged in. Confirm that the `db` service has `ports: ["127.0.0.1:5432:5432"]` (from the override) and the `api` service has the bind-mount volume.

5. Simulate how you would deploy to production.

```bash
docker compose -f compose.yaml -f compose.prod.yaml config
```

Confirm that the production config has `deploy.resources` limits on both `api` and `db`, and that the `db` service does **not** have the `127.0.0.1:5432` port mapping from the override.

6. Start the production-simulated stack.

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

7. Tear it down.

```bash
docker compose -f compose.yaml -f compose.prod.yaml down -v
```

---

### Example 3: Profiles for Optional Developer Tooling

You will extend the stack with two optional services — pgAdmin for database administration and Mailpit as a local SMTP server — gated behind a `tools` profile.

1. Add these services to `compose.yaml` (append below the `cache` service definition).

```yaml
  pgadmin:
    image: dpage/pgadmin4:8
    profiles: [tools]
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@local.dev
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    networks:
      - app-net

  mailpit:
    image: axllent/mailpit:latest
    profiles: [tools]
    ports:
      - "8025:8025"   # web UI
      - "1025:1025"   # SMTP
    networks:
      - app-net
```

2. Start only the core services (no tools).

```bash
docker compose up -d
```

Confirm that `pgadmin` and `mailpit` are not listed in `docker compose ps`.

3. Start the stack including the `tools` profile.

```bash
docker compose --profile tools up -d
```

Expected output includes:
```
 ✔ Container compose-three-tier-pgadmin-1  Started
 ✔ Container compose-three-tier-mailpit-1  Started
```

4. Open `http://localhost:5050` in a browser to confirm pgAdmin is running.

5. Stop all services including the profile services, using the same `--profile` flag.

```bash
docker compose --profile tools down
```

---

### Example 4: Compose Watch for Live Development

You will configure Compose Watch on the API service so that changes to `app.py` are synced into the running container automatically, and changes to `requirements.txt` trigger a full image rebuild.

1. Add a `develop` section to the `api` service in `compose.yaml`.

```yaml
  api:
    build: .
    ports:
      - "5000:5000"
    environment:
      DATABASE_URL: postgresql://appuser:apppass@db:5432/appdb
      REDIS_HOST: cache
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started
    restart: on-failure
    networks:
      - app-net
    develop:
      watch:
        - path: ./app.py
          target: /app/app.py
          action: sync+restart    # sync the file then restart the container

        - path: ./requirements.txt
          action: rebuild         # rebuild the image when dependencies change
```

2. Start the stack in watch mode.

```bash
docker compose up --watch
```

Expected output:
```
[+] Running 3/3
 ✔ Container compose-three-tier-db-1     Healthy
 ✔ Container compose-three-tier-cache-1  Started
 ✔ Container compose-three-tier-api-1    Started
Watch enabled
```

3. In a second terminal, confirm the app responds.

```bash
curl http://localhost:5000
```

4. Edit `app.py` — change the response format to include a timestamp. For example, change the body line to:

```python
        body = f"[UPDATED] DB visits: {db_count} | Cache visits: {cache_count}\n".encode()
```

5. Save the file. Within a few seconds, Compose Watch will detect the change, sync the file, and restart the API container. You will see output like:

```
Syncing "app.py" to "compose-three-tier-api-1:/app/app.py"
Restarting "compose-three-tier-api-1" after changes were detected
```

6. Confirm the change is live without a full rebuild.

```bash
curl http://localhost:5000
```

Expected output (reflects the edit):
```
[UPDATED] DB visits: 0 | Cache visits: 1
```

7. Press `Ctrl+C` to stop watch mode, then tear down.

```bash
docker compose down -v
```

---

### Example 5: Secrets in Compose

You will use the `secrets` top-level element to pass the database password securely, removing it from plaintext environment variables.

1. Create a `secrets/` directory and write the password to a file.

```bash
mkdir secrets
echo "supersecretpassword" > secrets/db_password.txt
```

2. Add `secrets/` to `.gitignore`.

```bash
echo "secrets/" >> .gitignore
```

3. Update `compose.yaml` to declare the secret and remove the plaintext password.

```yaml
services:
  api:
    build: .
    ports:
      - "5000:5000"
    environment:
      DATABASE_URL: postgresql://appuser@db:5432/appdb
      REDIS_HOST: cache
    secrets:
      - db_password
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started
    restart: on-failure
    networks:
      - app-net

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: appuser
      POSTGRES_DB: appdb
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - app-net

  cache:
    image: redis:7.4-alpine
    networks:
      - app-net

volumes:
  pg-data:

networks:
  app-net:

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

4. Update `app.py` to read the password from the secret file.

```python
# app.py — updated DB connection to read secret from file
import os
import psycopg2
import redis
from http.server import HTTPServer, BaseHTTPRequestHandler

def build_db_url():
    secret_path = "/run/secrets/db_password"
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            password = f.read().strip()
    else:
        password = os.environ.get("DB_PASSWORD", "")
    user = "appuser"
    host = "db"
    dbname = "appdb"
    return f"postgresql://{user}:{password}@{host}:5432/{dbname}"

REDIS_HOST = os.environ.get("REDIS_HOST", "cache")
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        conn = psycopg2.connect(build_db_url())
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM visits;")
        db_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        cache_count = r.incr("visits")
        body = f"DB visits: {db_count} | Cache visits: {cache_count}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

if __name__ == "__main__":
    conn = psycopg2.connect(build_db_url())
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS visits (id SERIAL PRIMARY KEY, ts TIMESTAMPTZ DEFAULT NOW());")
    conn.commit()
    cur.close()
    conn.close()
    print("Listening on port 5000")
    HTTPServer(("0.0.0.0", 5000), Handler).serve_forever()
```

5. Build and start the stack.

```bash
docker compose up -d --build
```

6. Confirm the secret is mounted inside the `db` container but the plaintext password is not in the environment.

```bash
docker compose exec db cat /run/secrets/db_password
```

Expected output:
```
supersecretpassword
```

```bash
docker compose exec db env | grep POSTGRES_PASSWORD
```

Expected output:
```
POSTGRES_PASSWORD_FILE=/run/secrets/db_password
```

The plaintext password does not appear in the environment — only the file path does.

7. Confirm the application still works.

```bash
curl http://localhost:5000
```

Expected output:
```
DB visits: 0 | Cache visits: 1
```

8. Tear down.

```bash
docker compose down -v
```

## Common Pitfalls

### Pitfall 1: Using `depends_on` Without a Health Check Condition

**Description:** `depends_on: [db]` only waits for the database container to start, not for PostgreSQL (or MySQL) to finish initializing and be ready to accept connections. The application container starts, immediately tries to connect, fails, and crashes.

**Why it happens:** The short form of `depends_on` is easy to write and gives false confidence. The message "db started" does not mean "db is accepting connections."

**Incorrect pattern:**
```yaml
services:
  api:
    depends_on:
      - db  # only waits for container start

  db:
    image: postgres:16-alpine
    # no healthcheck defined
```

**Correct pattern:**
```yaml
services:
  api:
    depends_on:
      db:
        condition: service_healthy  # waits until healthcheck passes

  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

---

### Pitfall 2: Putting Secrets in Environment Variables Inside `compose.yaml`

**Description:** Hardcoding passwords, API keys, or tokens in the `environment:` block of `compose.yaml` and committing that file to source control exposes the secret to everyone with repository access — and to anyone who can run `docker inspect` on a running container.

**Why it happens:** Environment variables are the simplest way to configure a container and the default example in most tutorials.

**Incorrect pattern:**
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: myrealpassword  # visible in git history forever
```

**Correct pattern:**
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt  # kept in .gitignore
```

---

### Pitfall 3: Running `docker compose down -v` in Production

**Description:** `docker compose down -v` removes all named volumes declared in `compose.yaml` — including database volumes. Running this against a production database destroys all data irreversibly.

**Why it happens:** Developers use `down -v` routinely in development to get a clean state. The flag is easy to type by habit, and the damage is silent until the next `docker compose up` reveals an empty database.

**Incorrect pattern:**
```bash
# This is common and correct in development:
docker compose down -v

# This is catastrophic in production:
ssh prod-server "cd /app && docker compose down -v"
```

**Correct pattern:**
```bash
# In production: preserve volumes, only remove containers and networks
docker compose down

# If you genuinely need to remove a specific volume in production:
docker volume rm myapp_pg-data  # deliberate, explicit, hard to type by mistake
```

---

### Pitfall 4: Using `:latest` for Service Images

**Description:** Using `image: myapp:latest` in `compose.yaml` means every `docker compose pull` fetches whatever the registry currently tags as `latest`. Between two deployments, the behavior of your application can silently change because a new image was pushed.

**Why it happens:** `:latest` is the default tag and requires no thought about versioning.

**Incorrect pattern:**
```yaml
services:
  api:
    image: registry.example.com/myapp/api:latest
```

**Correct pattern:**
```yaml
services:
  api:
    image: registry.example.com/myapp/api:1.4.2
```

---

### Pitfall 5: Forgetting That `compose.override.yaml` Is Applied Automatically

**Description:** A developer adds a bind mount, a debug port, or a plaintext secret to `compose.override.yaml` for local development. They then run a production deployment on a remote server that also has `compose.override.yaml` present. The override is silently applied, and the production container gets a bind mount that points to a path that does not exist on the server — causing the container to fail or, worse, to mount an unexpected path.

**Why it happens:** The automatic merging of `compose.override.yaml` is a convenience feature for local development that becomes a hazard in automated deployment if the file is accidentally present.

**Correct pattern:**
- Add `compose.override.yaml` to `.gitignore` so it is never committed or present on remote servers.
- Use explicit `-f` flags for production deployments: `docker compose -f compose.yaml -f compose.prod.yaml up -d`
- Alternatively, document that `compose.override.yaml` is a developer-local file and ensure deployment scripts always use explicit file lists.

---

### Pitfall 6: Scaling a Service That Binds a Fixed Host Port

**Description:** Running `docker compose up --scale api=3` fails with a port conflict if the `api` service has a fixed `ports` mapping like `"3000:3000"`. Three containers cannot all bind to the same host port.

**Why it happens:** Fixed host port bindings are convenient for development but incompatible with scaling.

**Incorrect pattern:**
```yaml
services:
  api:
    ports:
      - "3000:3000"  # cannot scale beyond 1
```

**Correct pattern for scaling:**
```yaml
services:
  api:
    ports:
      - "3000"        # expose container port 3000; Docker assigns random host ports
  proxy:
    image: nginx:1.27-alpine
    ports:
      - "3000:80"    # the proxy has the fixed host port and load-balances to api instances
```

---

### Pitfall 7: Confusing `docker compose restart` with `docker compose up`

**Description:** `docker compose restart` restarts running or stopped containers but does **not** recreate them, rebuild images, or apply configuration changes from an updated `compose.yaml`. After editing `compose.yaml`, developers run `restart` expecting the new configuration to apply, and it does not.

**Why it happens:** `restart` sounds like the logical command for applying changes, but Compose does not re-read the compose file during a restart — only during `up`.

**Incorrect pattern (after changing compose.yaml):**
```bash
docker compose restart    # containers restart but compose.yaml changes are ignored
```

**Correct pattern:**
```bash
docker compose up -d      # detects changes, recreates affected containers
docker compose up -d --build  # also rebuilds images before recreating
```

## Summary

- Docker Compose replaces a sequence of manual `docker run` commands with a single `compose.yaml` file that describes every service, network, volume, secret, and config in your application. One `docker compose up -d` creates and starts the entire stack; one `docker compose down` tears it down cleanly.
- The `compose.yaml` file has five top-level sections: `services` (required), `volumes`, `networks`, `configs`, and `secrets`. Services inherit networking DNS automatically — every service can reach others by their service name within the same project network.
- Use `depends_on` with `condition: service_healthy` and a `healthcheck` block on stateful services to ensure containers start only after their dependencies are genuinely ready, not merely started.
- Separate development from production using `compose.override.yaml` (applied automatically) for development additions and `compose.prod.yaml` (applied with explicit `-f` flags) for production hardening including resource limits, restart policies, and registry-pinned images.
- Use the `secrets:` top-level element to mount sensitive data as read-only files at `/run/secrets/<name>` rather than exposing passwords in environment variables, which appear in `docker inspect` output and version-controlled files.
- Compose profiles let you keep optional services (admin UIs, mocking tools, profilers) defined in the same `compose.yaml` without starting them by default. Compose Watch (`develop.watch`) syncs changed source files into running containers or triggers rebuilds automatically, making the development loop significantly faster.

## Further Reading

- [Docker Compose Overview — Official Docs](https://docs.docker.com/compose/) — The entry point to all Compose documentation, with links to quickstarts, how-to guides, and the full reference; the best bookmark for finding any Compose topic quickly.
- [Compose File Reference — Official Docs](https://docs.docker.com/reference/compose-file/) — The authoritative specification for every top-level element and service attribute in `compose.yaml`, including all configuration options, data types, and default values.
- [How Compose Works: The Application Model — Official Docs](https://docs.docker.com/compose/intro/compose-application-model/) — Explains the Compose project model, how services, networks, volumes, configs, and secrets relate to each other, and how Compose treats a project as a unit.
- [Control Startup and Shutdown Order in Compose — Official Docs](https://docs.docker.com/compose/how-tos/startup-order/) — Detailed guidance on `depends_on` conditions, health check configuration, and the correct patterns for ensuring services start in the right order.
- [Use Compose Watch — Official Docs](https://docs.docker.com/compose/how-tos/file-watch/) — Full documentation for the `develop.watch` specification, all available actions (`sync`, `rebuild`, `restart`, `sync+restart`, `sync+exec`), the `ignore` and `include` filter patterns, and how to run watch mode.
- [Manage Secrets in Compose — Official Docs](https://docs.docker.com/compose/how-tos/use-secrets/) — Step-by-step guide to declaring, granting, and consuming secrets in Compose services, with an explanation of why `environment:` is the wrong mechanism for sensitive data.
- [Use Compose in Production — Official Docs](https://docs.docker.com/compose/how-tos/production/) — Official guidance on adapting a Compose file for production deployment: removing bind mounts, adjusting restart policies, deploying updates with `--no-deps`, and using remote Docker hosts.
- [Compose Deploy Specification — Official Docs](https://docs.docker.com/reference/compose-file/deploy/) — The complete reference for the `deploy:` block including `replicas`, `resources` (limits and reservations), `restart_policy`, and `update_config` for rolling deployments.
- [Use Compose Profiles — Official Docs](https://docs.docker.com/compose/how-tos/profiles/) — Full documentation on defining profiles, activating them via CLI or environment variable, and the behavior of `depends_on` across profile boundaries.
- [Merge Multiple Compose Files — Official Docs](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) — Explains the exact merge semantics for scalars, lists, and maps when combining `compose.yaml` with override files using `-f`, enabling reliable dev/prod configuration splitting.
