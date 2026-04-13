# Module 3: Networking
> Subject: Docker | Difficulty: Intermediate | Estimated Time: 165 minutes

## Objective

After completing this module, you will be able to explain Docker's Container Network Model (CNM) and describe how the daemon, network drivers, and the embedded DNS server cooperate to connect containers. You will create, inspect, connect, disconnect, and remove user-defined networks using the full `docker network` CLI. You will select the correct driver — bridge, host, overlay, macvlan, ipvlan, or none — for a given scenario and justify the choice. You will distinguish between `EXPOSE` and `--publish`, use all forms of the `-p` flag including host-IP binding, and understand when to bind to `127.0.0.1` instead of `0.0.0.0`. You will configure DNS-based service discovery on user-defined bridge networks, define custom networks and external networks in `compose.yaml`, build multi-network topologies that enforce service isolation, and apply network security best practices including least-privilege network access and lateral-movement prevention.

## Prerequisites

- Completed Module 1: Basics — you should be comfortable with `docker run`, `docker ps`, `docker exec`, port mapping with `-p`, and basic Compose
- Completed Module 2: Volumes — familiarity with named volumes and `compose.yaml` syntax is assumed
- Docker Engine 27 or later installed (verify with `docker --version`; current stable release is Docker Engine 29.3.1)
- Basic understanding of TCP/IP networking concepts: IP addresses, ports, subnets, and DNS

## Key Concepts

### The Container Network Model (CNM)

Docker's networking architecture is defined by the **Container Network Model (CNM)**, a specification that abstracts the underlying infrastructure and provides a consistent API for connecting containers regardless of the host OS, cloud provider, or physical topology.

The CNM defines three core building blocks:

- **Sandbox**: An isolated network environment for a single container. It holds the container's network interfaces, routing table, and DNS configuration. A sandbox is created whenever a container is started and destroyed when it stops. It maps directly to a Linux network namespace.
- **Endpoint**: A virtual network interface that connects a sandbox to a network. Each time a container joins a network, an endpoint is created and assigned an IP address on that network. A container can have multiple endpoints — one per network it belongs to.
- **Network**: A group of endpoints that can communicate directly with each other. A network has its own subnet and gateway. Endpoints on different networks cannot communicate without explicit routing.

