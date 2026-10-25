#!/usr/bin/env python3
"""AgentWall Attack Demo.

This script demonstrates AgentWall blocking a prompt injection attack
that attempts to steal seeded fake credentials from the database tool server.
"""
import asyncio
import httpx
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import get_settings

settings = get_settings()

GATEWAY_URL = "http://localhost:8000/api/v1/rpc"
DIRECT_DB_URL = "http://localhost:8002"


async def print_section(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


async def print_json(data):
    print(json.dumps(data, indent=2))


async def run_attack_demo():
    """Run the attack demonstration."""
    await print_section("AgentWall Attack Demo")
    print()
    print("Scenario: An attacker agent attempts to steal credentials")
    print("from the database tool server using prompt injection.")
    print()

    # The attack payload - attempts to call the restricted db_internal_credentials tool
    attack_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "db_internal_credentials",
            "arguments": {"system": "api_keys"}
        },
        "id": 1
    }

    print("Attack payload:")
    await print_json(attack_payload)
    print()

    # Test 1: Direct attack on database server (bypassing AgentWall)
    await print_section("TEST 1: Direct attack on database server (AgentWall OFF)")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(DIRECT_DB_URL, json=attack_payload)
            result = resp.json()
            print(f"Status: {resp.status_code}")
            if "result" in result and result["result"]:
                content = result["result"].get("content", [{}])[0].get("text", "")
                print("Result: CREDENTIALS STOLEN!")
                await print_json(json.loads(content) if content.startswith("{") else content)
            else:
                print("Result:", json.dumps(result, indent=2)[:500])
        except Exception as e:
            print(f"Error: {e}")
            print("Note: Start the stack with 'docker compose up -d' to run live demo")

    print()

    # Test 2: Attack through AgentWall gateway
    await print_section("TEST 2: Attack through AgentWall gateway (AgentWall ON)")
    print("Note: This requires a valid agent API key.")
    print("With default-deny policy, the attack should be blocked.")
    print()

    # Simulate what the gateway would do
    print("Gateway processing:")
    print("  1. Rate limit check: PASS")
    print("  2. Loop detection: PASS")
    print("  3. Schema validation: PASS (tool exists)")
    print("  4. Threat detection: Checking for prompt injection...")
    print("     - Tool name 'db_internal_credentials' is suspicious")
    print("     - Arguments contain 'api_keys' - credential access pattern")
    print("  5. Policy evaluation: Default DENY (no allow policy for this tool)")
    print("  6. DLP scan: Would redact any credentials in response")
    print()
    print("EXPECTED RESULT: BLOCKED - Default deny policy prevents access")
    print("                 to restricted tools like db_internal_credentials")
    print()

    # Test 3: Show a benign request that would be allowed
    await print_section("TEST 3: Benign request through AgentWall (Allowed)")

    benign_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "db_get_user",
            "arguments": {"user_id": 1}
        },
        "id": 2
    }

    print("Benign payload:")
    await print_json(benign_payload)
    print()
    print("Gateway processing:")
    print("  1. Rate limit check: PASS")
    print("  2. Loop detection: PASS")
    print("  3. Schema validation: PASS")
    print("  4. Threat detection: CLEAN")
    print("  5. Policy evaluation: ALLOW (operator role can read users)")
    print("  6. DLP scan: No sensitive data in response")
    print()
    print("EXPECTED RESULT: ALLOWED - Returns user data")
    print()

    await print_section("Demo complete!")
    print("Summary:")
    print("  - AgentWall blocks unauthorized access to sensitive tools")
    print("  - Default-deny policy prevents credential theft")
    print("  - Legitimate tool calls continue to work")
    print("  - All attempts are logged in tamper-evident audit trail")


async def run_live_demo():
    """Run live demo against running services."""
    print("Attempting live demo...")

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Check if gateway is running
        try:
            resp = await client.get("http://localhost:8000/admin/health")
            if resp.status_code == 200:
                print("Gateway is running!")
                health = resp.json()
                print(f"  Status: {health['status']}")
                print(f"  Database: {health['database']}")
                print(f"  Redis: {health['redis']}")
            else:
                print("Gateway not healthy")
                return
        except Exception:
            print("Gateway not accessible at http://localhost:8000")
            print("Start the stack with: docker compose up -d")
            return

        # Check if we can create an agent (need admin key)
        print("\nTo run live demo, you need an admin API key.")
        print("Create one with:")
        print("  curl -X POST http://localhost:8000/admin/agents \\")
        print("    -H 'Content-Type: application/json' \\")
        print("    -H 'X-API-Key: YOUR_ADMIN_KEY' \\")
        print("    -d '{\"name\": \"demo-agent\", \"role\": \"operator\"}'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AgentWall Attack Demo")
    parser.add_argument("--live", action="store_true", help="Run live demo against running services")
    args = parser.parse_args()

    if args.live:
        asyncio.run(run_live_demo())
    else:
        asyncio.run(run_attack_demo())