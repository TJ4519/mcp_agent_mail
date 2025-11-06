#!/usr/bin/env python3
"""
TUTORIAL 01: Three Agents Building n²+1 Sequence Collaboratively

This is the SIMPLEST possible demonstration of MCP Agent Mail.
Three agents take turns adding to a sequence, coordinating via:
  - File reservations (to avoid conflicts)
  - Messages (to notify next agent)

The sequence: 0 → 1 → 2 → 5 → 26 → 677 → ...
Each number is computed as: previous² + 1
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

# ═══════════════════════════════════════════════════════════════════
# PRE-EMPTING YOUR ADHD BRAIN RIGHT NOW:
#
# 💭 "This looks long, should I read all of it?"
# 💬 NO. Scroll to main() at the bottom. See the 6 steps. That's all.
#
# 💭 "What are all these imports?"
# 💬 httpx = makes HTTP calls. subprocess = runs git commands. That's it.
#
# 💭 "Why is this in Python not bash?"
# 💬 Because you can copy-paste the functions into your own agent code.
# ═══════════════════════════════════════════════════════════════════

SERVER_URL = "http://127.0.0.1:8765"
MCP_ENDPOINT = f"{SERVER_URL}/mcp"


class MCPClient:
    """Minimal MCP client - just enough to call tools."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool and return the result."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        response = self.client.post(self.base_url, json=payload)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise Exception(f"MCP Error: {data['error']}")

        return data.get("result", {})


