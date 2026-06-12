#!/usr/bin/env python3
import time
import valkey
import numpy as np
import matplotlib.pyplot as plt

def run_benchmark(client, num_ops=5000):
    results = {}
    
    # Pre-clean benchmark keys
    bench_keys = client.keys("bench:*")
    if bench_keys:
        client.delete(*bench_keys)
    
    # -------------------------------------------------------------
    # 1. Benchmark String SET (Individual round-trips)
    # -------------------------------------------------------------
    print(f"Running SET benchmark ({num_ops} ops)...")
    latencies_set = []
    start_time = time.perf_counter()
    for i in range(num_ops):
        op_start = time.perf_counter()
        client.set(f"bench:str:{i}", f"val_{i}")
        latencies_set.append((time.perf_counter() - op_start) * 1000)  # ms
    total_time_set = time.perf_counter() - start_time
    ops_set = num_ops / total_time_set
    results['SET'] = {
        'total_time_s': total_time_set,
        'ops': ops_set,
        'latencies': latencies_set
    }

    # -------------------------------------------------------------
    # 2. Benchmark String GET (Individual round-trips)
    # -------------------------------------------------------------
    print(f"Running GET benchmark ({num_ops} ops)...")
    latencies_get = []
    start_time = time.perf_counter()
    for i in range(num_ops):
        op_start = time.perf_counter()
        client.get(f"bench:str:{i}")
        latencies_get.append((time.perf_counter() - op_start) * 1000)  # ms
    total_time_get = time.perf_counter() - start_time
    ops_get = num_ops / total_time_get
    results['GET'] = {
        'total_time_s': total_time_get,
        'ops': ops_get,
        'latencies': latencies_get
    }

    # -------------------------------------------------------------
    # 3. Benchmark String SET Pipelined (Batch processing)
    # Pipelining batches commands to reduce network RTT (Round Trip Time).
    # -------------------------------------------------------------
    print(f"Running SET Pipelined benchmark ({num_ops} ops)...")
    start_time = time.perf_counter()
    pipe = client.pipeline(transaction=False)
    
    # Measure total pipeline build + execution
    op_start = time.perf_counter()
    for i in range(num_ops):
        pipe.set(f"bench:pipe:{i}", f"val_{i}")
    pipe.execute()
    total_time_pipe_set = time.perf_counter() - start_time
    ops_pipe_set = num_ops / total_time_pipe_set
    # Average latency per operation in pipeline
    avg_lat_pipe = (total_time_pipe_set / num_ops) * 1000
    results['SET (Pipelined)'] = {
        'total_time_s': total_time_pipe_set,
        'ops': ops_pipe_set,
        'latencies': [avg_lat_pipe] * num_ops  # Distributed latency representation
    }

    # Clean up benchmark keys
    bench_keys = client.keys("bench:*")
    if bench_keys:
        client.delete(*bench_keys)
    
    return results

def print_report(results):
    print("\n" + "="*70)
    print("                    VALKEY BENCHMARK REPORT")
    print("="*70)
    print(f"{'Operation':<20} | {'Throughput':<15} | {'Avg Latency':<12} | {'p95 Latency':<12}")
    print("-"*70)
    
    for op, data in results.items():
        latencies = data['latencies']
        avg_lat = np.mean(latencies)
        p95_lat = np.percentile(latencies, 95)
        print(f"{op:<20} | {data['ops']:>10.1f} OPS | {avg_lat:>9.3f} ms | {p95_lat:>9.3f} ms")
    print("="*70)

def plot_results(results):
    # Plot bar chart for Throughput (OPS)
    ops_values = [data['ops'] for data in results.values()]
    operations = list(results.keys())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # 1. Throughput (Higher is better)
    colors = ['#4F46E5', '#06B6D4', '#10B981']
    bars = ax1.bar(operations, ops_values, color=colors, edgecolor='none', width=0.5)
    ax1.set_title('Throughput (Operations per Second)', fontsize=14, fontweight='bold', pad=15)
    ax1.set_ylabel('OPS (Higher = Better)', fontsize=12)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    
    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax1.annotate(f'{height:.0f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

    # 2. Latency comparison (excluding pipeline distribution to prevent skewed comparison)
    individual_ops = ['SET', 'GET']
    avg_latencies = [np.mean(results[op]['latencies']) for op in individual_ops]
    p95_latencies = [np.percentile(results[op]['latencies'], 95) for op in individual_ops]
    p99_latencies = [np.percentile(results[op]['latencies'], 99) for op in individual_ops]

    x = np.arange(len(individual_ops))
    width = 0.25

    ax2.bar(x - width, avg_latencies, width, label='Average', color='#06B6D4')
    ax2.bar(x, p95_latencies, width, label='95th Percentile', color='#4F46E5')
    ax2.bar(x + width, p99_latencies, width, label='99th Percentile', color='#EC4899')

    ax2.set_title('Latency Comparison (Individual Requests)', fontsize=14, fontweight='bold', pad=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(individual_ops)
    ax2.set_ylabel('Latency (ms - Lower = Better)', fontsize=12)
    ax2.legend()
    ax2.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    chart_path = 'benchmark_latency.png'
    plt.savefig(chart_path, dpi=300)
    print(f"\n[Chart Saved] Benchmark visualization chart saved to '{chart_path}'")

def main():
    print("Connecting to Valkey server at localhost:6379...")
    client = valkey.Valkey(host='localhost', port=6379, decode_responses=True)
    
    try:
        client.ping()
    except Exception as e:
        print(f"Failed to connect to local Valkey. Is it running? Error: {e}")
        return

    # Warm up connection pool
    client.ping()
    
    # Run benchmark with 10,000 operations (fast but statistically sound)
    results = run_benchmark(client, num_ops=10000)
    print_report(results)
    plot_results(results)

if __name__ == "__main__":
    main()
