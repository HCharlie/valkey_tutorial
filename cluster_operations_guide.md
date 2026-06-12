# Valkey & Redis Cluster Operations Guide

This guide describes how to interact with, manage, and operate a Valkey/Redis Cluster. It covers data command sets (Strings, Hashes, Lists, Sets, ZSets), administrative inspection commands, and recommendations on when to use each.

---

## 1. Connecting to the Cluster
How you connect to the cluster determines how commands are processed.

### A. Cluster Mode (`-c`)
Always use the `-c` flag for daily database operations. It enables client-side redirection. If you request a key residing on a different node, the server returns `-MOVED`, and the CLI client automatically reconnects to the correct node to fetch the data.
```bash
docker exec -it valkey-node-1 valkey-cli -c
```
> [!NOTE]
> **When to use**: Reading, writing, or deleting keys, testing application query patterns, and running multi-key commands.

### B. Single-Node Mode (No `-c`)
Connects you directly to a specific container's keyspace. If you query a key belonging to another node's hash slot, the operation fails with a `(error) MOVED ...` response.
```bash
docker exec -it valkey-node-1 valkey-cli
```
> [!NOTE]
> **When to use**: Querying node-specific metrics, checking local key distribution, debugging replication issues, or viewing a node's local configuration.

---

## 2. Cluster Administration & Monitoring Commands

Use these commands to check the state, topology, and performance of the cluster.

| Command | Usage | When to Use / Best Practices |
| :--- | :--- | :--- |
| **`CLUSTER INFO`** | `CLUSTER INFO` | **Check Cluster Health**: Verifies that `cluster_state` is `ok` and all 16,384 slots are assigned. Run during health checks or when failovers are suspected. |
| **`CLUSTER NODES`** | `CLUSTER NODES` | **Inspect Topology Map**: Returns the list of all nodes, their roles (`master`/`replica`), links, failover states, and assigned slot ranges. Excellent for debugging routing issues. |
| **`INFO REPLICATION`** | `INFO REPLICATION` | **Verify Replication Status**: Tells you if a node is currently a master or replica, its offset lag, and connection status to its peer. Check this on replicas to verify they are sync'd. |
| **`CLUSTER KEYSLOT <key>`** | `CLUSTER KEYSLOT user:1` | **Dry-Run Slot Hashing**: Shows which hash slot (0-16383) a specific key maps to without reading/writing the key. Used to verify Hash Tag structures. |
| **`KEYS <pattern>`** | `KEYS *` | **Local Key Listing (CAUTION)**: Lists all keys matching a pattern. **WARNING**: In a cluster, it only searches the node you are connected to. Never run `KEYS *` in production (it blocks the single-threaded server thread). Use `SCAN` instead. |

---

## 3. Data Manipulation Commands

### A. Strings (Basic Key-Value & Counters)
Strings are the most basic data type, binary-safe, and capped at 512MB.

| Command | Syntax | When to Use |
| :--- | :--- | :--- |
| **`SET`** | `SET key value [EX seconds]` | Storing configuration, user sessions, or caching DB queries. Always include `EX` (Expiration) for transient cache data to prevent memory bloat. |
| **`GET`** | `GET key` | Fetching a string value. Very fast (`O(1)`). |
| **`DEL`** | `DEL key` | Deleting a key. Runs in `O(1)` for strings. |
| **`EXISTS`** | `EXISTS key` | Check if a key exists before running expensive logic. |
| **`INCR` / `DECR`** | `INCR page:views` | Atomic counters (page views, rate limiting windows). Avoids race conditions. |

---

### B. Hashes (Objects)
Hashes represent flat maps/objects. They are memory-efficient because Valkey optimizes small hashes using `ziplists` / `listpacks`.

```text
Syntax: HSET <key> <field> <value>
```

| Command | Syntax | When to Use |
| :--- | :--- | :--- |
| **`HSET`** | `HSET user:101 name "Alice" age 30` | Storing structured objects (e.g. user profile details, product listings). Better than storing a JSON string if you need to update individual fields. |
| **`HGET`** | `HGET user:101 name` | Retrieving a single field of an object. |
| **`HMGET`** | `HMGET user:101 name age` | **Multi-field retrieval**: Fetching multiple specific fields in one round-trip (better performance than individual HGETs). |
| **`HGETALL`** | `HGETALL user:101` | **Get entire object**: Returns all fields and values. **Caution**: If a hash has thousands of fields, `HGETALL` can block the server. Use `HSCAN` for large hashes. |
| **`HDEL`** | `HDEL user:101 age` | Deleting specific fields from the object. |

---

### C. Lists (Queues / Stacks)
Lists are ordered collections of strings. They are implemented as linked lists, making insertion/deletion at the ends extremely fast (`O(1)`).