```
CNM Building Blocks:
┌─────────────────────────────────────────────────────────────────┐
│  Network A (bridge)  172.20.0.0/16                              │
│                                                                  │
│   ┌─────────────┐    endpoint     ┌─────────────────────────┐   │
│   │  Sandbox    │◄────────────────│  Container: web         │   │
│   │  eth0       │                 │  172.20.0.2             │   │
│   │  172.20.0.2 │                 └─────────────────────────┘   │
│   └─────────────┘                                                │
│                                                                  │
│   ┌─────────────┐    endpoint     ┌─────────────────────────┐   │
│   │  Sandbox    │◄────────────────│  Container: db          │   │
│   │  eth0       │                 │  172.20.0.3             │   │
│   │  172.20.0.3 │                 └─────────────────────────┘   │
│   └─────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

Pluggable **network drivers** implement the CNM specification. Docker ships with six built-in drivers on Linux, and third-party drivers (such as Weave or Cilium) can be installed as plugins. The driver you choose determines the physical and logical behavior of the network: how packets are forwarded, whether containers span multiple hosts, and how they appear on the physical network.

### Network Drivers

#### bridge (default)

The bridge driver creates an internal Layer 2 network on the Docker host, backed by a Linux bridge device (typically `docker0` for the default network). Containers attached to the same bridge network can communicate with each other. Traffic leaving the host is routed through NAT (masquerading).

There are two fundamentally different kinds of bridge networks:

**The default bridge (`bridge` network):** Created automatically when the Docker daemon starts. Every container that does not specify `--network` is attached to this network. Containers on the default bridge can communicate with each other only by IP address — hostname-based DNS resolution is not available. This is a significant limitation in practice, because IP addresses are reassigned on every container restart.

**User-defined bridge networks:** Networks you create explicitly with `docker network create`. These provide automatic DNS resolution: any container on the same user-defined bridge can reach any other container by its name. This makes user-defined bridges the correct choice for virtually all multi-container workloads on a single host.

| Feature | Default Bridge | User-Defined Bridge |
|---|---|---|
| DNS resolution by container name | No | Yes |
| Network isolation from other containers | No (all containers share it) | Yes (scoped to members) |
| Connect/disconnect without restart | No | Yes |
| Per-network configuration | No | Yes |
| Recommended for production | No | Yes |

#### host

The host driver removes the network namespace boundary between the container and the Docker host. The container process binds directly to the host's network interfaces and ports. There is no NAT, no port mapping, and no virtual bridge — if your application listens on port 8080, it occupies port 8080 on the host directly.

The host driver offers the lowest possible network latency for containers (no NAT overhead) and is occasionally useful for network-diagnostic tools that need to inspect or manipulate the host's network stack. The tradeoff is complete loss of network isolation: a container on the host network can reach and be reached by everything the host can. The `--publish` flag is meaningless with `--network host` because there is no separate network namespace to publish from.

The host driver is available on Linux only. On Docker Desktop for macOS and Windows, containers run inside a Linux VM, and `--network host` connects to the VM's network, not the physical host's.

#### overlay

The overlay driver creates a virtual network that spans multiple Docker daemon hosts. Packets between containers on different physical machines are encapsulated using VXLAN and tunnelled across the physical network. The overlay driver requires Docker Swarm mode to be initialized, because Swarm provides the distributed key-value store needed to share network state across hosts.

When you create an overlay network with `--attachable`, both standalone containers and Swarm services can join it. Without `--attachable`, only Swarm services can attach.

Three ports must be open between participating Docker hosts for overlay networking to function:

| Port | Protocol | Purpose |
|---|---|---|
| 2377 | TCP | Swarm cluster management |
| 4789 | UDP | Overlay network traffic (VXLAN) |
| 7946 | TCP + UDP | Node-to-node communication |

Optional IPsec encryption is available with `--opt encrypted`, but it carries a performance cost and is not supported on Windows containers.

#### macvlan

The macvlan driver assigns each container its own MAC address, making it appear as a physical device on the network. Traffic goes directly through the host's physical NIC to the external network — there is no NAT and no Linux bridge. The container gets an IP address from the same subnet as the physical network it is attached to, and is directly routable from other hosts on that subnet.

Macvlan is the correct choice for legacy applications that were previously running as virtual machines and expect to have a routable IP address on the physical network, or for network monitoring tools that need low-level access to raw packets.

Critical limitations:
- Linux only; not supported in rootless mode
- Requires promiscuous mode on the NIC (often unavailable in cloud environments)
- Containers cannot communicate with the Docker host itself (a Linux kernel restriction)
- Cloud providers typically block macvlan traffic

#### ipvlan

The ipvlan driver is similar to macvlan but all containers share the parent interface's MAC address — only the IP addresses differ. This avoids the MAC proliferation problem that macvlan causes in environments with per-MAC switching rules or cloud providers that limit MAC addresses per port.

IPvlan operates in two modes:
- **L2 mode**: Acts like macvlan but shares the parent MAC. Suitable for the same use cases as macvlan where MAC address constraints exist.
- **L3 mode**: Docker acts as a router and forwards packets at Layer 3. Containers are not in the same broadcast domain as the physical network; this enables very large deployments but requires static routes to be configured on the upstream router.

#### none

The none driver creates a container with no network interfaces except a loopback (`lo`). The container has absolutely no external connectivity. Used for:
- Batch processing jobs that need no network access
- Security-sensitive workloads that must be completely isolated
- Testing container behavior in a fully isolated environment

### Default Bridge vs. User-Defined Bridge: DNS Resolution in Depth

The DNS difference between default and user-defined bridges is the most practically important networking concept for developers. Understanding it prevents a class of subtle bugs where services find each other during initial startup but fail after restarts.

On the **default bridge**, Docker does not run an embedded DNS server. Each container inherits `/etc/resolv.conf` from the Docker host. Containers can only reach each other via IP address. IP addresses are assigned from the `172.17.0.0/16` pool and change every time a container is recreated.

On a **user-defined bridge**, Docker runs an embedded DNS server at the virtual address `127.0.0.11` inside each container. This DNS server maintains a mapping from container name to its current IP address. When container `api` tries to resolve `db`, the request goes to `127.0.0.11`, which returns the current IP of the `db` container — automatically updated whenever `db` is restarted. The DNS server also handles search domain resolution so a container named `my-database` is reachable as just `my-database`.

```
Default Bridge (DNS lookup fails by name):          User-Defined Bridge (DNS works):
┌──────────────────────┐                            ┌──────────────────────┐
│  api (172.17.0.3)    │                            │  api                 │
│  resolv: host DNS    │                            │  resolv: 127.0.0.11  │
│  $ ping db           │                            │  $ ping db           │
│  ping: unknown host  │                            │  PING db (172.20.0.3)│
└──────────────────────┘                            └──────────────────────┘
```

### Network CLI Commands

The `docker network` management command has seven subcommands:

| Command | What It Does |
|---|---|
| `docker network create [OPTIONS] NAME` | Create a new network |
| `docker network ls` | List all networks |
| `docker network inspect NAME` | Show detailed JSON information about a network |
| `docker network connect NETWORK CONTAINER` | Attach a running container to a network |
| `docker network disconnect NETWORK CONTAINER` | Detach a container from a network |
| `docker network rm NAME [NAME...]` | Remove one or more networks |
| `docker network prune` | Remove all networks not used by any container |

Key flags for `docker network create`:

| Flag | Purpose |
|---|---|
| `-d, --driver` | Network driver to use (default: `bridge`) |
| `--subnet` | CIDR notation subnet, e.g. `192.168.10.0/24` |
| `--gateway` | Gateway IP address for the subnet |
| `--ip-range` | Allocate container IPs from a sub-range of the subnet |
| `--opt` | Driver-specific options (e.g. `--opt com.docker.network.bridge.name=my-br0`) |
| `--attachable` | Allow standalone containers to attach (overlay networks only) |

```bash
# Create a basic user-defined bridge
docker network create app-net

# Create a bridge with a custom subnet and gateway
docker network create \
  --driver bridge \
  --subnet 192.168.50.0/24 \
  --gateway 192.168.50.1 \
  my-custom-net

