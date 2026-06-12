#!/usr/bin/env python3
import time
import valkey

def main():
    # Connect to local Valkey server. Since Valkey is a drop-in fork,
    # it runs on port 6379 by default, exactly like Redis.
    print("Connecting to Valkey server at localhost:6379...")
    client = valkey.Valkey(host='localhost', port=6379, decode_responses=True)
    
    # Check connection
    try:
        if client.ping():
            print("Connected successfully!\n")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    # Clear previous keys from this test namespace
    print("Clearing previous keys in namespace 'tutorial:*'...")
    keys_to_del = client.keys("tutorial:*")
    if keys_to_del:
        client.delete(*keys_to_del)
    
    # =========================================================================
    # 1. STRINGS (Key-Value)
    # Conventional Usage: Caching, session store, counters.
    # Key Naming Convention: namespace:object_type:id:field
    # =========================================================================
    print("--- 1. STRINGS ---")
    user_id = "1001"
    # Key encoding recommendation: Use structured, human-readable ASCII keys.
    # Colons (:) act as namespaces.
    key_str = f"tutorial:user:{user_id}:email"
    
    # Set a string value
    client.set(key_str, "alice@example.com")
    print(f"SET {key_str} -> alice@example.com")
    
    # Get a string value
    email = client.get(key_str)
    print(f"GET {key_str} -> {email}")
    
    # Atomic counter (great for page views, rate limiters, etc.)
    counter_key = f"tutorial:user:{user_id}:views"
    client.incr(counter_key)
    client.incr(counter_key)
    views = client.get(counter_key)
    print(f"INCR {counter_key} twice -> {views}")
    
    # Expiring Key (Time to Live / TTL)
    temp_key = f"tutorial:temp:session:{user_id}"
    client.set(temp_key, "active_session_token", ex=5)  # Expires in 5 seconds
    print(f"SET {temp_key} with TTL of 5s.")
    print(f"TTL of {temp_key}: {client.ttl(temp_key)}s")
    
    # =========================================================================
    # 2. HASHES (Objects / Dictionaries)
    # Conventional Usage: Storing objects with fields and values.
    # Saves memory compared to multiple individual strings.
    # =========================================================================
    print("\n--- 2. HASHES ---")
    hash_key = f"tutorial:user:{user_id}:profile"
    
    client.hset(hash_key, mapping={
        "username": "alice_dev",
        "role": "admin",
        "signup_year": "2026"
    })
    print(f"HSET {hash_key} (username, role, signup_year)")
    
    # Get specific fields
    role = client.hget(hash_key, "role")
    print(f"HGET {hash_key} role -> {role}")
    
    # Get all fields
    profile = client.hgetall(hash_key)
    print(f"HGETALL {hash_key} -> {profile}")
    
    # =========================================================================
    # 3. LISTS (Ordered Collections / Queue)
    # Conventional Usage: Message queues, recent task lists, activity feeds.
    # =========================================================================
    print("\n--- 3. LISTS (Queues) ---")
    queue_key = "tutorial:task_queue"
    
    # Push items into the queue (Left-Push)
    client.lpush(queue_key, "task_A")
    client.lpush(queue_key, "task_B")
    client.lpush(queue_key, "task_C")
    print(f"LPUSH {queue_key} -> task_A, task_B, task_C")
    
    # Read list length
    length = client.llen(queue_key)
    print(f"LLEN {queue_key} -> {length}")
    
    # Retrieve range of items (without removing them)
    items = client.lrange(queue_key, 0, -1)
    print(f"LRANGE {queue_key} 0 -1 (entire list) -> {items}")
    
    # Pop items (Right-Pop / FIFO queue behavior)
    popped = client.rpop(queue_key)
    print(f"RPOP {queue_key} -> {popped}")
    print(f"Remaining items -> {client.lrange(queue_key, 0, -1)}")
    
    # =========================================================================
    # 4. SETS (Unordered Unique Collections)
    # Conventional Usage: Storing tags, unique visitor IPs, social connections.
    # =========================================================================
    print("\n--- 4. SETS (Unique lists) ---")
    set_key = f"tutorial:user:{user_id}:tags"
    
    # Add elements (duplicates are ignored)
    client.sadd(set_key, "developer", "gamer", "writer", "developer")
    print(f"SADD {set_key} -> 'developer', 'gamer', 'writer', 'developer' (duplicate)")
    
    # Get size and members
    print(f"SCARD {set_key} (Set Cardinality) -> {client.scard(set_key)}")
    print(f"SMEMBERS {set_key} -> {client.smembers(set_key)}")
    
    # Check membership
    is_gamer = client.sismember(set_key, "gamer")
    is_designer = client.sismember(set_key, "designer")
    print(f"SISMEMBER 'gamer' -> {is_gamer}")
    print(f"SISMEMBER 'designer' -> {is_designer}")
    
    # =========================================================================
    # 5. SORTED SETS (ZSET - Ranked Lists)
    # Conventional Usage: Leaderboards, rate limiters, priority queues.
    # Elements are ordered by their associated floating-point score.
    # =========================================================================
    print("\n--- 5. SORTED SETS (Leaderboards) ---")
    zset_key = "tutorial:leaderboard"
    
    client.zadd(zset_key, {
        "UserBob": 1500,
        "UserAlice": 2300,
        "UserCharlie": 1200,
        "UserDave": 1850
    })
    print(f"ZADD {zset_key} (Bob:1500, Alice:2300, Charlie:1200, Dave:1850)")
    
    # Retrieve range by score / rank (ordered from lowest to highest)
    leaderboard = client.zrange(zset_key, 0, -1, withscores=True)
    print(f"ZRANGE {zset_key} 0 -1 (Ascending) -> {leaderboard}")
    
    # Retrieve reverse range (highest score to lowest - typical leaderboard)
    top_leaderboard = client.zrange(zset_key, 0, -1, desc=True, withscores=True)
    print(f"ZRANGE {zset_key} 0 -1 DESC (Descending) -> {top_leaderboard}")
    
    # Get Bob's rank and score
    bob_score = client.zscore(zset_key, "UserBob")
    bob_rank = client.zrevrank(zset_key, "UserBob")  # 0-indexed rank from top
    print(f"Bob's Score: {bob_score}, Bob's Rank: {bob_rank + 1} (1st place is Rank 1)")

if __name__ == "__main__":
    main()
