#!/usr/bin/env bash
set -e

echo "1. Spinning up 6 Valkey nodes using Docker Compose..."
docker compose up -d

echo "2. Waiting 5 seconds for nodes to initialize..."
sleep 5

echo "3. Bootstrapping Valkey Cluster (3 Masters, 3 Replicas)..."
# We run the cluster creation command inside valkey-node-1
# Using static IP addresses of the containers on the custom bridge network.
# --cluster-replicas 1 means every master node will get 1 replica.
docker exec valkey-node-1 valkey-cli --cluster create \
  172.20.0.11:6379 \
  172.20.0.12:6379 \
  172.20.0.13:6379 \
  172.20.0.14:6379 \
  172.20.0.15:6379 \
  172.20.0.16:6379 \
  --cluster-replicas 1 \
  --cluster-yes

echo ""
echo "=========================================================="
echo " Valkey Cluster has been successfully created!"
echo "=========================================================="
echo "Port Mappings for Host Access:"
echo " - Node 1 (Master A): 127.0.0.1:7001"
echo " - Node 2 (Master B): 127.0.0.1:7002"
echo " - Node 3 (Master C): 127.0.0.1:7003"
echo " - Node 4 (Replica A): 127.0.0.1:7004"
echo " - Node 5 (Replica B): 127.0.0.1:7005"
echo " - Node 6 (Replica C): 127.0.0.1:7006"
echo "=========================================================="
echo "Check cluster state with:"
echo "  docker exec valkey-node-1 valkey-cli cluster info"
echo "  docker exec valkey-node-1 valkey-cli cluster nodes"
echo "=========================================================="