# List all networks
docker network ls

# Inspect a network (outputs JSON with connected containers, IP assignments, etc.)
docker network inspect app-net

# Connect a running container to an additional network
docker network connect app-net my-container

# Disconnect a container from a network (container stays running)
docker network disconnect app-net my-container

# Remove a specific network (fails if any container is still connected)
docker network rm app-net

# Remove all unused networks
docker network prune
```

### Port Publishing: EXPOSE vs. --publish

These two mechanisms are commonly confused but serve entirely different purposes.

**`EXPOSE` in a Dockerfile** is documentation. It tells anyone reading the Dockerfile — and tooling such as Docker Desktop and Compose — which ports the containerized application listens on. It does not open any port to the outside world, does not create any firewall rule, and has no effect at runtime by itself. Think of it as a comment with machine-readable structure.

```dockerfile
# This documents that the app listens on 3000, but does not publish it
EXPOSE 3000
```

**`--publish` (or `-p`) at runtime** creates an actual port mapping in the host's network stack (via iptables/nftables rules on Linux). It maps a port on the host to a port inside the container, making the container's port reachable from outside the container network.

The `--publish` flag supports several forms:

```bash
# Map host port 8080 to container port 80 (TCP, all host IPs)
docker run -p 8080:80 nginx:1.27-alpine

# Map a specific host IP — only localhost can reach this port
docker run -p 127.0.0.1:8080:80 nginx:1.27-alpine

# Map a specific IPv6 address
docker run -p '[::1]:8080:80' nginx:1.27-alpine

# Publish UDP instead of TCP
docker run -p 5353:5353/udp my-dns-server:1.0.0

# Publish both TCP and UDP on the same port
docker run -p 8080:80/tcp -p 8080:80/udp my-app:1.0.0

# Let Docker assign a random ephemeral host port
docker run -p 80 nginx:1.27-alpine
```

**The security implications of host-IP binding** are significant. The default binding `0.0.0.0` means the port is reachable from any network interface on the host — the local machine, the LAN, and the internet (if port 0.0.0.0 is reachable externally). Binding to `127.0.0.1` restricts the port to traffic originating on the local machine only. For internal services that only need to be reached by processes on the same host (such as a backend API consumed by a reverse proxy running on the host), always bind to `127.0.0.1`.

```bash
# Insecure: database exposed to all network interfaces
docker run -p 5432:5432 postgres:16-alpine

# Secure: database only reachable from localhost
docker run -p 127.0.0.1:5432:5432 postgres:16-alpine
```

Also note the `--publish-all` / `-P` flag, which publishes all `EXPOSE`d ports to random ephemeral host ports. It is convenient for development but not suitable for production because the ports are unpredictable.

### DNS and Service Discovery in User-Defined Networks

Docker's embedded DNS server (`127.0.0.11`) handles four kinds of name resolution for containers on user-defined networks:

1. **Container name**: The exact name given with `--name` resolves to that container's IP on the shared network.
2. **Service name (Compose)**: In a Compose stack, the service name (e.g., `db`, `web`, `redis`) resolves to the IP of any healthy container running that service, automatically load-balancing across replicas.
3. **Network alias**: Additional hostnames assigned with `--network-alias` or the `aliases` key in Compose. A single container can be reachable under multiple names.
4. **External DNS**: If the embedded DNS server cannot resolve a name, it forwards the query to the DNS servers configured on the host, providing normal internet name resolution for external hostnames.

```bash
# Assign an alias so the container is reachable as both "db" and "postgres"
docker run -d \
  --name db \
  --network app-net \
  --network-alias postgres \
  postgres:16-alpine
```

### Inter-Container Communication and Network Isolation

A key property of user-defined networks is **scoped isolation**: only containers explicitly connected to a network can communicate with each other on that network. Two containers on different networks cannot reach each other without being connected to a common network or having a published port.

This property enables you to build precise network topologies that mirror the communication requirements of your application:

```
Example: Three-tier topology

  [internet]
      │
   ┌──┴──┐
   │ proxy│  ← only container on "frontend" network with published port
   └──┬──┘
      │ frontend network
   ┌──┴──┐
   │ app  │  ← connected to both "frontend" and "backend" networks
   └──┬──┘
      │ backend network
   ┌──┴──┐
   │  db  │  ← only on "backend" network; not reachable from proxy
   └─────┘
```

In this topology, the `proxy` container cannot directly reach `db` — they share no network. Only `app` bridges both tiers. This is network-level enforcement of your architectural intent. Even if `proxy` is compromised, it cannot directly query the database.

### Networks in Docker Compose

Compose automates network management, making complex topologies easy to declare.

**Default network:** When you run `docker compose up`, Compose creates a single network named `<project>_default` (where `<project>` is the directory name by default). Every service that does not specify a `networks` key is automatically attached to this default network and can reach every other service by its service name. This default behavior is sufficient for simple stacks.

**Custom networks:** Define multiple named networks in the top-level `networks` block and assign services to them explicitly using the `networks` key per service. Services only communicate across networks they both belong to.

```yaml
services:
  proxy:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
    networks:
      - frontend

  app:
    build: .
    networks:
      - frontend
      - backend

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secret
    networks:
      - backend

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
```

**Network aliases in Compose:** Add alternate hostnames for a service within a specific network using `aliases`:

```yaml
services:
  db:
    image: postgres:16-alpine
    networks:
      backend:
        aliases:
          - database
          - pg

