# Valkey & Redis End-to-End Tutorial

Welcome! This workspace is designed to help you master **Valkey** (and by extension, **Redis**) from basic usage up to advanced clustering concepts. It contains conceptual explanations, a cheatsheet for CLI commands, best practices for key encoding, hands-on Python scripts, and a performance benchmark.

---

## 1. What is Valkey?
**Valkey** is a high-performance, open-source, in-memory key-value data store. It was established in March 2024 as a community-driven fork of **Redis 7.2.4** under the stewardship of the **Linux Foundation**. 

### Why the Fork?
In March 2024, Redis Ltd. transitioned Redis from the open-source BSD 3-Clause license to a proprietary dual-license model (RSALv2 and SSPLv1). In response, a consortium of major tech companies (including AWS, Google Cloud, Oracle, Microsoft, and Ericsson) backed Valkey to ensure a fully open-source (BSD 3-Clause licensed), community-maintained alternative.

---

## 2. Valkey Server Running Environments

This workspace supports two server layouts using Docker:
1. **Single Node Instance**: Ideal for local development, caching, and basic learning.
2. **Distributed Cluster (6 Nodes)**: Ideal for learning advanced concepts like Data Sharding, High Availability (HA), Mesh Gossip communication, and Smart Clients.

### Layout 1: Running a Standalone Single Node
To start a single, stand-alone Valkey container:
```bash
docker run -d --name valkey-server -p 6379:6379 valkey/valkey:latest
```
* Stop it using: `docker stop valkey-server`
* CLI interactive access: `docker exec -it valkey-server valkey-cli`

### Layout 2: Running a Distributed Cluster (3 Masters, 3 Replicas)
We use a Docker Compose file (`docker-compose.yml`) containing 6 Valkey nodes assigned static IPs on a private bridge network (`valkey-cluster-net`).

To spin up and bootstrap the cluster automatically, run:
```bash
chmod +x create_cluster.sh
./create_cluster.sh
```
This script will start the containers and execute the `valkey-cli --cluster create` command to partition the 16,384 hash slots across the 3 master nodes and assign each master a failover replica.

* To verify cluster status:
  ```bash
  docker exec valkey-node-1 valkey-cli cluster info
  ```
* To view cluster topology:
  ```bash
  docker exec valkey-node-1 valkey-cli cluster nodes
  ```

---

## 3. Advanced Cluster Concepts Explained

### A. Data Sharding (Hash Slots)
Valkey Clusters partition the key space into exactly **16,384 Hash Slots**.
* When writing key `K`, the client calculates `CRC16(K) % 16384` to get the key's slot.
* The slots are divided among the master nodes. For example:
  * Node 1 (Master A): Slots 0 - 5460
  * Node 2 (Master B): Slots 5461 - 10922
  * Node 3 (Master C): Slots 10923 - 16383
* Sharding allows you to scale the database horizontally across multiple servers.

### B. High Availability (HA) & Failover
Every Master node is paired with a Replica (Slave) node that replicates its data.
* If a Master node (e.g., Master A) goes down, the remaining Master nodes run a consensus check and promote Replica A to become the new Master.
* When the old Master A recovers, it joins the cluster as a Replica of the new Master.

### C. Mesh Gossip Communication (Cluster Bus)
Valkey cluster nodes communicate directly with each other using a **Gossip Protocol** over a dedicated port offset by +10000 (e.g., port `16379` if the client port is `6379`).
* Nodes exchange health flags, failover voting, and slot migration status.
* This direct node-to-node communication creates a decentralized mesh with no single point of failure.

### D. Smart Clients (Cluster Aware)
A **Smart Client** (such as `ValkeyCluster` in Python) is cluster-aware:
1. On startup, it connects to any node and downloads the slot-to-node map (`CLUSTER SLOTS`).
2. When executing a command on key `K`, it computes the slot locally and sends the query directly to the owner node.
3. If the topology changes (e.g., a node fails or slots migrate) and a query reaches the wrong node, that node responds with a `-MOVED <slot> <new_ip:port>` redirection.
4. The Smart Client catches this error, updates its slot-to-node cache, and retries the command transparently.

---

## 4. Running the Hands-On Tutorials

### Step 1: Set up the Python Environment
Ensure you have activated the virtual environment:
```bash
source .venv/bin/activate
```

### Step 2: Run basic operations & benchmark
To test string, hash, list, set, and sorted set operations on the standalone server:
```bash
python valkey_basics.py
python valkey_benchmark.py
```

### Step 3: Run the Cluster-Aware Demo
Since the host computer cannot directly route to the internal private IP addresses of the Docker containers, we run the python demo inside a container attached to the `valkey-cluster-net` network:
```bash
docker run --rm --network valkey-cluster-net -v "$PWD":/app -w /app python:3.9-slim sh -c "pip install valkey && python valkey_cluster_demo.py"
```

This demo showcases:
1. **Routing**: Setting keys and watching which node gets assigned the slot.
2. **Redirection**: Demonstrating how a standard (non-cluster) client gets a `-MOVED` error when querying the wrong node.
3. **Hash Tags**: Explaining how multi-key operations (which require matching slots) fail, and how wrapping key namespaces in curly braces (e.g., `{user:1001}:profile` vs `{user:1001}:email`) forces them into the same slot to allow atomic bulk commands.
