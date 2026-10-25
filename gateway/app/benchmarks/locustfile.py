"""Locust load test for AgentWall gateway."""
import random

import gevent
from locust import HttpUser, between, events, task
from locust.env import Environment
from locust.stats import stats_printer


class AgentWallUser(HttpUser):
    """Simulated agent making tool calls through AgentWall."""

    wait_time = between(0.1, 0.5)  # 100-500ms between requests

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = None
        self.agent_id = None
        self.tools = [
            ("fs_read", {"path": "test.txt"}),
            ("fs_write", {"path": "notes.txt", "content": "Sample content"}),
            ("fs_list", {"path": "."}),
            ("db_query", {"table": "users", "limit": 10}),
            ("db_get_user", {"user_id": random.randint(1, 5)}),
            ("db_get_product", {"product_id": random.randint(1, 5)}),
            ("web_fetch", {"url": "https://api.example.com/users"}),
            ("web_search", {"query": "test query", "max_results": 5}),
        ]

    def on_start(self):
        """Initialize user with API key."""
        # In real test, you'd authenticate and get a key
        # For load test, we'll use a header that the gateway accepts
        self.client.headers.update({
            "Content-Type": "application/json",
            "X-API-Key": "aw_load_test_key",  # This would need to be a valid key
        })

    def make_rpc_call(self, method: str, params: dict, name: str = None):
        """Make a JSON-RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": random.randint(1, 1000000),
        }
        return self.client.post("/api/v1/rpc", json=payload, name=name or method)

    @task(10)
    def list_tools(self):
        """List available tools."""
        self.make_rpc_call("tools/list", {}, name="tools/list")

    @task(50)
    def call_random_tool(self):
        """Call a random tool."""
        tool_name, args = random.choice(self.tools)
        self.make_rpc_call("tools/call", {"name": tool_name, "arguments": args}, name=f"tools/call:{tool_name}")

    @task(5)
    def call_fs_read(self):
        """Read a file."""
        self.make_rpc_call("tools/call", {"name": "fs_read", "arguments": {"path": f"file_{random.randint(1,100)}.txt"}}, name="tools/call:fs_read")

    @task(3)
    def call_fs_write(self):
        """Write a file."""
        self.make_rpc_call("tools/call", {"name": "fs_write", "arguments": {"path": f"output_{random.randint(1,1000)}.txt", "content": "Load test data"}}, name="tools/call:fs_write")

    @task(10)
    def call_db_query(self):
        """Query database."""
        table = random.choice(["users", "products", "orders"])
        self.make_rpc_call("tools/call", {"name": "db_query", "arguments": {"table": table, "limit": 10}}, name="tools/call:db_query")

    @task(5)
    def call_web_fetch(self):
        """Fetch web content."""
        url = random.choice([
            "https://api.example.com/users",
            "https://api.example.com/config",
            "https://example.com/page",
        ])
        self.make_rpc_call("tools/call", {"name": "web_fetch", "arguments": {"url": url}}, name="tools/call:web_fetch")


class DirectToolServerUser(HttpUser):
    """Simulated user calling tool servers directly (baseline)."""

    wait_time = between(0.1, 0.5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tools = [
            ("fs_read", {"path": "test.txt"}),
            ("fs_write", {"path": "notes.txt", "content": "Sample content"}),
            ("fs_list", {"path": "."}),
            ("db_query", {"table": "users", "limit": 10}),
            ("db_get_user", {"user_id": random.randint(1, 5)}),
            ("web_fetch", {"url": "https://api.example.com/users"}),
        ]

    def make_rpc_call(self, method: str, params: dict, name: str = None):
        """Make a JSON-RPC call to tool server."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": random.randint(1, 1000000),
        }
        return self.client.post("/", json=payload, name=name or method)

    @task(10)
    def list_tools(self):
        self.make_rpc_call("tools/list", {}, name="tools/list")

    @task(50)
    def call_random_tool(self):
        tool_name, args = random.choice(self.tools)
        self.make_rpc_call("tools/call", {"name": tool_name, "arguments": args}, name=f"tools/call:{tool_name}")


# Custom event handlers for detailed reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "=" * 60)
    print("LOAD TEST STARTED")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "=" * 60)
    print("LOAD TEST COMPLETED")
    print("=" * 60)

    # Print summary statistics
    stats = environment.stats
    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Failure Rate: {stats.total.fail_ratio:.2%}")
    print(f"Avg Response Time: {stats.total.avg_response_time:.2f} ms")
    print(f"Min Response Time: {stats.total.min_response_time:.2f} ms")
    print(f"Max Response Time: {stats.total.max_response_time:.2f} ms")
    print(f"Median Response Time: {stats.total.median_response_time:.2f} ms")
    print(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f} ms")
    print(f"99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f} ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")

    # Per-endpoint stats
    print("\nPer-endpoint statistics:")
    print(f"{'Endpoint':<30} {'Reqs':>8} {'Fails':>8} {'Avg(ms)':>10} {'P50(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10} {'RPS':>8}")
    print("-" * 100)
    for entry in stats.entries.values():
        if entry.num_requests > 0:
            print(f"{entry.name:<30} {entry.num_requests:>8} {entry.num_failures:>8} "
                  f"{entry.avg_response_time:>10.2f} {entry.median_response_time:>10.2f} "
                  f"{entry.get_response_time_percentile(0.95):>10.2f} "
                  f"{entry.get_response_time_percentile(0.99):>10.2f} {entry.total_rps:>8.2f}")


def run_load_test(host: str = "http://localhost:8000", users: int = 50, spawn_rate: int = 10, run_time: str = "60s"):
    """Run load test programmatically."""

    env = Environment(user_classes=[AgentWallUser])
    env.create_local_runner()

    # Start test
    env.runner.start(users, spawn_rate=spawn_rate)

    # Run for specified time
    gevent.spawn_later(parse_time(run_time), lambda: env.runner.quit())

    # Start stats printer
    gevent.spawn(stats_printer(env.stats))

    env.runner.greenlet.join()

    return env.stats


def parse_time(time_str: str) -> int:
    """Parse time string like '60s', '5m', '1h' to seconds."""
    if time_str.endswith('s'):
        return int(time_str[:-1])
    elif time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    return int(time_str)


if __name__ == "__main__":

    # Run with: python -m benchmarks.locustfile
    # Or: locust -f benchmarks/locustfile.py --host=http://localhost:8000
    print("Run with: locust -f benchmarks/locustfile.py --host=http://localhost:8000")
    print("For headless: locust -f benchmarks/locustfile.py --host=http://localhost:8000 --headless -u 50 -r 10 -t 60s")