networks:
  backend:
```

**External networks:** If you have a network created outside of Compose — for example, shared infrastructure managed by a separate Compose stack — mark it as `external: true`. Compose will look for it rather than trying to create it, and will error if it does not exist.

```yaml
networks:
  shared-infra:
    external: true
    name: my-pre-existing-network
```

**Overriding the default network:** You can customize the auto-created default network by defining a `default` entry under `networks`:

```yaml
networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 192.168.100.0/24
```

### Multi-Host Overlay Networking (Swarm Mode)

For applications that span multiple Docker hosts, the overlay driver is Docker's built-in solution. It requires initializing a Swarm and then creating an overlay network:

```bash
# On the manager node: initialize the Swarm
docker swarm init --advertise-addr <MANAGER-IP>

# Create an overlay network accessible to both services and standalone containers
docker network create \
  --driver overlay \
  --attachable \
  multi-host-net

# Deploy a service onto the overlay network
docker service create \
  --name api \
  --network multi-host-net \
  --replicas 3 \
  myapi:1.0.0
```

Containers and services on the overlay network can communicate by service name regardless of which physical host they are running on. Docker Swarm's built-in DNS server resolves service names to the VIP (virtual IP) of the service, and the Swarm's internal load balancer distributes requests across replicas.

For new multi-host deployments in 2025–2026, Kubernetes is the dominant orchestration platform and overlay networking there is provided by CNI plugins (Flannel, Calico, Cilium). Docker Swarm overlay remains relevant for smaller deployments and is important to understand as the conceptual foundation for how all overlay networking works.

### Network Security Best Practices

#### 1. Use user-defined networks to isolate services

Never let unrelated services share the default bridge network. Services that do not need to communicate with each other should not be able to, even by accident. Create separate networks for separate tiers and connect only the services that need to talk.

#### 2. Bind published ports to specific IPs

Unless a service is meant to be publicly accessible, bind published ports to `127.0.0.1` rather than `0.0.0.0`. A database published on `0.0.0.0:5432` is reachable from the LAN and the internet if firewall rules permit. The same database on `127.0.0.1:5432` is only reachable by processes on the same host.

#### 3. Do not publish ports that do not need to be published

Containers on the same user-defined network communicate over container ports directly — no port publishing is needed for internal traffic. Only publish ports for services that external clients (browsers, API consumers, monitoring tools) need to reach. Every published port is an attack surface.

#### 4. Give each service the minimum set of networks it needs

A container that only talks to a database does not need to be on the frontend network. Apply the least-privilege principle: each service should be a member of only the networks required for its specific communication needs.

#### 5. Use internal networks for backend tiers

The `internal: true` option on a network prevents containers on that network from reaching the external internet, even if they are not publish-restricted:

```yaml
networks:
  backend:
    driver: bridge
    internal: true
```

Use `internal: true` on any network that should carry only inter-service traffic and never needs to reach an external URL.

#### 6. Encrypt overlay traffic in Swarm

When using overlay networks with sensitive data, enable IPsec encryption:

```bash
docker network create \
  --driver overlay \
  --opt encrypted \
  secure-overlay
