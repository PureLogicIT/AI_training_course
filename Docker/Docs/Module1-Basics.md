# Module 1: Basics
> Subject: Docker | Difficulty: Beginner | Estimated Time: 105 minutes

## Objective

After completing this module, you will be able to explain what Docker is and how its client-server architecture works, distinguish between images and containers, create and manage containers using the core CLI commands (`docker pull`, `docker run`, `docker ps`, `docker stop`, `docker rm`, `docker rmi`), write a functional Dockerfile using the most common instructions (`FROM`, `RUN`, `COPY`, `WORKDIR`, `EXPOSE`, `CMD`), mount volumes to persist container data, connect containers using Docker networks, and define a multi-container application with a basic `compose.yaml` file.

## Prerequisites

- A computer with Docker Engine 27 or later installed, or Docker Desktop (verify with `docker --version`; current stable release is Docker Engine 29.3.1)
- Basic familiarity with the command line (navigating directories, editing text files)
- No prior Docker or containerization knowledge is assumed
- Understanding of what a web server or database is at a conceptual level is helpful but not required

## Key Concepts

### What Docker Is and Why It Exists

Docker is an open platform for developing, shipping, and running applications in isolated environments called containers. Before containers, developers frequently encountered the problem of software working on their machine but failing in production — because the production server had a different OS version, a different version of Node.js or Python, or different system libraries installed. Docker solves this by bundling an application together with everything it needs to run: the runtime, system libraries, configuration files, and code. That bundle travels as a single artifact from a developer's laptop to a CI server to production, and it behaves identically everywhere.

Docker is not a virtual machine. A virtual machine (VM) emulates a complete hardware stack and runs a full guest operating system, which takes gigabytes of disk space and seconds to minutes to start. A Docker container shares the host operating system's kernel and isolates only the user-space processes and filesystem. This makes containers much smaller (often tens of megabytes) and dramatically faster to start (typically under one second).

```
Virtual Machine Stack          Docker Container Stack
─────────────────────          ──────────────────────
  App A   |  App B               App A    |  App B
  Bins/Libs  Bins/Libs           Bins/Libs  Bins/Libs
  Guest OS   Guest OS            ─────────────────────
  Hypervisor                     Docker Engine
  Host OS                        Host OS
  Hardware                       Hardware
```

Docker operates on a client-server architecture. The **Docker client** (`docker`) is the command-line interface you interact with. It sends commands to the **Docker daemon** (`dockerd`), a background service that does the actual work of building, running, and managing containers. The client and daemon communicate via a REST API over a UNIX socket or over a network interface. The **Docker registry** (Docker Hub by default) is a remote store from which the daemon pulls and to which it pushes images.

### Images: Read-Only Blueprints

A Docker image is a read-only template that contains the complete filesystem and configuration needed to create a container. Think of it as the blueprint or mold from which containers are stamped out. An image includes the base operating system layer, installed packages, application code, environment variables, and the default command to run when the container starts.

Images are composed of layers. Each instruction in a Dockerfile creates a new layer on top of the previous one. Layers are cached and shared between images — if two images share the same base `FROM ubuntu:24.04` layer, Docker stores that layer only once on disk. This layered design makes images fast to build, fast to pull, and storage-efficient.

Images are named using the format `repository:tag`. The tag identifies a specific version. If you omit the tag, Docker defaults to `latest`, which is a mutable label that can point to different image versions over time — a common source of inconsistency.

```
ubuntu:24.04              # Official Ubuntu image, tag 24.04
nginx:1.27-alpine         # Nginx on Alpine Linux, pinned to 1.27
python:3.12-slim          # Slim Python 3.12 image
myapp:1.0.0               # A custom image you built, tagged 1.0.0
```

### Containers: Running Instances of Images

A container is a runnable instance of an image. When Docker starts a container, it takes the image's read-only layers and adds a thin, writable layer on top. All changes the running process makes — writing files, creating directories, modifying configuration — go into that writable layer. The underlying image layers are never modified. This means you can run many containers from the same image simultaneously, and each one gets its own isolated writable layer.

