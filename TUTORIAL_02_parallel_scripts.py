#!/usr/bin/env python3
"""
TUTORIAL 02: Two Agents Editing Independent Scripts in Parallel

This demonstrates:
  - Multiple agents working simultaneously
  - No file conflicts (different files)
  - Agents still coordinate via messages (optional but good practice)

Scenario:
  - Agent A builds fibonacci.py (computes fib sequence)
  - Agent B builds primes.py (computes prime numbers)
  - Both work independently but notify each other of progress
"""

import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

# ═══════════════════════════════════════════════════════════════════
# PRE-EMPTING YOUR ADHD BRAIN:
#
# 💭 "Is this more complex than Tutorial 01?"
# 💬 NO. It's actually simpler - agents don't block each other.
#
# 💭 "Do I need to reserve files if they're different files?"
# 💬 Technically no, but it's good practice. Shows intent clearly.
#
# 💭 "Why are they sending messages if they're independent?"
# 💬 Status updates. In real projects, another agent might depend on
#    knowing when these scripts are done.
# ═══════════════════════════════════════════════════════════════════

SERVER_URL = "http://127.0.0.1:8765"
MCP_ENDPOINT = f"{SERVER_URL}/mcp"


class MCPClient:
    """Minimal MCP client."""

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
    """Agent with file reservation and messaging capabilities."""

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
        print(f"  [{self.name}] ✓ Reserved")

    def release_file(self, path: str) -> None:
        self.client.call_tool("release_file_reservations", {
            "project_key": self.project_key,
            "agent_name": self.name,
            "paths": [path]
        })
        print(f"  [{self.name}] 🔓 Released {path}")

    def send_status(self, to: list[str], subject: str, body: str) -> None:
        print(f"  [{self.name}] 📨 Broadcasting status...")
        self.client.call_tool("send_message", {
            "project_key": self.project_key,
            "sender_name": self.name,
            "to": to,
            "subject": subject,
            "body_md": body
        })


def build_fibonacci_script(agent: Agent, repo_path: Path) -> None:
    """Agent A builds fibonacci.py"""
    filename = "fibonacci.py"
    filepath = repo_path / filename

    print(f"\n{'━'*60}")
    print(f"{agent.name}: Building {filename}")
    print('━'*60)

    # Reserve file
    agent.reserve_file(filename, "Creating Fibonacci sequence generator")

    # Write the script
    code = '''#!/usr/bin/env python3
"""Compute Fibonacci sequence up to N terms."""

def fibonacci(n: int) -> list[int]:
    """Generate first n Fibonacci numbers."""
    if n <= 0:
        return []
    if n == 1:
        return [0]
    if n == 2:
        return [0, 1]

    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[-1] + fib[-2])
    return fib


if __name__ == "__main__":
    print("Fibonacci sequence (first 10):")
    print(fibonacci(10))
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
    result = subprocess.run(
        ["python3", filename],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    print(f"  [{agent.name}] 🧪 Test output: {result.stdout.strip()}")

    # Release and notify
    agent.release_file(filename)
    agent.send_status(
        ["BlueLake"],
        f"{filename} complete",
        f"Fibonacci sequence generator is ready.\n\nTest passed:\n```\n{result.stdout.strip()}\n```"
    )


def build_primes_script(agent: Agent, repo_path: Path) -> None:
    """Agent B builds primes.py"""
    filename = "primes.py"
    filepath = repo_path / filename

    print(f"\n{'━'*60}")
    print(f"{agent.name}: Building {filename}")
    print('━'*60)

    # Reserve file
    agent.reserve_file(filename, "Creating prime number generator")

    # Write the script
    code = '''#!/usr/bin/env python3
"""Generate prime numbers up to N."""

def is_prime(n: int) -> bool:
    """Check if n is prime."""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


def primes_up_to(limit: int) -> list[int]:
    """Generate all primes up to limit."""
    return [n for n in range(2, limit + 1) if is_prime(n)]


if __name__ == "__main__":
    print("Primes up to 50:")
    print(primes_up_to(50))
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
    result = subprocess.run(
        ["python3", filename],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    print(f"  [{agent.name}] 🧪 Test output: {result.stdout.strip()}")

    # Release and notify
    agent.release_file(filename)
    agent.send_status(
        ["RedCastle"],
        f"{filename} complete",
        f"Prime number generator is ready.\n\nTest passed:\n```\n{result.stdout.strip()}\n```"
    )


def setup_test_repo() -> Path:
    """Create fresh test repository."""
    test_dir = Path("/tmp/mcp_tutorial_parallel_scripts")

    if test_dir.exists():
        subprocess.run(["rm", "-rf", str(test_dir)], check=True)

    test_dir.mkdir(parents=True)

    subprocess.run(["git", "init"], cwd=test_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tutorial"], cwd=test_dir, check=True)
    subprocess.run(["git", "config", "user.email", "tutorial@example.com"], cwd=test_dir, check=True)

    readme = test_dir / "README.md"
    readme.write_text("# Parallel Scripts Tutorial\n\nTwo agents building independent scripts.\n")
    subprocess.run(["git", "add", "README.md"], cwd=test_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=test_dir, check=True, capture_output=True)

    print(f"✓ Created test repo at {test_dir}\n")
    return test_dir


def main():
    print("═" * 60)
    print("TUTORIAL 02: Parallel Independent Scripts")
    print("═" * 60)
    print()
    print("What we're building:")
    print("  - fibonacci.py (by RedCastle)")
    print("  - primes.py (by BlueLake)")
    print("  - Both agents work in parallel")
    print("  - No conflicts (different files)")
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
            "task": "Build utility scripts"
        })
        print(f"  ✓ {name}")
    print()

    red = Agent("RedCastle", client, project_key)
    blue = Agent("BlueLake", client, project_key)

    # Simulate parallel work (in real scenario, these would be async)
    # For demo, we run sequentially but show they COULD be parallel
    import threading

    thread_a = threading.Thread(target=build_fibonacci_script, args=(red, repo_path))
    thread_b = threading.Thread(target=build_primes_script, args=(blue, repo_path))

    print("Starting parallel builds...")
    thread_a.start()
    time.sleep(0.1)  # Small stagger for readability
    thread_b.start()

    thread_a.join()
    thread_b.join()

    print(f"\n{'─'*60}")
    print("FINAL RESULT")
    print('─'*60)
    print()

    # Show git history
    result = subprocess.run(
        ["git", "log", "--oneline", "--all", "--graph"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    print("Git history:")
    print(result.stdout)

    # Show files created
    print("Files created:")
    for f in ["fibonacci.py", "primes.py"]:
        print(f"  ✓ {f}")
    print()

    print("✅ Tutorial 02 complete!")
    print()
    print("═" * 60)
    print("KEY INSIGHT")
    print("═" * 60)
    print()
    print("1. Different files → No blocking")
    print("   Agents can work truly in parallel")
    print()
    print("2. File reservations still used (best practice)")
    print("   Makes intent clear in audit trail")
    print()
    print("3. Messages provide status updates")
    print("   Useful for orchestration / next steps")
    print()


if __name__ == "__main__":
    main()