```

Be aware that this carries a CPU performance cost and must be tested before production use. Also note that encrypted overlay networks are not supported between Linux and Windows containers.

---

## Best Practices

1. **Always use user-defined bridge networks for multi-container applications.** The default bridge offers no DNS resolution between containers. User-defined bridges provide automatic DNS, better isolation, and the ability to connect and disconnect containers at runtime without restarts. This is the single most impactful networking habit to develop.

2. **Model your network topology after your application's communication requirements.** Before writing any `docker network create` commands, draw your services and which ones need to talk. Translate that diagram directly into networks in `compose.yaml`. Every service-to-service communication path becomes a shared network membership; every missing path becomes an isolation guarantee.

3. **Bind published ports to `127.0.0.1` for services that are only consumed locally.** Internal APIs, admin panels, and databases that are accessed by a reverse proxy or another service on the same host should bind to localhost only. Reserve `0.0.0.0` binding for services genuinely intended to be publicly reachable.

4. **Minimize the number of published ports.** Inter-container traffic on a shared network uses container ports and needs no host-port mapping. Only publish a port when an external client — something outside the container network — must reach that service.

5. **Use `internal: true` on backend networks.** Networks that carry only service-to-service traffic and never need outbound internet access should be declared `internal`. This prevents a compromised container from making outbound requests to exfiltrate data or download further payloads.

6. **Use `docker network inspect` to verify topology before deploying.** After building a network configuration, run `docker network inspect <network>` and check the `Containers` block. Confirm that exactly the right containers are members of each network and that no unexpected containers have been added to the default bridge.

7. **Clean up unused networks regularly.** Networks accumulate as containers are removed and recreated. Run `docker network prune` as part of routine maintenance to remove dangling networks and avoid subnet exhaustion, which can cause new network creation to fail.

8. **Pin explicit subnets in production.** By default Docker assigns subnets automatically from a pool, which can cause IP range conflicts with existing VPNs, corporate networks, or cloud VPCs. In production, always specify `--subnet` (CLI) or `ipam.config.subnet` (Compose) to use a predictable, non-conflicting range.

9. **Avoid the `--link` flag.** `--link` is a legacy feature from the default bridge era. It creates one-way DNS aliases and injects environment variables — behaviors now fully superseded by user-defined networks. The `--link` flag is deprecated and may be removed in a future release.

10. **Use `aliases` for zero-downtime service migration.** When renaming a service or migrating from one container to another, add the old name as a network alias on the new container. Consumers using the old name will automatically route to the new container without any reconfiguration.

---

## Use Cases

### Use Case 1: Isolated Development Stack with Three Tiers

A development team is building a three-tier application: an Nginx reverse proxy, a Node.js API, and a PostgreSQL database.

- **Problem:** The proxy must reach the API, the API must reach the database, but the proxy must have no direct path to the database. All three services must be reachable by name.
- **Concepts applied:** Two user-defined bridge networks (`frontend`, `backend`), service name DNS resolution, `app` service connected to both networks as the intermediary, `db` service on `backend` only with no published ports.
- **Expected outcome:** The proxy can resolve `api` by name. The API can resolve `db` by name. Neither the proxy nor any external process can open a direct connection to the database, because `db` is on the `backend` network only and has no published ports.

### Use Case 2: Sharing Infrastructure Between Compose Stacks

A team runs two separate Compose stacks: a monitoring stack (Prometheus + Grafana) and an application stack (API + database). The monitoring services need to scrape metrics from the application stack.

- **Problem:** Compose stacks create their own isolated networks by default; containers in different stacks cannot reach each other.
- **Concepts applied:** External network declared in both `compose.yaml` files, pre-existing network created with `docker network create monitoring-bridge`, each stack joins it with `external: true`.
- **Expected outcome:** Prometheus can reach the API's `/metrics` endpoint by service name. Neither stack controls the lifecycle of the shared network; it persists independently.

### Use Case 3: Legacy Application Requiring a Physical Network IP

A legacy application was previously deployed as a bare-metal service. It hard-codes its own IP address for peer discovery and must appear on the corporate LAN's `10.0.1.0/24` subnet with a routable IP.

- **Problem:** Standard Docker bridge networking puts containers behind NAT on a private Docker subnet, not the corporate LAN. The application's peer discovery breaks.
- **Concepts applied:** Macvlan driver with `--subnet 10.0.1.0/24 --gateway 10.0.1.1 -o parent=eth0`, container receives a routable LAN IP such as `10.0.1.50`.
- **Expected outcome:** The container appears as a physical host on the LAN, receives ARP requests, and its IP is routable from other hosts without NAT. Note that the container cannot reach the Docker host directly.

### Use Case 4: Security-Hardened Single-Host Production Stack

A production deployment of a web application must pass a security audit. The auditor requires that the database is not reachable from the internet and cannot make outbound connections to download data.

- **Problem:** The default bridge exposes the database to other containers, and the backend network should be air-gapped from the internet.
- **Concepts applied:** Published port on API bound to `127.0.0.1` (consumed by a host-level Nginx), `internal: true` on the backend network, no published ports on the database container.
- **Expected outcome:** The database has no externally published port, no internet access, and is reachable only by the API container on the `backend` network. A port scan from outside the host returns no open ports for the database.

---

## Hands-on Examples

### Example 1: Explore the Default vs. User-Defined Bridge DNS Behaviour

You will run two containers on the default bridge, observe that DNS fails, then move them to a user-defined bridge and watch DNS succeed. No custom images are needed.

1. Create two containers on the default bridge network.

```bash
docker run -d --name alpha alpine:3.20 sleep 600
docker run -d --name beta alpine:3.20 sleep 600
```

2. From `alpha`, try to ping `beta` by name.

```bash
docker exec alpha ping -c 2 beta
```

Expected output:
```
ping: bad address 'beta'
```

Name resolution fails because the default bridge has no embedded DNS. Note the IP address assigned to `beta` for comparison later:

```bash
docker inspect beta --format '{{.NetworkSettings.IPAddress}}'
```

Expected output (your IP will vary):
```
172.17.0.3
```

3. Ping by IP — this works on the default bridge.

```bash
docker exec alpha ping -c 2 172.17.0.3
```

Expected output:
```
PING 172.17.0.3 (172.17.0.3): 56 data bytes
64 bytes from 172.17.0.3: seq=0 ttl=64 time=0.124 ms
64 bytes from 172.17.0.3: seq=1 ttl=64 time=0.089 ms
```

4. Clean up these containers.

```bash
docker stop alpha beta
docker rm alpha beta
```

5. Create a user-defined bridge network.

```bash
docker network create demo-net
```

Expected output:
```
7f3a1b2c9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
```

6. Start the same two containers on the user-defined network.

```bash
docker run -d --name alpha --network demo-net alpine:3.20 sleep 600
docker run -d --name beta --network demo-net alpine:3.20 sleep 600
```

7. Ping by name — this now works.

```bash
docker exec alpha ping -c 2 beta
```

Expected output:
```
PING beta (172.18.0.3): 56 data bytes
64 bytes from 172.18.0.3: seq=0 ttl=64 time=0.096 ms
64 bytes from 172.18.0.3: seq=1 ttl=64 time=0.078 ms
```

8. Inspect the embedded DNS server address inside the container.

```bash
docker exec alpha cat /etc/resolv.conf
```

Expected output:
```
search demo-net
nameserver 127.0.0.11
options ndots:0
```

The nameserver `127.0.0.11` is Docker's embedded DNS server, present only in user-defined networks.

9. Inspect the network to see connected containers.

```bash
docker network inspect demo-net
```

Look for the `"Containers"` block in the JSON output, which lists both `alpha` and `beta` with their assigned IPs and MAC addresses.

10. Clean up.

```bash
docker stop alpha beta
docker rm alpha beta
docker network rm demo-net
```

---

### Example 2: Port Publishing Patterns and Host-IP Binding

You will experiment with all the major port publishing forms and verify their access behaviour.

1. Publish a port bound to all interfaces (the default).

```bash
docker run -d --name pub-all -p 8080:80 nginx:1.27-alpine
```

2. Confirm the binding.

```bash
docker port pub-all
```

Expected output:
```
80/tcp -> 0.0.0.0:8080
80/tcp -> [::]:8080
```

The port is bound to all IPv4 and IPv6 interfaces.

3. Run a second container bound to localhost only.

```bash
docker run -d --name pub-local -p 127.0.0.1:8081:80 nginx:1.27-alpine
```

4. Confirm the binding.

```bash
docker port pub-local
```

Expected output:
```
80/tcp -> 127.0.0.1:8081
```

5. Test that both are reachable from localhost.

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081
```