| Command | Syntax | When to Use |
| :--- | :--- | :--- |
| **`LPUSH`** / **`RPUSH`** | `LPUSH tasks "job_id_5"` | Adding items to the start (Left) or end (Right) of a queue. Used for background job queuing. |
| **`LPOP`** / **`RPOP`** | `RPOP tasks` | Removing items. Combine `LPUSH` and `RPOP` to build a First-In-First-Out (FIFO) queue. |
| **`LRANGE`** | `LRANGE tasks 0 9` | Getting a slice of the list. Excellent for retrieving "recent activity feeds" or pagination. |

---

### D. Sets (Unordered Unique Collections)
Sets are unordered collections of unique elements.

| Command | Syntax | When to Use |
| :--- | :--- | :--- |
| **`SADD`** | `SADD user:101:roles "admin" "editor"` | Storing unique identifiers, e.g. user tags, online user IDs, IP addresses. Duplicates are ignored. |
| **`SISMEMBER`** | `SISMEMBER user:101:roles "admin"` | Checking if an element exists. Runs in `O(1)` time. |
| **`SMEMBERS`** | `SMEMBERS user:101:roles` | Getting all items. Do not use on massive sets (millions of items); use `SSCAN`. |

---

### E. Sorted Sets (ZSET - Ordered by Score)
ZSets are collections of unique strings where every member is associated with a floating-point score. Members are ordered from lowest to highest score.

| Command | Syntax | When to Use |
| :--- | :--- | :--- |
| **`ZADD`** | `ZADD leaderboard 1500 "UserA"` | Leaderboards, rate limiters, or priority queues. |
| **`ZRANGE`** | `ZRANGE leaderboard 0 2 REV WITHSCORES` | Getting ranked slices. `REV` gets high scores first. `WITHSCORES` returns scores alongside members. |

---

## 4. Multi-Key Operations in a Cluster (The CROSSSLOT Rule)
In a cluster environment, operations that involve multiple keys (like `MGET`, `MSET`, `SINTER`, or `MULTI`/`EXEC` transactions) are only allowed if **all target keys map to the exact same hash slot**.

If you run:
```text
MSET user:1:name "Bob" user:2:name "Alice"
```
It will fail with: `(error) CROSSSLOT Keys in request don't hash to the same slot`.

### The Solution: Hash Tags
Force keys to reside on the same slot by wrapping the common identifier in curly braces `{...}`:
```text
MSET {user:1}:name "Bob" {user:1}:email "bob@example.com"
```
* Valkey only hashes `user:1` when calculating the slot.
* Both keys land on the same node, allowing transactions and multi-key commands to execute atomically.

---

## 5. Replica Promotion & Automatic Failover

Valkey handles primary node crashes and recovers without downtime using decentralized consensus.

### Live Failover Walkthrough (How it Works)
1. **Primary Node Crashes**: 
   When a master node (e.g. `valkey-node-1`) stops responding, peer master nodes detect its absence.
   ```bash
   docker stop valkey-node-1
   ```
2. **Failure Detection**: 
   Once the master node remains unreachable for the duration of `cluster-node-timeout` (e.g. 5000ms), it is marked as `FAIL` by the majority of masters.
3. **Replica Promotion**: 
   The failed master's replica (e.g. `valkey-node-5`) registers the failure, starts a failover election, gathers votes from other masters, and promotes itself to **Master**. It immediately takes ownership of the hash slots (e.g. `0-5460`).
   ```bash
   # Checking nodes output shows replica now flagged as master
   docker exec valkey-node-2 valkey-cli cluster nodes
   ```
4. **Primary Recovery & Failback**: 
   When the crashed node returns, it detects that its replica has taken over. It automatically transitions to a **Replica** of the new Master to prevent split-brain conflicts.
   ```bash
   docker start valkey-node-1
   ```

---

## 6. Accessing Replicas & Read Scaling

Replicas mirror masters. You can access replicas when the primary node is healthy, but there are rules for doing so:

### The Redirection Rule (Default Behavior)
By default, if you connect to a replica node and run a read command (e.g. `GET key`), the replica calculates the hash slot. If the slot is owned by a master, the replica returns a `MOVED` redirection.
```text
# Querying replica Node 6
docker exec valkey-node-6 valkey-cli GET cherry
(error) MOVED 6259 172.20.0.12:6379
```

### Read Scaling with `READONLY`
To scale read capacity, you can read from replicas by disabling the automatic redirection. To do this, you must run the **`READONLY`** command.

* **Step 1: Open session and run `READONLY`**
  ```text
  127.0.0.1:6379> READONLY
  OK
  ```
* **Step 2: Read key**
  ```text
  127.0.0.1:6379> GET cherry
  "delicious"
  ```

> [!WARNING]
> * **Writes will still fail**: Even in `READONLY` mode, any write commands (e.g. `SET`, `HSET`) sent to a replica will fail with `(error) READONLY You can't write against a read only replica`.
> * **Eventual Consistency**: Replicas are asynchronously updated. Reading from replicas can result in reading slightly outdated data if the replica has not finished copying recent writes from the master.
> * **Restore default behavior**: Run `READWRITE` on the client connection to restore the default redirection behavior.
