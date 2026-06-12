# Valkey & Redis Learning Guide and Benchmark Report

This report summarizes the essential concepts of Valkey, key design best practices, local single-node performance benchmarks, and advanced clustering mechanics (Data Sharding, High Availability, Mesh Communication, and Smart Clients).

---

## 1. What is Valkey?
Valkey is a high-performance, open-source, in-memory key-value data store. It was established in March 2024 as a community-driven fork of **Redis 7.2.4** under the stewardship of the **Linux Foundation**.

> [!NOTE]
> Valkey was created after Redis Ltd. transitioned Redis to a proprietary license model. It is backed by AWS, Google, Oracle, Microsoft, and others, ensuring a fully open-source (BSD 3-Clause) community alternative.

* **Drop-in Compatibility**: Valkey is wire-compatible with Redis. It uses the same ports (`6379`), CLI commands, and RESP protocols.
* **Client Reuse**: You can use existing Redis SDKs (`redis-py`, `go-redis`, `ioredis`) to connect to Valkey without modifying your code.

---

## 2. Key Naming and Encoding Guidelines
Valkey keys are binary-safe (up to 512 MB). Adhering to conventions is critical for performance and code maintenance:

* **Namespace separator**: Use colons (`:`) to group keys hierarchical. E.g., `user:1001:profile`.
* **Descriptive but concise**: Storing long keys wastes memory. Avoid `user_profile_information_for_user_with_id_1001`. Use `user:1001:profile`.
* **Binary hashing for long keys**: If your key is naturally massive (like a full URL), hash it first (e.g., MD5/SHA256) and use the hash.
* **Avoid spaces**: Spaces make command-line tool usage and client parsing error-prone.

---

## 3. Local Single-Node Performance Benchmark Results
We executed a performance benchmark of 10,000 operations on your local machine using the Python environment targeting a standalone Valkey Docker container.

### Benchmark Data
| Operation | Total Ops | Throughput (OPS) | Avg Latency | 95th Percentile Latency |
| :--- | :--- | :--- | :--- | :--- |
| **SET** (Individual) | 10,000 | 9,924.1 | 0.101 ms | 0.121 ms |
| **GET** (Individual) | 10,000 | 9,242.6 | 0.108 ms | 0.120 ms |
| **SET** (Pipelined) | 10,000 | 219,033.5 | 0.005 ms | 0.005 ms |

> [!IMPORTANT]
> **Performance Insight**: Running Valkey inside Docker adds virtualized network interface overhead (latency increased from `~0.03ms` native to `~0.10ms` in Docker). 
> However, **Pipelined operations** completely bypass this overhead by batching network packets, maintaining an identical throughput of **~219k OPS** (`0.005ms` per operation). This makes pipelining even more essential in containerized environments (like Docker, Kubernetes, and Cloud deploys).

### Latency and Throughput Chart
![Valkey Benchmark Latencies](/Users/changli/.gemini/antigravity-cli/brain/cebbdb49-1aac-4047-8b2e-c81b56d52450/benchmark_latency.png)

---

## 4. Advanced Topic: Distributed Valkey Cluster

To scale beyond a single node, Valkey supports decentralized **Clustering**. We configured a local 6-node cluster (3 Masters, 3 Replicas) inside Docker to explore these architecture details:

### A. Data Sharding (Hash Slots)
Valkey Clusters do not shard keys randomly. Instead, the keyspace is partitioned into exactly **16,384 Hash Slots**.
* Every key `K` is assigned a slot via the calculation: `CRC16(K) % 16384`.
* Master nodes divide the slot ranges. For example:
  * Node 1 (Master A): Slots 0 - 5460
  * Node 2 (Master B): Slots 5461 - 10922
  * Node 3 (Master C): Slots 10923 - 16383
* This allows transparent horizontal scaling of storage capacity and throughput.

### B. High Availability (HA) & Automatic Failover
Each Master node has one or more Replica nodes mimicking its data in real time.
* If a Master node fails, the remaining Masters detect the outage via gossip messages, hold elections, and promote the replica to become the new Master.
* When the old Master recovers, it joins back as a Replica of the new Master.

### C. Mesh Gossip Communication (Cluster Bus)
Nodes communicate directly with one another over a **Cluster Bus** using a custom binary protocol (port = node client port + 10000). E.g., port `16379`.
* Gossip messages are sent continuously to share routing state, vote on failover promotion, and detect splits.
* There is **no load balancer** or proxy sitting in between nodes; the cluster represents a true decentralized mesh.