Expected output for each:
```
200
```

6. Clean up.

```bash
docker stop pub-all pub-local
docker rm pub-all pub-local
```

---

### Example 3: Connect and Disconnect a Running Container

You will connect a running container to a second network at runtime, verify it gains DNS access to that network's containers, and then disconnect it.

1. Create two separate networks.

```bash
docker network create net-a
docker network create net-b
```

2. Start a container on each network.

```bash
docker run -d --name service-a --network net-a alpine:3.20 sleep 600
docker run -d --name service-b --network net-b alpine:3.20 sleep 600
```

3. Confirm that `service-a` cannot reach `service-b` (different networks).

```bash
docker exec service-a ping -c 1 service-b
```

Expected output:
```
ping: bad address 'service-b'
```

4. Connect `service-a` to `net-b` at runtime (no restart required).

```bash
docker network connect net-b service-a
```

5. Verify `service-a` now has two network interfaces.

```bash
docker exec service-a ip addr show
```

Expected output shows two `eth` interfaces: one for `net-a`, one for `net-b`.

6. Ping `service-b` by name from `service-a` — now it works.

```bash
docker exec service-a ping -c 2 service-b
```

Expected output:
```
PING service-b (172.19.0.2): 56 data bytes
64 bytes from 172.19.0.2: seq=0 ttl=64 time=0.111 ms
64 bytes from 172.19.0.2: seq=1 ttl=64 time=0.093 ms
```

7. Disconnect `service-a` from `net-b`.

```bash
docker network disconnect net-b service-a
```

8. Confirm `service-b` is no longer reachable.

```bash
docker exec service-a ping -c 1 service-b
```

Expected output:
```
ping: bad address 'service-b'
```

9. Clean up.

```bash
docker stop service-a service-b
docker rm service-a service-b
docker network rm net-a net-b
```

---

### Example 4: Multi-Network Topology with Docker Compose

You will implement the three-tier isolation topology from the Use Cases section: a proxy on the `frontend` network, an app on both networks, and a database on the `backend` network only. You will verify the isolation holds.

1. Create a project directory.

```bash
mkdir network-demo
cd network-demo
```

2. Create `app.py` — a minimal HTTP server that reports its name and queries the "database" placeholder.

```python
# app.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        hostname = socket.gethostname()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"Response from app container: {hostname}\n".encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    print("app listening on port 5000")
    HTTPServer(("0.0.0.0", 5000), Handler).serve_forever()
```

3. Create `Dockerfile` for the app.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
EXPOSE 5000
CMD ["python", "app.py"]
```

4. Create `compose.yaml`.

```yaml
services:
  proxy:
    image: nginx:1.27-alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - frontend
    depends_on:
      - app

  app:
    build: .
    networks:
      - frontend
      - backend

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secret
    networks:
      - backend

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true
```

5. Create `nginx.conf` to proxy requests from port 80 to the `app` service on port 5000.

```nginx
server {
    listen 80;
    location / {
        proxy_pass http://app:5000;
    }
}
```

6. Start the stack.

```bash
docker compose up -d --build
```

Expected output:
```
[+] Running 5/5
 ✔ Network network-demo_frontend  Created
 ✔ Network network-demo_backend   Created
 ✔ Container network-demo-db-1    Started
 ✔ Container network-demo-app-1   Started
 ✔ Container network-demo-proxy-1 Started
