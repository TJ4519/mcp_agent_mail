#!/usr/bin/env python3
"""
TUTORIAL 03: Two Agents with Dependent Scripts

This demonstrates:
  - Agent B depends on Agent A finishing first
  - Coordination via messages + inbox checking
  - Real-world workflow: main.py imports utils.py

Scenario:
  - Agent A builds utils.py (helper functions)
  - Agent B waits for utils.py, then builds main.py (uses utils)
  - Shows polling inbox, ack_required messages
"""

import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

# ═══════════════════════════════════════════════════════════════════
# PRE-EMPTING YOUR ADHD BRAIN:
#
# 💭 "This looks complicated with dependencies..."
# 💬 It's just: Agent B polls inbox, waits for "utils done" message.
#    That's it. Same pattern you'd use checking email.
#
# 💭 "What if Agent A never sends the message?"
# 💬 Agent B would timeout or check file reservations to see activity.
#    In real systems, add timeout logic.
#
# 💭 "Do I need to understand threading for this?"
# 💬 NO. This is sequential. One agent finishes, the other starts.
# ═══════════════════════════════════════════════════════════════════

SERVER_URL = "http://127.0.0.1:8765"
MCP_ENDPOINT = f"{SERVER_URL}/mcp"


class MCPClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments}
        }
        response = self.client.post(self.base_url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise Exception(f"MCP Error: {data['error']}")
        return data.get("result", {})


class Agent:
    def __init__(self, name: str, client: MCPClient, project_key: str):
        self.name = name
        self.client = client
        self.project_key = project_key

    def reserve_file(self, path: str, reason: str) -> None:
        print(f"  [{self.name}] 🔒 Reserving {path}...")
        self.client.call_tool("file_reservation_paths", {
            "project_key": self.project_key,
            "agent_name": self.name,
            "paths": [path],
            "exclusive": True,
            "ttl_seconds": 120,
            "reason": reason
        })

    def release_file(self, path: str) -> None:
        self.client.call_tool("release_file_reservations", {
            "project_key": self.project_key,
            "agent_name": self.name,
            "paths": [path]
        })
        print(f"  [{self.name}] 🔓 Released {path}")

    def send_message(self, to: list[str], subject: str, body: str, ack_required: bool = False) -> int:
        print(f"  [{self.name}] 📨 Sending: {subject}")
        result = self.client.call_tool("send_message", {
            "project_key": self.project_key,
            "sender_name": self.name,
            "to": to,
            "subject": subject,
            "body_md": body,
            "ack_required": ack_required
        })
        return result.get("id", 0)

    def check_inbox(self, unread_only: bool = True) -> list[dict[str, Any]]:
        """Check inbox for new messages."""
        print(f"  [{self.name}] 📬 Checking inbox...")
        result = self.client.call_tool("fetch_inbox", {
            "project_key": self.project_key,
            "agent_name": self.name,
            "include_bodies": True,
            "limit": 10
        })
        messages = result.get("messages", [])

        if unread_only:
            messages = [m for m in messages if not m.get("read_ts")]

        print(f"  [{self.name}] 📨 Found {len(messages)} message(s)")
        return messages

    def acknowledge_message(self, message_id: int) -> None:
        """Acknowledge a message (confirms receipt and processing)."""
        print(f"  [{self.name}] ✅ Acknowledging message {message_id}")
        self.client.call_tool("acknowledge_message", {
            "project_key": self.project_key,
            "message_id": message_id,
            "agent_name": self.name
        })

    def wait_for_message(self, subject_contains: str, max_attempts: int = 10) -> dict[str, Any] | None:
        """Poll inbox until message with subject arrives."""
        print(f"  [{self.name}] ⏳ Waiting for message about '{subject_contains}'...")

        for attempt in range(max_attempts):
            messages = self.check_inbox(unread_only=True)

            for msg in messages:
                if subject_contains.lower() in msg.get("subject", "").lower():
                    print(f"  [{self.name}] ✓ Found message!")
                    return msg

            if attempt < max_attempts - 1:
                time.sleep(2)

        print(f"  [{self.name}] ⚠️  Timeout waiting for message")
        return None


def agent_a_builds_utils(agent: Agent, repo_path: Path) -> None:
    """Agent A: Build utils.py with helper functions."""
    print(f"\n{'━'*60}")
    print(f"{agent.name}: Building utils.py")
    print('━'*60)

    filename = "utils.py"
    filepath = repo_path / filename

    agent.reserve_file(filename, "Creating utility functions")

    code = '''#!/usr/bin/env python3
"""Utility functions for data processing."""


def square(n: int) -> int:
    """Return square of n."""
    return n * n


def double(n: int) -> int:
    """Return double of n."""
    return n * 2


def compute_series(start: int, count: int) -> list[int]:
    """Generate series: start, square(start), double(square(start)), ..."""
    result = [start]
    for _ in range(count - 1):
        last = result[-1]
        result.append(square(double(last)))
    return result


if __name__ == "__main__":
    print("Testing utils...")
    print(f"square(5) = {square(5)}")
    print(f"double(5) = {double(5)}")
    print(f"compute_series(2, 5) = {compute_series(2, 5)}")
'''

    filepath.write_text(code)
    print(f"  [{agent.name}] ✍️  Wrote {filename}")

    # Commit
    subprocess.run(["git", "add", filename], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"[{agent.name}] Create {filename}"],
        cwd=repo_path, check=True, capture_output=True
    )
    print(f"  [{agent.name}] ✅ Committed")

    # Test it
    result = subprocess.run(["python3", filename], cwd=repo_path, capture_output=True, text=True)
    print(f"  [{agent.name}] 🧪 Test passed")

    agent.release_file(filename)

    # Send message to BlueLake with ack_required
    agent.send_message(
        ["BlueLake"],
        "utils.py ready - you can build main.py now",
        f"I've completed utils.py with helper functions.\n\n**Available functions:**\n- `square(n)`\n- `double(n)`\n- `compute_series(start, count)`\n\nTest output:\n```\n{result.stdout.strip()}\n```\n\nYou can now build main.py that imports these.",
        ack_required=True
    )
    print(f"  [{agent.name}] 🎯 Notified BlueLake (ack required)")