class Agent:
    """Represents one agent in the tutorial."""

    def __init__(self, name: str, client: MCPClient, project_key: str):
        self.name = name
        self.client = client
        self.project_key = project_key

    def reserve_file(self, path: str, ttl_seconds: int = 60) -> None:
        """Reserve a file exclusively."""
        print(f"  [{self.name}] 🔒 Reserving {path}...")
        self.client.call_tool("file_reservation_paths", {
            "project_key": self.project_key,
            "agent_name": self.name,
            "paths": [path],
            "exclusive": True,
            "ttl_seconds": ttl_seconds,
            "reason": f"Computing next value in sequence"
        })
        print(f"  [{self.name}] ✓ Lock acquired")

    def release_file(self, path: str) -> None:
        """Release file reservation."""
        self.client.call_tool("release_file_reservations", {
            "project_key": self.project_key,
            "agent_name": self.name,
            "paths": [path]
        })
        print(f"  [{self.name}] 🔓 Lock released")

    def send_message(self, to: str, subject: str, body: str) -> None:
        """Send a message to another agent."""
        print(f"  [{self.name}] 📨 Sending message to {to}...")
        self.client.call_tool("send_message", {
            "project_key": self.project_key,
            "sender_name": self.name,
            "to": [to],
            "subject": subject,
            "body_md": body
        })
        print(f"  [{self.name}] ✓ Message sent")

    def check_inbox(self) -> list[dict[str, Any]]:
        """Check for new messages."""
        result = self.client.call_tool("fetch_inbox", {
            "project_key": self.project_key,
            "agent_name": self.name,
            "include_bodies": False,
            "limit": 10
        })
        return result.get("messages", [])

    def compute_next_value(self, current: int) -> int:
        """The actual computation: n² + 1"""
        return current * current + 1

    def take_turn(self, repo_path: Path, file_name: str, next_agent_name: str) -> None:
        """Complete one turn: reserve, compute, write, notify, release."""

        # Step 1: Reserve the file
        self.reserve_file(file_name)

        # Step 2: Read current value
        file_path = repo_path / file_name
        with open(file_path) as f:
            lines = f.read().strip().split('\n')
            current = int(lines[-1])
        print(f"  [{self.name}] 📖 Read current value: {current}")

        # Step 3: Compute next value
        next_val = self.compute_next_value(current)
        print(f"  [{self.name}] 🧮 Computed: {current}² + 1 = {next_val}")

        # Step 4: Write and commit
        with open(file_path, 'a') as f:
            f.write(f"{next_val}\n")

        subprocess.run(["git", "add", file_name], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"[{self.name}] Add {next_val} to sequence"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        print(f"  [{self.name}] ✍️  Written and committed")

        # Step 5: Notify next agent
        self.send_message(
            next_agent_name,
            f"Your turn - sequence at {next_val}",
            f"I computed {current}² + 1 = {next_val}.\n\nFile is ready for you."
        )

        # Step 6: Release the file
        self.release_file(file_name)


def setup_test_repo() -> Path:
    """Create a fresh test repository with initial sequence.txt"""
    test_dir = Path("/tmp/mcp_tutorial_simple_sequence")

    # Clean slate
    if test_dir.exists():
        subprocess.run(["rm", "-rf", str(test_dir)], check=True)

    test_dir.mkdir(parents=True)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=test_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tutorial"], cwd=test_dir, check=True)
    subprocess.run(["git", "config", "user.email", "tutorial@example.com"], cwd=test_dir, check=True)

    # Create initial sequence file
    sequence_file = test_dir / "sequence.txt"
    sequence_file.write_text("0\n")

    subprocess.run(["git", "add", "sequence.txt"], cwd=test_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial: Start sequence at 0"],
        cwd=test_dir,
        check=True,
        capture_output=True
    )

    print(f"✓ Created test repo at {test_dir}")
    print(f"✓ Initial sequence.txt contains: 0\n")

    return test_dir


def register_agents(client: MCPClient, project_key: str) -> tuple[Agent, Agent, Agent]:
    """Register three agents with the MCP server."""

    print("Ensuring project exists...")
    client.call_tool("ensure_project", {"human_key": project_key})
    print("✓ Project initialized\n")

    agents = []
    for name in ["RedCastle", "BlueLake", "GreenMountain"]:
        print(f"🤖 Registering {name}...")
        client.call_tool("register_agent", {
            "project_key": project_key,
            "name": name,
            "program": "tutorial",
            "model": "demo",
            "task": "Build sequence collaboratively"
        })
        agents.append(Agent(name, client, project_key))
        print(f"   ✓ {name} registered\n")

    return tuple(agents)


def main():
    """
    THE MAIN TUTORIAL FLOW

    This is what you should read to understand what's happening.
    Everything above this is just helper functions.
    """

    print("═" * 60)
    print("TUTORIAL 01: Simple Collaborative Sequence")
    print("═" * 60)
    print()
    print("What we're building:")
    print("  - Empty repo with sequence.txt")
    print("  - 3 agents (RedCastle, BlueLake, GreenMountain)")
    print("  - Each agent reads last number, computes n²+1, appends")
    print("  - Agents coordinate via file reservations + messages")
    print()
    print("Sequence: 0 → 1 → 2 → 5 → 26 → 677 → ...")
    print()
    print("─" * 60)

    # Check server is running
    try:
        response = httpx.get(f"{SERVER_URL}/health/liveness", timeout=5.0)
        response.raise_for_status()
        print("✓ MCP Agent Mail server is running\n")
    except Exception as e:
        print("✗ MCP Agent Mail server not responding")
        print("\nPlease start the server in another terminal:")
        print("  cd /home/user/mcp_agent_mail")
        print("  source .venv/bin/activate")
        print("  python -m mcp_agent_mail.cli serve-http --host 127.0.0.1 --port 8765")
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # THE SIX STEPS (This is all you need to remember)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # STEP 1: Create test repository
    repo_path = setup_test_repo()
    project_key = str(repo_path.resolve())

    # STEP 2: Create MCP client
    client = MCPClient(MCP_ENDPOINT)

    # STEP 3: Register three agents
    print("─" * 60)
    print("STEP 1: Register three agents")
    print("─" * 60)
    print()
    red, blue, green = register_agents(client, project_key)

    # STEP 4: Run 5 rounds of the sequence
    print("─" * 60)
    print("STEP 2: Run collaborative sequence (5 turns)")
    print("─" * 60)
    print()

    agents = [red, blue, green]
    for i in range(5):
        current_agent = agents[i % 3]
        next_agent = agents[(i + 1) % 3]

        print(f"━━━ Turn {i+1}: {current_agent.name} ━━━")
        current_agent.take_turn(repo_path, "sequence.txt", next_agent.name)
        print()
        time.sleep(0.5)  # Small delay for readability

    # STEP 5: Show final result
    print("─" * 60)
    print("FINAL RESULT")
    print("─" * 60)
    print()

    sequence_file = repo_path / "sequence.txt"
    sequence = sequence_file.read_text().strip().split('\n')
    print("Sequence built:")
    print("  " + " → ".join(sequence))
    print()

    # Show git history
    result = subprocess.run(
        ["git", "log", "--oneline", "--all"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    )
    print("Git history:")
    for line in result.stdout.strip().split('\n'):
        print(f"  {line}")
    print()

    # STEP 6: Show how to view in Web UI
    print("─" * 60)
    print("VIEW IN WEB UI")
    print("─" * 60)
    print()

    # Get project slug for URL
    result = client.call_tool("ensure_project", {"human_key": project_key})
    project_slug = result.get("project", {}).get("slug", "")

    print(f"Open in browser:")
    print(f"  {SERVER_URL}/mail/{project_slug}")
    print()
    print("You'll see:")
    print("  - All 3 agents registered")
    print("  - 5 messages exchanged")
    print("  - File reservations history")
    print()

    print("✅ Tutorial 01 complete!")
    print()
    print("═" * 60)
    print("WHAT JUST HAPPENED (The Key Insight)")
    print("═" * 60)
    print()
    print("1. Each agent RESERVED the file before editing")
    print("   → If two tried simultaneously, one gets CONFLICT error")
    print()
    print("2. Agents sent messages to coordinate handoff")
    print("   → Next agent knows when file is ready")
    print()
    print("3. All activity recorded in Git + viewable in Web UI")
    print("   → Humans can audit what happened")
    print()
    print("4. NO manual coordination needed")
    print("   → Agents are autonomous but cooperative")
    print()


if __name__ == "__main__":
    main()