Containers are isolated from each other and from the host by default. Each container has its own process namespace (it cannot see the host's processes), its own network interfaces, and its own filesystem view. They are not permanent: stopping and removing a container discards its writable layer. Any data that must survive a container's deletion must be stored in a volume (covered below).

```bash
# Run the official Nginx web server as a container
docker run --name my-nginx -d -p 8080:80 nginx:1.27-alpine

# The container is now running in the background
# Visiting http://localhost:8080 serves the Nginx welcome page
```

A container can be in several states: `created`, `running`, `paused`, `restarting`, `exited`, or `dead`. The `docker ps` command shows running containers; `docker ps -a` shows all containers regardless of state.

### Volumes: Persistent Data Storage

By default, data written inside a container is lost when the container is removed. Volumes are the mechanism Docker provides to persist data independently of the container lifecycle. A volume is a directory managed by Docker that lives on the host filesystem outside the container's writable layer. When a container writes to a volume-mounted path, the data goes into the volume, not the container layer, and it survives the container being stopped, restarted, or deleted.

There are two primary ways to mount persistent data into a container:

- **Named volumes**: Created and managed by Docker. Docker chooses the storage location on the host. Named volumes are the recommended approach for most use cases because they are portable, easy to back up, and work identically across Linux, macOS, and Windows.
- **Bind mounts**: Mount a specific directory or file from the host filesystem into the container. Useful for development workflows where you want live code changes inside the container without rebuilding the image.

```bash
# Create a named volume
docker volume create my-data

# Run a container with the named volume mounted at /app/data
docker run -d --name app-server -v my-data:/app/data myapp:1.0.0

# Run a container with a bind mount (host path -> container path)
docker run -d --name dev-server -v /home/user/src:/app/src myapp:1.0.0

# List all volumes
docker volume ls

# Remove a volume (only if no container is using it)
docker volume rm my-data
```

The `--mount` flag is the more explicit, modern alternative to `-v`:

```bash
docker run -d --name app-server \
  --mount type=volume,src=my-data,dst=/app/data \
  myapp:1.0.0
```

### Networks: Container Communication

Docker provides a networking layer that allows containers to communicate with each other, with the host, or with the outside world. Every container is automatically connected to a default network, but for production use you should define your own.

Docker supports several network drivers:

- **bridge** (default): Creates an isolated private network on the host. Containers on the same bridge network can communicate with each other. The default bridge network requires containers to reference each other by IP address. User-defined bridge networks — which you create yourself — allow containers to communicate by container name, which is far more practical.
- **host**: Removes the network isolation between the container and the host. The container shares the host's network stack directly. Useful for performance-sensitive applications but reduces isolation.
- **none**: Completely disables networking for the container. Used when network access is not needed.

```bash
# Create a user-defined bridge network
docker network create my-app-network

# Run a container attached to the network
docker run -d --name db --network my-app-network postgres:16-alpine

# Run another container on the same network; it can reach db by name
docker run -d --name api --network my-app-network -p 3000:3000 myapi:1.0.0

# List all networks
docker network ls

# Inspect a network to see which containers are connected
docker network inspect my-app-network
```

### Core CLI Commands

The Docker CLI follows the pattern `docker [MANAGEMENT COMMAND] [SUBCOMMAND] [OPTIONS]` but also supports older shorthand forms like `docker run` and `docker ps`. The commands most used day-to-day are:

| Command | What It Does |
|---|---|
| `docker pull <image>` | Download an image from a registry |
| `docker run [OPTIONS] <image>` | Create and start a container from an image |
| `docker ps` | List running containers |
| `docker ps -a` | List all containers (running and stopped) |
| `docker stop <container>` | Gracefully stop a running container (SIGTERM, then SIGKILL after timeout) |
| `docker rm <container>` | Remove a stopped container |
| `docker images` | List locally available images |
| `docker rmi <image>` | Remove a local image |
| `docker exec -it <container> <cmd>` | Run a command inside a running container |
| `docker logs <container>` | View stdout/stderr output from a container |
| `docker build -t <name>:<tag> .` | Build an image from a Dockerfile in the current directory |

```bash
# Pull an image without running it
docker pull redis:7.4-alpine

# Run an interactive Ubuntu shell (removed on exit with --rm)
docker run --rm -it ubuntu:24.04 /bin/bash

# Run Nginx detached, named, with host port 8080 mapped to container port 80
docker run -d --name web -p 8080:80 nginx:1.27-alpine

# Check what is running
docker ps

# Stop the container gracefully
docker stop web

# Remove the stopped container
docker rm web

# Remove an image from local storage
docker rmi nginx:1.27-alpine
```

### Dockerfile: Building Your Own Images

A Dockerfile is a plain text file containing a sequence of instructions that Docker executes in order to build a custom image. Each instruction creates a new image layer. The file is typically named `Dockerfile` (no extension) and lives at the root of your project directory.

The most important instructions:

- **`FROM`**: Every Dockerfile starts here. Declares the base image to build upon.
- **`WORKDIR`**: Sets the working directory for all subsequent `RUN`, `COPY`, `ADD`, `CMD`, and `ENTRYPOINT` instructions. Creates the directory if it does not exist.
- **`COPY`**: Copies files and directories from the build context (your project directory) into the image.
- **`RUN`**: Executes a shell command during the build and commits the result as a new layer. Used to install packages, compile code, and set up the environment.
- **`EXPOSE`**: Documents which port the container's application listens on. Does not actually publish the port — that happens at runtime with `-p`.
- **`ENV`**: Sets environment variables that are available both during the build and at container runtime.
- **`CMD`**: The default command to run when a container starts. Only the last `CMD` instruction takes effect. Can be overridden at runtime.
- **`ENTRYPOINT`**: Like `CMD`, but harder to override. Used when the container should always run a specific executable.
- **`USER`**: Sets which user the subsequent instructions and the container runtime will run as. Use this to avoid running as root.

A complete example for a Node.js application:

```dockerfile
# Use an official Node.js 22 slim image as the base
FROM node:22-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependency manifests first to exploit layer caching
COPY package.json package-lock.json ./

# Install dependencies (this layer is cached unless package files change)
RUN npm ci --omit=dev

# Copy the application source code
COPY src/ ./src/

# Document that the app listens on port 3000
EXPOSE 3000

# Create a non-root user and switch to it before running
RUN useradd --create-home appuser
USER appuser

# Default command to start the application
CMD ["node", "src/index.js"]
```

Build the image from the directory containing the Dockerfile:

```bash
docker build -t my-node-app:1.0.0 .
```

### Docker Compose: Defining Multi-Container Applications

Most real applications consist of multiple services: a web server, a database, a cache, a background worker. Running each manually with `docker run` is tedious and error-prone. Docker Compose solves this by letting you define all services, their configurations, volumes, and networks in a single YAML file called `compose.yaml` (older projects may use `docker-compose.yml`).

Docker Compose is now a plugin integrated into the Docker CLI (`docker compose`) rather than a separate binary. The `docker-compose` standalone binary (v1) is no longer maintained.

A basic `compose.yaml` for a web application with a PostgreSQL database:

```yaml
services:
  web:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/appdb
    depends_on:
      - db
    networks:
      - app-network

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=appdb
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - app-network

volumes:
  postgres-data:

networks:
  app-network:
```

Key Compose CLI commands:

```bash
# Start all services (build images if needed), detached
docker compose up -d

# Stop and remove containers, networks (volumes are preserved by default)
docker compose down

# View running service status
docker compose ps

# Tail logs for all services
docker compose logs -f

# Rebuild images and recreate containers
docker compose up -d --build

# Run a one-off command in a service container
docker compose exec web /bin/bash
```

## Best Practices

1. **Always pin base image versions with a specific tag, never rely on `:latest`.** The `latest` tag is reassigned every time a new version is published; builds that used `python:latest` today may use a different Python version tomorrow, silently breaking your application.

2. **Order Dockerfile instructions from least-frequently-changed to most-frequently-changed.** Docker caches each layer; if a layer has not changed, Docker reuses it from cache. Placing `COPY package.json` and `RUN npm ci` before `COPY src/` means dependency installation is only re-run when `package.json` changes, not every time you edit source code.

3. **Combine related `RUN` commands into a single instruction using `&&`.** Each `RUN` creates a layer; multiple separate `RUN apt-get install` calls bloat the image and can cause stale cache bugs. Chain update and install together: `RUN apt-get update && apt-get install -y --no-install-recommends package && rm -rf /var/lib/apt/lists/*`.

4. **Always create and use a `.dockerignore` file.** Without it, the entire build context — including `node_modules/`, `.git/`, log files, and local secrets — is sent to the Docker daemon on every build, inflating build times and risking leaking sensitive files into the image.

5. **Never run application processes as root inside a container.** The default container user is root; if an attacker exploits a vulnerability in your application, they gain root access to the container, which significantly increases risk. Add a `USER` instruction to your Dockerfile to drop privileges before the final `CMD`.

6. **Use named volumes for persistent data instead of writing to the container's writable layer.** Data in the writable layer is destroyed when the container is removed; named volumes persist independently and are easily backed up with `docker volume inspect` and standard copy tools.

7. **Use user-defined bridge networks instead of the default bridge network for container-to-container communication.** On user-defined networks, containers can address each other by service name rather than by IP address, which changes on every container restart.

8. **Use `docker compose down` rather than `docker stop` + `docker rm` for Compose-managed applications.** `docker compose down` tears down containers, networks, and can optionally remove volumes in a single, consistent operation aligned with how the services were defined.

9. **Keep images small by using slim or Alpine base images and removing package manager caches in the same `RUN` layer where they were created.** Smaller images pull faster in CI/CD, use less disk space, and have a smaller attack surface.

10. **Validate your Dockerfile builds cleanly from scratch periodically using `docker build --no-cache`.** Cache can hide errors that only appear on a fresh build, such as a missing package that was previously installed in a cached layer.

## Use Cases

### Use Case 1: Consistent Development Environments Across a Team

A small team of developers is building a Python Flask application. Three developers have different versions of Python installed locally, and the application behaves differently on each machine.

- **Problem:** Environment inconsistency wastes debugging time and causes the classic "works on my machine" problem.
- **Concepts applied:** Dockerfile (`FROM python:3.12-slim`, `COPY`, `RUN pip install`), `docker build`, `docker run -p`, `.dockerignore`
- **Expected outcome:** Every developer runs `docker build -t flask-app:dev .` and `docker run -p 5000:5000 flask-app:dev` to get an identical Python 3.12 environment regardless of their local OS, eliminating environment-related bugs.

### Use Case 2: Running a Database for Local Development Without a System Install

A developer wants to use PostgreSQL for a new project but does not want to install it globally on their laptop.

- **Problem:** Installing a database globally pollutes the system, conflicts with other projects using different versions, and is difficult to cleanly uninstall.
- **Concepts applied:** `docker run` with named volume for data persistence, port mapping to expose the database on `localhost`, named container for easy reference
- **Expected outcome:** The developer runs `docker run -d --name dev-pg -e POSTGRES_PASSWORD=secret -v pg-data:/var/lib/postgresql/data -p 5432:5432 postgres:16-alpine` and has a fully functional, isolated PostgreSQL instance accessible at `localhost:5432` with data that persists across restarts.

### Use Case 3: Spinning Up a Full Application Stack with One Command

A new team member joins a project that has a `compose.yaml` defining a web API, a PostgreSQL database, and a Redis cache. They need to get the full stack running locally.

- **Problem:** Manually running and configuring three interdependent services with the correct environment variables, networks, and volumes is complex and error-prone.
- **Concepts applied:** `compose.yaml` with `services`, `depends_on`, `networks`, `volumes`, `environment`; `docker compose up -d`
- **Expected outcome:** The developer clones the repository and runs `docker compose up -d`. All three services start in the correct order, are connected on a shared network, and are immediately usable for development.

### Use Case 4: Isolating Application Versions in CI/CD

A CI/CD pipeline must run tests against two different Node.js versions (18 and 22) to verify compatibility before merging a pull request.

- **Problem:** The CI server has only one version of Node.js installed and cannot run both test suites in the same environment.
- **Concepts applied:** `docker run` with different image tags (`node:18-slim`, `node:22-slim`), bind mount of the repository source code, `--rm` flag for automatic cleanup
- **Expected outcome:** The pipeline runs `docker run --rm -v $(pwd):/app node:18-slim sh -c "cd /app && npm ci && npm test"` and then the same command with `node:22-slim`, providing isolated test results for each version without any system configuration changes.

## Hands-on Examples

### Example 1: Pull and Run Your First Container

You will pull the official Nginx web server image from Docker Hub, run it as a background container, verify it is serving content, then stop and clean it up.

1. Pull the Nginx image. Pinning to version 1.27 ensures reproducibility.

```bash
docker pull nginx:1.27-alpine
```

Expected output:
```
1.27-alpine: Pulling from library/nginx
661ff4d9561e: Pull complete
...
Status: Downloaded newer image for nginx:1.27-alpine
docker.io/library/nginx:1.27-alpine
```

2. Run the container in detached mode, giving it the name `demo-web` and mapping host port 8080 to container port 80.

```bash
docker run -d --name demo-web -p 8080:80 nginx:1.27-alpine
```

Expected output:
```
a94c3b7a2d5f8e1c0b1234567890abcdef1234567890abcdef1234567890abcd
```
(A 64-character container ID is printed.)

3. Confirm the container is running.

```bash
docker ps
```

Expected output:
```
CONTAINER ID   IMAGE               COMMAND                  CREATED         STATUS         PORTS                  NAMES
a94c3b7a2d5f   nginx:1.27-alpine   "/docker-entrypoint.…"   5 seconds ago   Up 4 seconds   0.0.0.0:8080->80/tcp   demo-web
```

4. Open `http://localhost:8080` in a browser, or use `curl` to confirm Nginx is responding.

```bash
curl -I http://localhost:8080
```

Expected output:
```
HTTP/1.1 200 OK
Server: nginx/1.27.x
...
```

5. View the container's access logs.

```bash
docker logs demo-web
```

Expected output (one line per request):
```
172.17.0.1 - - [04/Apr/2026:12:00:00 +0000] "GET / HTTP/1.1" 200 615 "-" "curl/7.88.1" "-"
```

6. Stop the container, remove it, then remove the image.

```bash
docker stop demo-web
docker rm demo-web
docker rmi nginx:1.27-alpine
```

Expected output for `docker stop`: `demo-web`
Expected output for `docker rm`: `demo-web`
Expected output for `docker rmi`: `Untagged: nginx:1.27-alpine ...`

---

### Example 2: Write a Dockerfile and Build a Custom Image

You will create a minimal Python HTTP server packaged as a Docker image and run it as a container.

1. Create a working directory and the application file.

```bash
mkdir hello-docker
cd hello-docker
```

2. Create the application file `server.py`.

```python
# server.py
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Hello from Docker!\n")

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("Listening on port 8000")
    server.serve_forever()
```

3. Create a `.dockerignore` file to prevent unnecessary files from entering the build context.

```
__pycache__
*.pyc
*.pyo
.git
```

4. Create the `Dockerfile`.

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY server.py .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["python", "server.py"]
```

5. Build the image, tagging it `hello-docker:1.0.0`.

```bash
docker build -t hello-docker:1.0.0 .
```

Expected output (abbreviated):
```
[+] Building 12.4s (9/9) FINISHED
 => [internal] load build definition from Dockerfile
 => [internal] load metadata for docker.io/library/python:3.12-slim
 => [1/4] FROM docker.io/library/python:3.12-slim
 => [2/4] WORKDIR /app
 => [3/4] COPY server.py .
 => [4/4] RUN useradd --create-home appuser
 => exporting to image
 => naming to docker.io/library/hello-docker:1.0.0
```

6. Run the image, mapping host port 8000 to container port 8000.

```bash
docker run -d --name hello-server -p 8000:8000 hello-docker:1.0.0
```

7. Test the server responds.

```bash
curl http://localhost:8000
```

Expected output:
```
Hello from Docker!
```

8. Confirm the process runs as the non-root `appuser`.

```bash
docker exec hello-server whoami
```

Expected output:
```
appuser
```

9. Stop and remove the container.

```bash
docker stop hello-server
docker rm hello-server
```

---

### Example 3: Persist Data with a Named Volume

You will run a PostgreSQL database container with a named volume so that data survives container restarts and removal.

1. Create a named volume for the database files.

```bash
docker volume create pg-data
```

Expected output:
```
pg-data
```

2. Run a PostgreSQL 16 container using the volume.

```bash
docker run -d \
  --name dev-pg \
  -e POSTGRES_USER=devuser \
  -e POSTGRES_PASSWORD=devpassword \
  -e POSTGRES_DB=devdb \
  -v pg-data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:16-alpine
```

3. Create a table in the database.

```bash
docker exec -it dev-pg psql -U devuser -d devdb -c \
  "CREATE TABLE notes (id SERIAL PRIMARY KEY, content TEXT);"
```

Expected output:
```
CREATE TABLE
```

4. Insert a row.

```bash
docker exec -it dev-pg psql -U devuser -d devdb -c \
  "INSERT INTO notes (content) VALUES ('This data survives container restarts');"
```

Expected output:
```
INSERT 0 1
```

5. Stop and remove the container entirely.

```bash
docker stop dev-pg
docker rm dev-pg
```

6. Start a brand-new container using the same volume.

```bash
docker run -d \
  --name dev-pg-2 \
  -e POSTGRES_USER=devuser \
  -e POSTGRES_PASSWORD=devpassword \
  -e POSTGRES_DB=devdb \
  -v pg-data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:16-alpine
```

7. Verify the data is still present.

```bash
docker exec -it dev-pg-2 psql -U devuser -d devdb -c "SELECT * FROM notes;"
```

Expected output:
```
 id |                content
----+---------------------------------------
  1 | This data survives container restarts
(1 row)
```

The data persisted because it was stored in the `pg-data` volume, which was never removed.

---

### Example 4: Define a Multi-Container App with Docker Compose

You will write a `compose.yaml` that starts a simple web application alongside a Redis cache, connected on a shared network.

1. Create a project directory and the application file.

```bash
mkdir compose-demo
cd compose-demo
```

2. Create `app.py`.

```python
# app.py
import os
import redis
from http.server import HTTPServer, BaseHTTPRequestHandler

r = redis.Redis(host="redis", port=6379)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        count = r.incr("visits")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"Visit count: {count}\n".encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    print("Listening on port 8080")
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
```

3. Create `requirements.txt`.

```
redis==5.2.1
```

4. Create `Dockerfile`.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8080
CMD ["python", "app.py"]
```

5. Create `compose.yaml`.

```yaml
services:
  web:
    build: .
    ports:
      - "8080:8080"
    depends_on:
      - redis
    networks:
      - app-net

  redis:
    image: redis:7.4-alpine
    networks:
      - app-net

networks:
  app-net:
```

6. Start the application stack.

```bash
docker compose up -d
```

Expected output:
```
[+] Running 3/3
 ✔ Network compose-demo_app-net    Created
 ✔ Container compose-demo-redis-1  Started
 ✔ Container compose-demo-web-1    Started
```

7. Test that the visit counter increments.

```bash
curl http://localhost:8080
curl http://localhost:8080
curl http://localhost:8080
```

Expected output across three calls:
```
Visit count: 1
Visit count: 2
Visit count: 3
```

8. Check the status of the stack.

```bash
docker compose ps
```

Expected output:
```
NAME                    IMAGE                COMMAND                  SERVICE   STATUS    PORTS
compose-demo-redis-1    redis:7.4-alpine     "docker-entrypoint.s…"   redis     running   6379/tcp
compose-demo-web-1      compose-demo-web     "python app.py"          web       running   0.0.0.0:8080->8080/tcp
```

9. Tear down the stack.

```bash
docker compose down
```

Expected output:
```
[+] Running 3/3
 ✔ Container compose-demo-web-1    Removed
 ✔ Container compose-demo-redis-1  Removed
 ✔ Network compose-demo_app-net    Removed
```

## Common Pitfalls

### Pitfall 1: Using the `:latest` Tag in Production Dockerfiles

**Description:** Specifying `FROM node:latest` or pulling `docker pull postgres:latest` gives you whichever version was most recently pushed to Docker Hub — which can change without notice, silently introducing breaking changes.

**Why it happens:** `:latest` is the default tag and requires no extra thought, making it the path of least resistance for beginners.

**Incorrect pattern:**
```dockerfile
FROM python:latest
```

**Correct pattern:**
```dockerfile
FROM python:3.12-slim
```

---

### Pitfall 2: Losing Data by Forgetting to Mount a Volume

**Description:** A developer runs a database or file-storage container without mounting a volume. Everything appears to work, but all data is destroyed the moment the container is removed with `docker rm`.

**Why it happens:** Docker containers present a fully functional filesystem without any volumes; it is not obvious that the data is ephemeral until it disappears.

**Incorrect pattern:**
```bash
# No volume: all PostgreSQL data lives in the container's writable layer
docker run -d --name db -e POSTGRES_PASSWORD=secret postgres:16-alpine
docker rm db
# All data is gone
```

**Correct pattern:**
```bash
# Named volume: data persists on the host, independent of the container
docker run -d --name db \
  -e POSTGRES_PASSWORD=secret \
  -v pg-data:/var/lib/postgresql/data \
  postgres:16-alpine
docker rm db
# Data is preserved in the pg-data volume
```

---

### Pitfall 3: Invalidating the Build Cache by Copying Source Code Too Early

**Description:** Placing a `COPY . .` instruction before dependency installation means every time any source file changes, Docker rebuilds the dependency layer from scratch — even if `package.json` or `requirements.txt` did not change. This turns a 2-second build into a 2-minute build.

**Why it happens:** Copying everything at once feels natural, and the caching behaviour of Dockerfile layers is not immediately obvious to beginners.

**Incorrect pattern:**
```dockerfile
FROM node:22-slim
WORKDIR /app
COPY . .
RUN npm ci
CMD ["node", "src/index.js"]
```

**Correct pattern:**
```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY src/ ./src/
CMD ["node", "src/index.js"]
```

---

### Pitfall 4: Running the Container Process as Root

**Description:** By default, processes inside a Docker container run as the `root` user. If a vulnerability in the application is exploited, the attacker has root access within the container, which substantially increases the blast radius of an attack.

**Why it happens:** Base images run as root by default, and adding a `USER` instruction is easy to overlook when just trying to get something running.

**Incorrect pattern:**
```dockerfile
FROM node:22-slim
WORKDIR /app
COPY . .
RUN npm ci
CMD ["node", "index.js"]
# Runs as root
```

**Correct pattern:**
```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN useradd --create-home appuser
USER appuser
CMD ["node", "index.js"]
```

---

### Pitfall 5: Not Using a `.dockerignore` File

**Description:** Without a `.dockerignore`, the Docker build context — which includes everything in the directory — is sent to the Docker daemon. This can include `node_modules/` (hundreds of megabytes), `.git/` (complete repository history), `.env` files with secrets, and large log files. Build times balloon, and secrets may end up baked into the image.

**Why it happens:** The `.dockerignore` file is not created automatically; it requires a deliberate step that beginners are often unaware of.

**Incorrect pattern:**
No `.dockerignore` exists; `docker build .` sends gigabytes of data to the daemon.

**Correct pattern:**
Create a `.dockerignore` file at the root of your project:
```
node_modules/
.git/
.env
*.log
dist/
coverage/
```

---

### Pitfall 6: Using the Default Bridge Network for Multi-Container Communication

**Description:** When two containers are on the default bridge network, they cannot reach each other by name — only by IP address. Container IP addresses change every time a container restarts, so hardcoding them fails silently after the first restart.

**Why it happens:** Containers connect to the default bridge network automatically; user-defined networks must be created explicitly, which is an extra step beginners often skip.

**Incorrect pattern:**
```bash
docker run -d --name db postgres:16-alpine
docker run -d --name api -e DB_HOST=172.17.0.2 myapi:1.0.0
# 172.17.0.2 will break after the next db container restart
```

**Correct pattern:**
```bash
docker network create app-net
docker run -d --name db --network app-net postgres:16-alpine
docker run -d --name api --network app-net -e DB_HOST=db myapi:1.0.0
# "db" resolves by name on user-defined networks
```

---

### Pitfall 7: Stopping Compose Services with `docker stop` Instead of `docker compose down`

**Description:** Running `docker stop <container-name>` on a Compose-managed container stops only that container and leaves networks and other services in a partially running state. The stopped container also remains in the stopped state rather than being removed, causing conflicts on the next `docker compose up`.

**Why it happens:** `docker stop` is the natural instinct for stopping a running container; beginners do not immediately associate Compose services with the Compose CLI.

**Incorrect pattern:**
```bash
# Stops one container, leaves others running, does not clean up networks
docker stop myapp-web-1
```

**Correct pattern:**
```bash
# Stops all services, removes containers and networks cleanly
docker compose down
```

## Summary

- Docker packages applications and their dependencies into portable, isolated containers that run identically across any environment, eliminating the "works on my machine" problem without the overhead of full virtual machines.
- Images are read-only, layered blueprints built from Dockerfiles; containers are running instances of images with an added writable layer that is discarded on removal.
- Named volumes decouple persistent data from the container lifecycle, ensuring databases and file stores survive container deletion.
- User-defined bridge networks allow containers to communicate with each other by name, which is the foundation of every multi-container Docker application.
- Docker Compose replaces error-prone manual `docker run` chains with a single declarative `compose.yaml` file, letting the entire application stack start with `docker compose up -d` and stop cleanly with `docker compose down`.

## Further Reading

- [Docker Overview — Official Docs](https://docs.docker.com/get-started/docker-overview/) — The authoritative introduction to Docker's architecture, core objects, and design philosophy; the best single page to re-read when any fundamental concept is unclear.
- [Dockerfile Reference — Official Docs](https://docs.docker.com/reference/dockerfile/) — The complete reference for every Dockerfile instruction with syntax, options, and behavioural notes; essential for understanding instructions beyond the basics covered in this module.
- [Docker Build Best Practices — Official Docs](https://docs.docker.com/build/building/best-practices/) — Official guidance on writing efficient, secure, and maintainable Dockerfiles, covering multi-stage builds, layer caching, and base image selection.
- [Docker Engine Storage: Volumes — Official Docs](https://docs.docker.com/engine/storage/volumes/) — Deep coverage of named volumes, bind mounts, `tmpfs` mounts, and when to use each; critical reading before building any application that manages persistent data.
- [Docker Networking Overview — Official Docs](https://docs.docker.com/engine/network/) — Explains every network driver (bridge, host, overlay, none) with usage guidance; the definitive reference for understanding how containers communicate in single-host and multi-host deployments.
- [Docker Compose Application Model — Official Docs](https://docs.docker.com/compose/intro/compose-application-model/) — Explains the Compose Specification model (services, networks, volumes, configs, secrets) with canonical YAML examples; the right next read after this module's Compose introduction.
- [Docker Engine 29 Release Notes — Official Docs](https://docs.docker.com/engine/release-notes/29/) — Release notes for Docker Engine v29 (current stable as of 2026), covering the nftables firewall backend, the containerd image store as default, and security fixes; useful for understanding version-specific behaviour.
- [Top 10 Docker Mistakes Beginners Make — Ashish Singh, Medium](https://ashishnoob.medium.com/top-10-docker-mistakes-beginners-make-and-how-to-avoid-them-b1283e8bd2d3) — A practitioner-written walkthrough of the most common mistakes new Docker users make, with concrete before/after examples that reinforce the pitfalls covered in this module.