```

7. Test that the proxy correctly routes to the app.

```bash
curl http://localhost:8080
```

Expected output:
```
Response from app container: <container-id>
```

8. Verify that the proxy cannot reach the database directly. The `db` service is on the `backend` network only and the proxy is on `frontend` only — they share no network.

```bash
docker compose exec proxy ping -c 1 db
```

Expected output:
```
ping: bad address 'db'
```

This confirms network isolation: the proxy cannot resolve `db` because they share no common network.

9. Verify the app can reach both `proxy` and `db`.

```bash
docker compose exec app ping -c 1 proxy
docker compose exec app ping -c 1 db
```

Expected output for each:
```
PING proxy (...): ...
64 bytes from ...: seq=0 ...
```

The `app` service resolves both names because it is a member of both networks.

10. Inspect both networks to see which containers are members.

```bash
docker network inspect network-demo_frontend
docker network inspect network-demo_backend
```

In the `"Containers"` block: `network-demo_frontend` contains `proxy` and `app`. `network-demo_backend` contains `app` and `db`. The database is absent from the frontend network entirely.

11. Tear down the stack.

```bash
docker compose down
```

Expected output:
```
[+] Running 5/5
 ✔ Container network-demo-proxy-1 Removed
 ✔ Container network-demo-app-1   Removed
 ✔ Container network-demo-db-1    Removed
 ✔ Network network-demo_frontend  Removed
 ✔ Network network-demo_backend   Removed
```

---

## Common Pitfalls

### Pitfall 1: Using the Default Bridge Network for Inter-Container Communication

**Description:** Containers on the default bridge cannot resolve each other by name. Developers who connect services by IP address instead find that IP addresses change on every container restart, causing silent connection failures.

**Why it happens:** Containers join the default bridge automatically without any `--network` flag, making it the path of least resistance. The DNS limitation is not obvious until a service restart breaks everything.

**Incorrect pattern:**
```bash
docker run -d --name db postgres:16-alpine
docker run -d --name api -e DB_HOST=172.17.0.2 myapi:1.0.0
# 172.17.0.2 changes after "docker rm db && docker run db"
```

**Correct pattern:**
```bash
docker network create app-net
docker run -d --name db --network app-net postgres:16-alpine
docker run -d --name api --network app-net -e DB_HOST=db myapi:1.0.0
# "db" resolves correctly by name even after restarts
```

---

### Pitfall 2: Publishing a Database Port to 0.0.0.0

**Description:** Running a database with `-p 5432:5432` (no host IP specified) binds the port to all network interfaces, potentially exposing the database to the LAN or internet if the host's firewall is not carefully configured.

**Why it happens:** The default binding to `0.0.0.0` requires no extra typing. The security implication is invisible — the container works perfectly and no warning is issued.

**Incorrect pattern:**
```bash
# Reachable from any host that can reach this machine's port 5432
docker run -d --name db -p 5432:5432 postgres:16-alpine
```

**Correct pattern:**
```bash
# Only reachable from the local machine
docker run -d --name db -p 127.0.0.1:5432:5432 postgres:16-alpine
```

---

### Pitfall 3: Confusing EXPOSE with --publish

**Description:** A developer adds `EXPOSE 8080` to a Dockerfile and assumes the port is now accessible from the host. It is not — `EXPOSE` is documentation only.

**Why it happens:** The word "expose" strongly implies making something accessible. The distinction between documentation (`EXPOSE`) and runtime port mapping (`-p`) is not intuitive.

**Incorrect assumption:**
```dockerfile
# Developer thinks this makes port 8080 accessible from the host
FROM node:22-slim
WORKDIR /app
COPY . .
EXPOSE 8080
CMD ["node", "server.js"]
```
```bash
docker run -d myapp:1.0.0
curl http://localhost:8080  # Connection refused
```

**Correct pattern:**
```bash
# -p creates the actual host-to-container port mapping at runtime
docker run -d -p 8080:8080 myapp:1.0.0
curl http://localhost:8080  # Works
```

---

### Pitfall 4: Subnet Conflicts with VPNs or Corporate Networks

**Description:** Docker automatically assigns subnets for new networks from a default pool that includes ranges like `172.17.0.0/16`, `172.18.0.0/16`, etc. If your VPN or corporate network uses an overlapping subnet, container traffic intended for the Docker network gets routed to the VPN, and VPN traffic may break entirely.

**Why it happens:** Docker's automatic subnet assignment picks available ranges from the host's perspective, but it cannot know about VPN routes that are not yet active when the network is created.

**Incorrect pattern:**
```bash
# Docker assigns 172.17.0.0/16 — conflicts with VPN that uses 172.16.0.0/12
docker network create app-net
```

**Correct pattern:**
```bash
# Explicitly specify a subnet that does not conflict with known ranges
docker network create --subnet 192.168.200.0/24 app-net
```

Or in `compose.yaml`:
```yaml
networks:
  app-net:
    ipam:
      config:
        - subnet: 192.168.200.0/24
```

---

### Pitfall 5: Forgetting That `internal: true` Also Blocks Outbound Traffic

**Description:** A developer marks a network `internal: true` to prevent external services from reaching a database, but the application on that network also needs to download packages or reach an external API during startup. Both inbound and outbound connections are blocked.

**Why it happens:** `internal: true` sounds like it means "internal-facing" (no inbound exposure), but it actually means "no routing to/from external networks" in either direction.

**Incorrect pattern:**
```yaml
services:
  worker:
    image: myworker:1.0.0
    # worker.py downloads ML model from HuggingFace on startup — this will fail
    networks:
      - data-processing