### D. Smart Clients (Cluster Aware)
Smart client SDKs (like `valkey.ValkeyCluster` in Python) automatically cache the slot topology map.
* **Routing**: The client hashes the key locally to determine the slot and routes the query directly to the correct node.
* **Redirection (`-MOVED`)**: If the client sends a query to the wrong node, the node returns a `-MOVED <slot> <target_address>` response. The smart client catches this error, updates its internal routing table, and retries the command without exposing the failure to the application code.

---

## 5. Multi-Key Operations and Hash Tags

Multi-key operations (like transaction `MULTI-EXEC` blocks, `MGET`, or `MSET`) require all target keys to belong to the **same hash slot**; otherwise, they fail with a `CROSSSLOT` error.

> [!TIP]
> **Hash Tags** solve this limitation. By placing a part of the key inside curly braces `{ ... }`, only the string inside the braces is hashed.
> * `user:1001:name` -> Slot 12650
> * `user:1001:email` -> Slot 11221
> * `{user:1001}:name` and `{user:1001}:email` -> Both map to **Slot 5712**. Since they share a slot, they are stored on the same node, enabling multi-key commands and atomic transactions!

### Demonstration Output (From Local Run)
```text
Connecting to Valkey Cluster using the Smart Client...
Connected to Cluster successfully!

=== Cluster Node Topology ===
Node: 172.20.0.12:6379   | ID: 039acdde... | Role: master  | Slots: [['5461', '10922']]
Node: 172.20.0.11:6379   | ID: 7c7e5b69... | Role: master  | Slots: [['0', '5460']]
Node: 172.20.0.13:6379   | ID: 104f1ad4... | Role: master  | Slots: [['10923', '16383']]
Node: 172.20.0.15:6379   | ID: 79001d60... | Role: replica | Slots: []
Node: 172.20.0.14:6379   | ID: 68f7d106... | Role: replica | Slots: []
Node: 172.20.0.16:6379   | ID: 7f976720... | Role: replica | Slots: []
=============================

--- 1. DATA SHARDING & HASH SLOTS ---
Key 'apple ' -> Hash Slot:  7092 -> Stored on node: 172.20.0.12:6379
Key 'banana' -> Hash Slot:  9380 -> Stored on node: 172.20.0.12:6379
Key 'cherry' -> Hash Slot:  6259 -> Stored on node: 172.20.0.12:6379
Key 'date  ' -> Hash Slot:  2022 -> Stored on node: 172.20.0.11:6379
Key 'fig   ' -> Hash Slot:  1080 -> Stored on node: 172.20.0.11:6379
Key 'grape ' -> Hash Slot:  2324 -> Stored on node: 172.20.0.11:6379

--- 2. SMART CLIENT REDIRECTIONS (-MOVED) ---
Let's connect to Node 1 (172.20.0.11) directly using a normal Valkey client:
Targeting key 'apple' (Slot 7092, owned by 172.20.0.12:6379)...
Error caught: MOVED 7092 172.20.0.12:6379
Explanation: The node returned a -MOVED redirection indicating where the slot resides.

--- 3. MULTI-KEY OPERATIONS & HASH TAGS ---
key_a: 'user:1001:name' -> Slot 12650
key_b: 'user:1001:email' -> Slot 11221
Attempting MSET on keys with different slots:
Error caught: MSET - all keys must map to the same key slot
Explanation: Valkey Cluster blocks multi-key operations if they hash to different nodes (CROSSSLOT error).

Solving it with HASH TAGS { ... }:
tagged_key_a: '{user:1001}:name' -> Slot 5712
tagged_key_b: '{user:1001}:email' -> Slot 5712
Attempting MSET on keys with the same Hash Tag:
MSET Succeeded!
Retrieved values: ['Alice', 'alice@example.com']
```

---

## 6. Learning Files Created in Your Workspace
The following files are available in your workspace [valkey_tutorial](file:///Users/changli/src/github.com/HCharlie/valkey_tutorial):
1. [docker-compose.yml](file:///Users/changli/src/github.com/HCharlie/valkey_tutorial/docker-compose.yml): The 6-node cluster Compose network setup.
2. [create_cluster.sh](file:///Users/changli/src/github.com/HCharlie/valkey_tutorial/create_cluster.sh): The shell script that orchestrates container startup and calls `--cluster create`.
3. [valkey_cluster_demo.py](file:///Users/changli/src/github.com/HCharlie/valkey_tutorial/valkey_cluster_demo.py): The Python cluster-aware demonstration code.
4. [README.md](file:///Users/changli/src/github.com/HCharlie/valkey_tutorial/README.md): Full walkthrough guide and command-line instructions.
