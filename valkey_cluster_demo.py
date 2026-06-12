#!/usr/bin/env python3
import valkey
from valkey.exceptions import ResponseError, ValkeyClusterException

def main():
    # Connect using the smart client (ValkeyCluster).
    # We only need to provide one or more startup nodes; the smart client
    # will query the node for the full cluster topology and route commands automatically.
    print("Connecting to Valkey Cluster using the Smart Client...")
    try:
        cluster = valkey.ValkeyCluster(host='172.20.0.11', port=6379, decode_responses=True)
        print("Connected to Cluster successfully!\n")
    except Exception as e:
        print(f"Failed to connect to cluster: {e}")
        return

    # Print cluster nodes topology
    print("=== Cluster Node Topology ===")
    nodes_info = cluster.cluster_nodes()
    for addr, info in nodes_info.items():
        role = "master" if "master" in info['flags'] else "replica"
        print(f"Node: {addr:<18} | ID: {info['node_id'][:8]}... | Role: {role:<7} | Slots: {info.get('slots', 'none')}")
    print("=============================\n")

    # =========================================================================
    # 1. DATA SHARDING & HASH SLOTS
    # =========================================================================
    print("--- 1. DATA SHARDING & HASH SLOTS ---")
    keys = ["apple", "banana", "cherry", "date", "fig", "grape"]
    
    for key in keys:
        # Determine the hash slot for the key (CRC16 of key % 16384)
        slot = cluster.keyslot(key)
        
        # Write the key using the smart client
        cluster.set(key, f"val_{key}")
        
        # The smart client automatically resolves which node owns the slot.
        # Let's inspect where it sent the key.
        node = cluster.nodes_manager.get_node_from_slot(slot)
        print(f"Key '{key:<6}' -> Hash Slot: {slot:>5} -> Stored on node: {node.host}:{node.port}")
    
    # =========================================================================
    # 2. SMART CLIENT REDIRECTIONS (-MOVED)
    # =========================================================================
    print("\n--- 2. SMART CLIENT REDIRECTIONS (-MOVED) ---")
    print("What happens if we use a standard (non-cluster) client to connect to a single node?")
    print("Let's connect to Node 1 (172.20.0.11) directly using a normal Valkey client:")
    
    single_node_client = valkey.Valkey(host="172.20.0.11", port=6379, decode_responses=True)
    
    # We will try to read/write keys that may or may not belong to Node 1.
    for key in ["apple", "banana"]:
        slot = cluster.keyslot(key)
        target_node = cluster.nodes_manager.get_node_from_slot(slot)
        
        print(f"\nTargeting key '{key}' (Slot {slot}, owned by {target_node.host}:{target_node.port})...")
        try:
            # Attempt to GET key from Node 1 (172.20.0.11)
            val = single_node_client.get(key)
            print(f"Success! Retrieved key '{key}' value: '{val}' from 172.20.0.11")
        except ResponseError as err:
            # If the key belongs to another node, the single node returns a -MOVED error
            print(f"Error caught: {err}")
            print("Explanation: The node returned a -MOVED redirection indicating where the slot resides.")

    # =========================================================================
    # 3. MULTI-KEY OPERATIONS & HASH TAGS
    # =========================================================================
    print("\n--- 3. MULTI-KEY OPERATIONS & HASH TAGS ---")
    print("Multi-key operations (like MSET/MGET or transactions) require all keys to reside in the SAME hash slot.")
    
    key_a = "user:1001:name"
    key_b = "user:1001:email"
    
    slot_a = cluster.keyslot(key_a)
    slot_b = cluster.keyslot(key_b)
    
    print(f"key_a: '{key_a}' -> Slot {slot_a}")
    print(f"key_b: '{key_b}' -> Slot {slot_b}")
    
    print("Attempting MSET on keys with different slots:")
    try:
        cluster.mset({key_a: "Alice", key_b: "alice@example.com"})
        print("MSET Succeeded!")
    except (ValkeyClusterException, ResponseError) as err:
        print(f"Error caught: {err}")
        print("Explanation: Valkey Cluster blocks multi-key operations if they hash to different nodes (CROSSSLOT error).")

    print("\nSolving it with HASH TAGS { ... }:")
    # By wrapping part of the key in braces, Valkey only hashes the content inside the braces.
    tagged_key_a = "{user:1001}:name"
    tagged_key_b = "{user:1001}:email"
    
    tagged_slot_a = cluster.keyslot(tagged_key_a)
    tagged_slot_b = cluster.keyslot(tagged_key_b)
    
    print(f"tagged_key_a: '{tagged_key_a}' -> Slot {tagged_slot_a}")
    print(f"tagged_key_b: '{tagged_key_b}' -> Slot {tagged_slot_b}")
    
    print("Attempting MSET on keys with the same Hash Tag:")
    try:
        cluster.mset({tagged_key_a: "Alice", tagged_key_b: "alice@example.com"})
        print("MSET Succeeded!")
        print(f"Retrieved values: {cluster.mget(tagged_key_a, tagged_key_b)}")
    except Exception as err:
        print(f"Failed: {err}")

    # Clean up keys
    print("\nCleaning up keys...")
    for key in keys:
        cluster.delete(key)
    cluster.delete(tagged_key_a, tagged_key_b)
    print("Done!")

if __name__ == "__main__":
    main()