def agent_b_builds_main(agent: Agent, repo_path: Path) -> None:
    """Agent B: Wait for utils.py, then build main.py."""
    print(f"\n{'━'*60}")
    print(f"{agent.name}: Waiting for utils.py, then building main.py")
    print('━'*60)

    # STEP 1: Wait for message from RedCastle
    msg = agent.wait_for_message("utils.py ready", max_attempts=10)
    if not msg:
        print(f"  [{agent.name}] ❌ Failed to receive ready signal")
        return

    # STEP 2: Acknowledge the message
    msg_id = msg.get("id")
    if msg_id:
        agent.acknowledge_message(msg_id)

    print(f"  [{agent.name}] 📖 Message received. Building main.py...")

    # STEP 3: Build main.py that uses utils.py
    filename = "main.py"
    filepath = repo_path / filename

    agent.reserve_file(filename, "Creating main script using utils")

    code = '''#!/usr/bin/env python3
"""Main script that uses utility functions."""

from utils import square, double, compute_series


def main():
    print("=== Main Script Demo ===")
    print()

    # Test square
    n = 7
    print(f"Square of {n}: {square(n)}")

    # Test double
    print(f"Double of {n}: {double(n)}")

    # Test series
    print(f"Series starting from {n}:")
    series = compute_series(n, 5)
    print(f"  {series}")

    print()
    print("✓ All tests passed!")


if __name__ == "__main__":
    main()
'''

    filepath.write_text(code)
    print(f"  [{agent.name}] ✍️  Wrote {filename}")

    # Commit
    subprocess.run(["git", "add", filename], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"[{agent.name}] Create {filename} using utils"],
        cwd=repo_path, check=True, capture_output=True
    )
    print(f"  [{agent.name}] ✅ Committed")

    # STEP 4: Test it (this will import utils.py)
    result = subprocess.run(["python3", filename], cwd=repo_path, capture_output=True, text=True)
    print(f"  [{agent.name}] 🧪 Test output:")
    for line in result.stdout.strip().split('\n'):
        print(f"      {line}")

    agent.release_file(filename)

    # STEP 5: Send completion message
    agent.send_message(
        ["RedCastle"],
        "Project complete - main.py working!",
        f"Successfully built main.py using your utils.\n\nTest output:\n```\n{result.stdout.strip()}\n```\n\n✓ Integration test passed!"
    )
    print(f"  [{agent.name}] 🎉 Project complete!")


