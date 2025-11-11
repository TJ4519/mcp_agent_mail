#!/bin/bash
# TUTORIAL 01: Three agents building n²+1 sequence collaboratively

set -e

echo "═══════════════════════════════════════════════════════"
echo "TUTORIAL 01: Simple Collaborative Sequence"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "What we're building:"
echo "  - Empty repo with sequence.txt"
echo "  - 3 agents (RedCastle, BlueLake, GreenMountain)"
echo "  - Each agent reads last number, computes n²+1, appends"
echo "  - Agents coordinate via file reservations"
echo ""
echo "Sequence: 0 → 1 → 2 → 5 → 26 → 677 → ..."
echo ""

# Create empty test repo
TEST_DIR="/tmp/mcp_tutorial_simple_sequence"
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"
git init
echo "0" > sequence.txt
git add sequence.txt
git commit -m "Initial: Start sequence at 0"

echo "✓ Created test repo at $TEST_DIR"
echo "✓ Initial sequence.txt contains: 0"
echo ""

# Get absolute path
PROJECT_KEY="$TEST_DIR"

echo "───────────────────────────────────────────────────────"
echo "Setting up MCP Agent Mail server..."
echo "───────────────────────────────────────────────────────"
echo ""
echo "Pre-requisite: MCP Agent Mail server must be running."
echo "In another terminal, run:"
echo ""
echo "  cd /home/user/mcp_agent_mail"
echo "  source .venv/bin/activate"
echo "  python -m mcp_agent_mail.cli serve-http --host 127.0.0.1 --port 8765"
echo ""
echo "Press ENTER when server is running..."
read

# Test server health
echo "Testing server connection..."
curl -s http://127.0.0.1:8765/health/liveness > /dev/null && echo "✓ Server is live" || (echo "✗ Server not responding" && exit 1)

echo ""
echo "───────────────────────────────────────────────────────"
echo "STEP 1: Register three agents"
echo "───────────────────────────────────────────────────────"
echo ""

# We'll simulate agents via curl to the MCP endpoint
# In real usage, agents would use MCP client libraries

# Helper function to call MCP tools
call_tool() {
    local tool_name=$1
    local args=$2
    curl -s -X POST http://127.0.0.1:8765/mcp \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$tool_name\",\"arguments\":$args}}" | jq .
}

echo "🤖 Registering RedCastle..."
call_tool "ensure_project" "{\"human_key\":\"$PROJECT_KEY\"}" | jq -r '.result.project.slug' > /tmp/project_slug
PROJECT_SLUG=$(cat /tmp/project_slug)
echo "   Project slug: $PROJECT_SLUG"

call_tool "register_agent" "{\"project_key\":\"$PROJECT_KEY\",\"name\":\"RedCastle\",\"program\":\"tutorial\",\"model\":\"demo\",\"task\":\"Build sequence collaboratively\"}" > /dev/null
echo "   ✓ RedCastle registered"

echo ""
echo "🤖 Registering BlueLake..."
call_tool "register_agent" "{\"project_key\":\"$PROJECT_KEY\",\"name\":\"BlueLake\",\"program\":\"tutorial\",\"model\":\"demo\",\"task\":\"Build sequence collaboratively\"}" > /dev/null
echo "   ✓ BlueLake registered"

echo ""
echo "🤖 Registering GreenMountain..."
call_tool "register_agent" "{\"project_key\":\"$PROJECT_KEY\",\"name\":\"GreenMountain\",\"program\":\"tutorial\",\"model\":\"demo\",\"task\":\"Build sequence collaboratively\"}" > /dev/null
echo "   ✓ GreenMountain registered"

echo ""
echo "───────────────────────────────────────────────────────"
echo "STEP 2: Agent workflow simulation (5 iterations)"
echo "───────────────────────────────────────────────────────"
echo ""

AGENTS=("RedCastle" "BlueLake" "GreenMountain")

for i in {1..5}; do
    AGENT="${AGENTS[$((i % 3))]}"
    echo "━━━ Turn $i: $AGENT ━━━"

    # 1. Reserve the file
    echo "  1️⃣  Reserving sequence.txt..."
    call_tool "file_reservation_paths" "{\"project_key\":\"$PROJECT_KEY\",\"agent_name\":\"$AGENT\",\"paths\":[\"sequence.txt\"],\"exclusive\":true,\"ttl_seconds\":60,\"reason\":\"Computing next value\"}" > /dev/null
    echo "      ✓ Exclusive lock acquired"

    # 2. Read current value
    CURRENT=$(tail -n 1 "$TEST_DIR/sequence.txt")
    echo "  2️⃣  Read current value: $CURRENT"

    # 3. Compute next value (n² + 1)
    NEXT=$((CURRENT * CURRENT + 1))
    echo "  3️⃣  Computed next value: $CURRENT² + 1 = $NEXT"

    # 4. Write new value
    echo "$NEXT" >> "$TEST_DIR/sequence.txt"
    git -C "$TEST_DIR" add sequence.txt
    git -C "$TEST_DIR" commit -m "[$AGENT] Add $NEXT to sequence"
    echo "  4️⃣  Appended $NEXT and committed"

    # 5. Send message to next agent
    NEXT_AGENT="${AGENTS[$(((i + 1) % 3))]}"
    echo "  5️⃣  Notifying $NEXT_AGENT..."
    call_tool "send_message" "{\"project_key\":\"$PROJECT_KEY\",\"sender_name\":\"$AGENT\",\"to\":[\"$NEXT_AGENT\"],\"subject\":\"Your turn - sequence at $NEXT\",\"body_md\":\"I computed $CURRENT² + 1 = $NEXT. File is ready for you.\"}" > /dev/null
    echo "      ✓ Message sent"

    # 6. Release the file
    call_tool "release_file_reservations" "{\"project_key\":\"$PROJECT_KEY\",\"agent_name\":\"$AGENT\",\"paths\":[\"sequence.txt\"]}" > /dev/null
    echo "  6️⃣  Released lock"

    echo ""
    sleep 1
done

echo "───────────────────────────────────────────────────────"
echo "FINAL RESULT"
echo "───────────────────────────────────────────────────────"
echo ""
echo "Sequence built:"
cat "$TEST_DIR/sequence.txt" | tr '\n' ' '
echo ""
echo ""

echo "Git history:"
git -C "$TEST_DIR" log --oneline --all

echo ""
echo "───────────────────────────────────────────────────────"
echo "VIEW IN WEB UI"
echo "───────────────────────────────────────────────────────"
echo ""
echo "Open in browser:"
echo "  http://127.0.0.1:8765/mail/$PROJECT_SLUG"
echo ""
echo "You'll see:"
echo "  - All 3 agents registered"
echo "  - 5 messages exchanged"
echo "  - File reservations history"
echo ""

echo "✅ Tutorial 01 complete!"
echo ""
echo "What just happened:"
echo "  1. Each agent RESERVED the file before editing"
echo "  2. If two tried to reserve simultaneously, one would get CONFLICT error"
echo "  3. Agents sent messages to coordinate handoff"
echo "  4. All activity is in Git + viewable in Web UI"