networks:
  data-processing:
    internal: true
```

**Correct pattern:** Only use `internal: true` on networks whose members never need external internet access. Keep internet-facing services on a non-internal network.

---

### Pitfall 6: Overlay Networks Without Required Firewall Ports

**Description:** A developer initializes a Docker Swarm, creates an overlay network, and deploys services — but containers on different nodes cannot communicate. The network appears to be set up correctly, but packets never arrive.

**Why it happens:** Overlay networking requires three specific ports to be open between all participating hosts. Cloud security groups and firewalls block these by default.

**Incorrect pattern:**
Deploying an overlay stack without verifying that ports 2377/tcp, 4789/udp, and 7946/tcp+udp are open between all Swarm nodes.

**Correct pattern:**
Before initializing a Swarm, verify or configure security group / firewall rules:
```bash
# On Linux hosts using ufw, allow the required Swarm ports
ufw allow 2377/tcp
ufw allow 4789/udp
ufw allow 7946
```
Then verify connectivity between hosts before deploying services.

---

### Pitfall 7: Expecting `--network host` to Work on Docker Desktop

**Description:** A developer uses `--network host` on Docker Desktop for Mac or Windows, expecting the container to share the host's physical network interfaces. The container instead shares the network of the Linux VM Docker Desktop runs in, not the developer's laptop network.

**Why it happens:** Docker Desktop on macOS and Windows runs containers inside a Linux VM for kernel compatibility. `--network host` refers to that VM's host, not the physical machine. This is a documented limitation but easily missed.

**Correct pattern:** On Docker Desktop, use port publishing (`-p`) for any port that needs to be reachable from the developer's host machine. Reserve `--network host` for Linux hosts where it works as expected.

---

## Summary

- Docker's Container Network Model (CNM) defines three abstractions — sandboxes, endpoints, and networks — implemented by pluggable drivers that handle actual packet forwarding.
- The six built-in drivers each solve a distinct problem: bridge for single-host isolation, host for maximum performance with no isolation, overlay for multi-host Swarm deployments, macvlan and ipvlan for physical-network integration, and none for complete isolation.
- The most important practical distinction is between the **default bridge** (no DNS, IP-only communication) and **user-defined bridges** (automatic DNS resolution by container name, scoped isolation). Always use user-defined networks for multi-container workloads.
- `EXPOSE` in a Dockerfile is documentation only; `--publish` / `-p` at runtime creates actual port mappings. Bind to `127.0.0.1` for services that do not need to be reachable externally.
- Docker Compose manages networks automatically: it creates a default network per stack, supports custom multi-network topologies, allows external network references, and enables aliases — all declared in `compose.yaml` with no manual `docker network create` calls needed.
- Network security follows the principle of least privilege: give each service access to only the networks it needs, use `internal: true` to block outbound internet on backend-only networks, and avoid publishing ports that are only consumed by other containers.

---

## Further Reading

- [Docker Networking Overview — Official Docs](https://docs.docker.com/engine/network/) — The canonical starting point for all Docker networking topics, covering every driver with usage guidance and links to driver-specific deep dives; bookmark this as the authoritative reference for this module's content.
- [Bridge Network Driver — Official Docs](https://docs.docker.com/engine/network/drivers/bridge/) — In-depth coverage of the bridge driver including the complete comparison between default and user-defined bridges, configuration options such as MTU and subnet, and IPv6 bridge setup.
- [Overlay Network Driver — Official Docs](https://docs.docker.com/engine/network/drivers/overlay/) — Official documentation for overlay networking including Swarm initialization requirements, `--attachable` flag behavior, per-network encryption with `--opt encrypted`, and Windows limitations.
- [Macvlan Network Driver — Official Docs](https://docs.docker.com/engine/network/drivers/macvlan/) — Detailed guide to macvlan bridge mode and 802.1Q VLAN trunking, including kernel version requirements, promiscuous mode considerations, and comparison with ipvlan for MAC-constrained environments.
- [Port Publishing and Mapping — Official Docs](https://docs.docker.com/engine/network/port-publishing/) — Complete reference for the `-p` flag syntax covering all forms: host-IP binding, protocol specification, and daemon-level default binding configuration for production hardening.
- [Networking in Docker Compose — Official Docs](https://docs.docker.com/compose/how-tos/networking/) — Authoritative guide to Compose network behavior: default network creation, custom network topologies, external networks, network aliases via `links`, and static IP assignment.
- [Docker Compose Networks Reference — Official Docs](https://docs.docker.com/reference/compose-file/networks/) — The full Compose file specification for the `networks` top-level element and per-service `networks` key, covering every option including `ipam`, `internal`, `external`, `labels`, and `driver_opts`.
- [Docker Security Best Practices — Wiz Academy](https://www.wiz.io/academy/container-security/docker-container-security-best-practices) — A practitioner-oriented checklist covering network isolation, privilege reduction, image hardening, and runtime monitoring; useful for understanding the broader security context in which network isolation practices sit.
