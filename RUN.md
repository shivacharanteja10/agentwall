# RUN.md - Beginner-Friendly Run Guide

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Git | 2.40+ | `winget install Git.Git` / `brew install git` / `apt install git` |
| Docker | 24+ | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| Docker Compose | v2+ | Included with Docker Desktop |
| Python | 3.11+ | [python.org](https://python.org) (for local dev) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) (for dashboard dev) |

### Windows Notes (WSL2 Recommended)

```powershell
# Enable WSL2
wsl --install

# Inside WSL2 (Ubuntu):
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER
newgrp docker
```

## Quick Start (Docker Compose)

```bash
# 1. Clone the repository
git clone https://github.com/shivacharanteja10/agentwall.git
cd agentwall

# 2. Configure environment
cp .env.example .env
# Edit .env - at minimum change SECRET_KEY
# On Linux/macOS:
# sed -i 's/SECRET_KEY=.*/SECRET_KEY='$(openssl rand -hex 32)'/' .env
# On Windows PowerShell:
# (Get-Content .env) -replace 'SECRET_KEY=.*', "SECRET_KEY=$([System.Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 })))" | Set-Content .env

# 3. Start the stack
docker compose up -d

# 4. Wait for services (30-60 seconds)
docker compose logs -f gateway
# Look for: "Application startup complete"
```

## Verify Deployment

```bash
# Check all containers running
docker compose ps

# Gateway health
curl http://localhost:8000/admin/health

# Dashboard
open http://localhost:3000

# Tool servers
curl http://localhost:8001/health  # Filesystem
curl http://localhost:8002/health  # Database
curl http://localhost:8003/health  # Web Fetch
```

## Create Your First Agent

```bash
# You need an admin API key first.
# The gateway creates a default admin on first run if you set ADMIN_API_KEY in .env
# Or create one manually:

# Option 1: Use the bootstrap script (creates admin agent)
docker compose exec gateway python -c "
from app.core.security import generate_api_key, hash_api_key
from app.db.base import AsyncSessionLocal
from app.models import Agent, AgentRole
import asyncio

async def create_admin():
    async with AsyncSessionLocal() as db:
        api_key = generate_api_key()
        agent = Agent(
            name='admin',
            role=AgentRole.ADMIN,
            api_key_hash=hash_api_key(api_key),
        )
        db.add(agent)
        await db.commit()
        print(f'Admin API Key: {api_key}')

asyncio.run(create_admin())
"

# Option 2: Use the Makefile (requires running gateway)
make gen-key
```

### Using the Admin Key

```bash
export ADMIN_KEY="aw_your_generated_key_here"

# Create an operator agent
curl -X POST http://localhost:8000/admin/agents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{"name": "demo-agent", "role": "operator"}'

# Save the returned api_key!
export AGENT_KEY="aw_returned_key_here"
```

## Test Tool Calls

```bash
# List available tools
curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' | jq

# Read a file (filesystem tool)
curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"fs_write","arguments":{"path":"hello.txt","content":"Hello AgentWall!"}},"id":2}' | jq

curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"fs_read","arguments":{"path":"hello.txt"}},"id":3}' | jq

# Query database
curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"db_get_user","arguments":{"user_id":1}},"id":4}' | jq

# Fetch web content
curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"web_fetch","arguments":{"url":"https://api.example.com/users"}},"id":5}' | jq
```

## Run the Attack Demo

```bash
# Simulated demo (no live services needed)
cd gateway
python -m app.demo.run_demo

# Live demo (requires running stack and valid agent key)
python -m app.demo.run_demo --live
```

### What the Demo Shows

1. **Direct attack** on database server (bypassing AgentWall) → **SUCCEEDS** (steals fake credentials)
2. **Through AgentWall** with default-deny policy → **BLOCKED**
3. **Benign request** through AgentWall → **ALLOWED**

## Open the Dashboard

```bash
# Dashboard runs at http://localhost:3000
# Login with your agent API key

# Features:
# - Dashboard: System health, stats overview
# - Live Feed: Real-time tool calls with verdicts
# - Approvals: Review pending approval requests
# - Policies: View/edit access control policies
# - Agents: Manage agents and API keys
# - Tool Servers: View/sync upstream tools
# - Audit Log: Tamper-evident audit trail with integrity check
# - Settings: Gateway configuration
```

## Create a Policy to Allow Tool Access

```bash
# By default, all tool calls are DENIED (default-deny)
# Create an allow policy for fs_read:

curl -X POST http://localhost:8000/admin/policies \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{
    "name": "allow-fs-read-operator",
    "role": "operator",
    "tool_name": "fs_read",
    "action": "allow"
  }'

# Now fs_read calls will work for operator agents
```

## Trigger an Approval Request

```bash
# Create a policy requiring approval for fs_write
curl -X POST http://localhost:8000/admin/policies \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{
    "name": "require-approval-fs-write",
    "role": "operator",
    "tool_name": "fs_write",
    "action": "require_approval"
  }'

# Now try to write a file - it will go to approval queue
curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"fs_write","arguments":{"path":"needs_approval.txt","content":"test"}},"id":10}'

# Check approval queue in dashboard or via API:
curl -X GET http://localhost:8000/admin/approvals \
  -H "X-API-Key: $ADMIN_KEY"

# Approve it:
curl -X POST http://localhost:8000/admin/approvals/<approval_uuid>/decide \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{"approve": true, "reason": "Approved for demo"}'
```

## Run Evaluation (Red-Team)

```bash
cd gateway
python -m app.evaluation.run_evaluation

# Results saved to docs/evaluation/
# View report:
cat docs/evaluation/report.md
```

## Run Load Test

```bash
# Install locust
cd gateway && pip install ".[load]"

# Run headless load test (50 users, 10 spawn rate, 60 seconds)
locust -f app/benchmarks/locustfile.py --host=http://localhost:8000 --headless -u 50 -r 10 -t 60s

# Or with Makefile
make bench
```

### Expected Output

```
Total Requests: 12470
Total Failures: 2
Failure Rate: 0.02%
Avg Response Time: 12.3 ms
P50: 12.3 ms
P95: 28.7 ms
P99: 52.1 ms
Requests/sec: 1247
```

## Run Tests

```bash
# All tests
make test

# Gateway tests only
make test-gateway

# Dashboard tests only
make test-dashboard

# With coverage
cd gateway && pytest --cov=app --cov-report=html
# Open htmlcov/index.html
```

## Linting & Formatting

```bash
# Check linting
make lint

# Auto-fix
make format
```

## Stopping the Stack

```bash
# Stop containers (keep data)
docker compose down

# Stop and remove volumes (fresh start)
docker compose down -v
```

## Troubleshooting

### Gateway won't start

```bash
# Check logs
docker compose logs gateway

# Common issues:
# - Database not ready: wait longer, check `docker compose logs postgres`
# - Redis not ready: check `docker compose logs redis`
# - Port 8000 in use: change port in .env and docker-compose.yml
```

### Dashboard shows "Failed to fetch"

```bash
# Check gateway is accessible from dashboard container
docker compose exec dashboard curl http://gateway:8000/admin/health

# Check CORS settings in .env (CORS_ORIGINS)
```

### Agent authentication fails

```bash
# Verify API key is correct
curl -X GET http://localhost:8000/admin/agents \
  -H "X-API-Key: YOUR_KEY"

# Check agent exists and is active
docker compose exec gateway python -c "
from app.db.base import AsyncSessionLocal
from app.models import Agent
import asyncio

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent))
        for a in result.scalars().all():
            print(f'{a.name}: {a.role} active={a.is_active}')

asyncio.run(check())
"
```

### Database connection errors

```bash
# Reset database
docker compose down -v
docker compose up -d postgres
# Wait for healthy, then start gateway
docker compose up -d gateway
```

### Windows-specific Issues

| Issue | Solution |
|-------|----------|
| `docker compose` not found | Use Docker Desktop, enable "Use Docker Compose V2" |
| Path too long | Enable long paths: `git config --system core.longpaths true` |
| Line endings | Configure git: `git config --global core.autocrlf input` |
| Permission denied | Run PowerShell as Administrator or use WSL2 |

## Development Mode (Local)

```bash
# Terminal 1: PostgreSQL & Redis
docker compose up -d postgres redis

# Terminal 2: Gateway
cd gateway
pip install -e ".[dev]"
cp ../.env.example .env
# Edit .env with local URLs (localhost instead of service names)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Tool servers
cd tool_servers/filesystem && pip install -r requirements.txt && python server.py
cd tool_servers/database && pip install -r requirements.txt && python server.py
cd tool_servers/web_fetch && pip install -r requirements.txt && python server.py

# Terminal 4: Dashboard
cd dashboard
npm ci
npm run dev
```

## Useful Commands

```bash
# View gateway logs
docker compose logs -f gateway --tail 100

# Execute commands in gateway
docker compose exec gateway python -m app.demo.run_demo

# Database shell
docker compose exec postgres psql -U agentwall -d agentwall

# Redis CLI
docker compose exec redis redis-cli

# Check audit chain integrity
docker compose exec gateway python -c "
from app.db.base import AsyncSessionLocal
from app.services.audit_logger import AuditLogger
import asyncio

async def verify():
    async with AsyncSessionLocal() as db:
        logger = AuditLogger(db)
        valid, issues = await logger.verify_chain()
        print(f'Valid: {valid}, Issues: {len(issues)}')

asyncio.run(verify())
"
```