def setup_test_repo() -> Path:
    test_dir = Path("/tmp/mcp_tutorial_dependent_scripts")

    if test_dir.exists():
        subprocess.run(["rm", "-rf", str(test_dir)], check=True)

    test_dir.mkdir(parents=True)

    subprocess.run(["git", "init"], cwd=test_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tutorial"], cwd=test_dir, check=True)
    subprocess.run(["git", "config", "user.email", "tutorial@example.com"], cwd=test_dir, check=True)

    readme = test_dir / "README.md"
    readme.write_text("# Dependent Scripts Tutorial\n\nAgent B depends on Agent A's work.\n")
    subprocess.run(["git", "add", "README.md"], cwd=test_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=test_dir, check=True, capture_output=True)

    print(f"✓ Created test repo at {test_dir}\n")
    return test_dir


def main():
    print("═" * 60)
    print("TUTORIAL 03: Dependent Scripts with Coordination")
    print("═" * 60)
    print()
    print("Workflow:")
    print("  1. RedCastle builds utils.py")
    print("  2. RedCastle sends 'ready' message (ack_required)")
    print("  3. BlueLake polls inbox, waits for message")
    print("  4. BlueLake acknowledges message")
    print("  5. BlueLake builds main.py (imports utils)")
    print("  6. BlueLake notifies completion")
    print()

    # Check server
    try:
        httpx.get(f"{SERVER_URL}/health/liveness", timeout=5.0).raise_for_status()
        print("✓ MCP Agent Mail server is running\n")
    except Exception:
        print("✗ Server not running. Please start it first.")
        return

    # Setup
    repo_path = setup_test_repo()
    project_key = str(repo_path.resolve())

    client = MCPClient(MCP_ENDPOINT)
    client.call_tool("ensure_project", {"human_key": project_key})

    # Register agents
    print("Registering agents...")
    for name in ["RedCastle", "BlueLake"]:
        client.call_tool("register_agent", {
            "project_key": project_key,
            "name": name,
            "program": "tutorial",
            "model": "demo",
            "task": "Build dependent scripts"
        })
        print(f"  ✓ {name}")
    print()

    red = Agent("RedCastle", client, project_key)
    blue = Agent("BlueLake", client, project_key)

    # SEQUENTIAL workflow (B depends on A)
    agent_a_builds_utils(red, repo_path)
    agent_b_builds_main(blue, repo_path)

    print(f"\n{'─'*60}")
    print("FINAL RESULT")
    print('─'*60)
    print()

    # Show git history
    result = subprocess.run(
        ["git", "log", "--oneline", "--all"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    print("Git history:")
    for line in result.stdout.strip().split('\n'):
        print(f"  {line}")
    print()

    # Run the final integrated program
    print("Running integrated program:")
    print("─" * 40)
    result = subprocess.run(["python3", "main.py"], cwd=repo_path, capture_output=True, text=True)
    print(result.stdout)
    print("─" * 40)

    print("\n✅ Tutorial 03 complete!")
    print()
    print("═" * 60)
    print("KEY INSIGHTS")
    print("═" * 60)
    print()
    print("1. Dependency coordination via inbox polling")
    print("   Agent B waits for explicit 'ready' signal")
    print()
    print("2. ack_required ensures message was received")
    print("   Agent A knows B got the message")
    print()
    print("3. Sequential workflow (not parallel)")
    print("   B cannot proceed until A completes")
    print()
    print("4. This pattern scales to N agents")
    print("   Chain dependencies: A → B → C → D")
    print()
    print("5. Audit trail shows full coordination")
    print("   Messages + commits tell complete story")
    print()


if __name__ == "__main__":
    main()
