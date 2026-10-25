# AgentWall

**Zero-trust security gateway for AI agent tool calls**

AgentWall sits between AI agents and the tools they call (MCP-style JSON-RPC over HTTP), enforcing policy, blocking prompt-injection and data-exfiltration attempts, requiring human approval for risky actions, and keeping a tamper-evident audit log.

## Problem Statement

AI agents increasingly interact with external tools via standardized protocols like MCP (Model Context Protocol). Without proper safeguards, agents can be tricked into:
- Executing malicious code via prompt injection
- Leaking sensitive data (API keys, PII, credentials)
- Making unauthorized external requests
- Escalating privileges beyond their intended scope

AgentWall provides a security boundary that enforces zero-trust principles for every tool call.

## Architecture

```mermaid
graph TB
    subgraph "Agent Layer"
        A1[Agent 1]
        A2[Agent 2]
        A3[Agent N]
    end

    subgraph "AgentWall Gateway"
        GW[FastAPI Gateway\nPort 8000]
        PE[Policy Engine]
        TD[Threat Detection\nPrompt Injection + DLP]
        RL[Rate Limiter\nRedis]
        AQ[Approval Queue\nRedis]
        AL[Audit Logger\nPostgreSQL + Hash Chain]
    end

    subgraph "Upstream Tool Servers"
        FS[Filesystem Server\nPort 8001]
        DB[Database Server\nPort 8002]
        WF[Web Fetch Server\nPort 8003]
    end

    subgraph "Infrastructure"
        PG[(PostgreSQL)]
        RD[(Redis)]
    end

    subgraph "Dashboard"
        UI[React Dashboard\nPort 3000]
    end

    A1 -->|JSON-RPC\nX-API-Key| GW
    A2 -->|JSON-RPC\nX-API-Key| GW
    A3 -->|JSON-RPC\nX-API-Key| GW

    GW --> PE
    GW --> TD
    GW --> RL
    GW --> AQ
    GW --> AL

    PE -->|Allow/Deny/\nRequire Approval| GW
    TD -->|Block/Redact| GW
    RL -->|Rate Limit| GW
    AQ -->|Pending/Approved/\nDenied| GW
    AL -->|Hash-Chained\nAudit Log| PG

    GW -.->|Proxy| FS
    GW -.->|Proxy| DB
    GW -.->|Proxy| WF

    UI -->|REST API| GW
    UI -->|WebSocket| GW
```

## Threat Model

| Threat | Category | Mitigation |
|--------|----------|------------|
| Direct prompt injection | Injection | Heuristic patterns + ML classifier |
| Indirect injection (data exfil) | Injection | Pattern matching + egress allowlist |
| Encoding evasion (base64, unicode) | Evasion | Recursive decoding + pattern matching |
| Tool argument smuggling | Injection | Schema validation + argument inspection |
| Role escalation | Privilege | RBAC policies + pattern detection |
| Data exfiltration | Exfiltration | Egress allowlist + size/rate limits + DLP |
| PII/secret leakage | Data Loss | Regex-based DLP + redaction |
| Audit log tampering | Integrity | Hash-chained audit log |
| Runaway agent loops | Availability | Loop detection + rate limiting |

## Features

- **Zero-Trust Gateway**: Every tool call authenticated, authorized, and inspected
- **Policy-as-Code**: YAML/DB policies with allow/deny/require-approval by role, tool, arguments, time
- **Prompt Injection Detection**: Multi-layer (heuristics, encodings, optional ML)
- **Data Loss Prevention**: Detects/redacts API keys, passwords, PII, secrets
- **Egress Control**: Allowlist, rate limits, size limits, loop detection
- **Human-in-the-Loop**: Approval queue with timeout-to-deny
- **Tamper-Evident Audit**: Hash-chained log with integrity verification
- **Admin Dashboard**: Live feed, approvals, policies, agents, audit viewer
- **Demo Tool Servers**: Filesystem, Database (with fake credentials), Web Fetch

## Quick Start

```bash
# Prerequisites: Docker, Docker Compose
git clone https://github.com/shivacharanteja10/agentwall.git
cd agentwall
cp .env.example .env
# Edit .env with your settings (especially SECRET_KEY)
docker compose up -d
```

Open dashboard at http://localhost:3000

## Configuration

Key environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://agentwall:agentwall@localhost:5432/agentwall` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key | **Must change in production** |
| `FILESYSTEM_SERVER_URL` | Upstream FS server | `http://localhost:8001` |
| `DATABASE_SERVER_URL` | Upstream DB server | `http://localhost:8002` |
| `WEB_FETCH_SERVER_URL` | Upstream web server | `http://localhost:8003` |
| `EGRESS_ALLOWLIST` | Comma-separated allowed URLs | `http://localhost:8001,http://localhost:8002,http://localhost:8003` |
| `ENABLE_ML_CLASSIFIER` | Enable ML threat classifier | `false` |
| `ENABLE_DLP` | Enable data loss prevention | `true` |

## API Usage

### Agent Authentication

```bash
# Create an agent (requires admin key)
curl -X POST http://localhost:8000/admin/agents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -d '{"name": "my-agent", "role": "operator"}'

# Response includes API key (save it!)
```

### Make Tool Calls

```bash
# List tools
curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Call a tool
curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_AGENT_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"fs_read","arguments":{"path":"test.txt"}},"id":2}'
```

### Policy Management

```bash
# Create policy (admin only)
curl -X POST http://localhost:8000/admin/policies \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ADMIN_KEY" \
  -d '{
    "name": "allow-fs-read",
    "role": "operator",
    "tool_name": "fs_read",
    "action": "allow"
  }'
```

## Evaluation Results

### Red-Team Corpus

| Category | Samples |
|----------|---------|
| Direct Injection | 20 |
| Indirect Injection | 14 |
| Encoding Evasion | 25 (5 encodings × 5 payloads) |
| Role Escalation | 8 |
| Tool Smuggling | 6 |
| Exfiltration | 6 |
| **Total Attacks** | **79** |
| **Benign Samples** | **220** |

> **Note**: The corpus contains 79 unique attack patterns with encoding variations generating 200+ attack samples. Full 200+ unique attacks require additional pattern variations.

### Detection Metrics (Heuristic Only, ML Disabled)

| Metric | Value |
|--------|-------|
| Precision | 1.000 |
| Recall | 0.658 |
| F1 Score | 0.794 |
| Block Rate | 0.174 |
| False Positive Rate | 0.000 |

### Per-Category Breakdown

| Category | Samples | Precision | Recall | F1 |
|----------|---------|-----------|--------|-----|
| direct_injection | 20 | 1.000 | 0.900 | 0.947 |
| indirect_injection | 14 | 1.000 | 0.857 | 0.923 |
| encoding_evasion | 25 | 1.000 | 0.440 | 0.611 |
| role_escalation | 8 | 1.000 | 1.000 | 1.000 |
| tool_smuggling | 6 | 1.000 | 0.500 | 0.667 |
| exfiltration | 6 | 0.000 | 0.000 | 0.000 |
| benign | 220 | 0.000 | 0.000 | 0.000 |

### Baseline Comparison (AgentWall Disabled)

| Metric | With AgentWall | Without AgentWall |
|--------|----------------|-------------------|
| Attack Success Rate | 34.2% | 100% |
| Data Leakage | 0 incidents | 79 incidents |

## Performance Benchmarks

### Test Environment

- **Machine**: 8 vCPU, 16 GB RAM (GitHub Actions runner)
- **Gateway**: 2 workers, Python 3.11
- **Database**: PostgreSQL 16 (local)
- **Cache**: Redis 7 (local)

### Results (50 concurrent users, 60s)

| Metric | Gateway | Direct (Baseline) | Overhead |
|--------|---------|-------------------|----------|
| Requests/sec | 1,247 | 3,891 | 68% |
| P50 Latency | 12.3 ms | 4.1 ms | +8.2 ms |
| P95 Latency | 28.7 ms | 9.8 ms | +18.9 ms |
| P99 Latency | 52.1 ms | 18.4 ms | +33.7 ms |
| Error Rate | 0.02% | 0.01% | +0.01% |

### Analysis

The gateway adds ~8-19ms median overhead per request, primarily from:
1. Policy evaluation (~2ms)
2. Threat detection (~3ms)
3. DLP scanning (~2ms)
4. Audit logging (~1ms)
5. Upstream proxy (~1ms)

Throughput is limited by synchronous upstream calls; async batching would improve this.

## Design Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Default-deny policies | Security first; explicit allow | More policy management overhead |
| Heuristic threat detection | Works offline, no ML dependencies | Higher false positives than ML |
| Hash-chained audit log | Tamper-evident without external deps | Verification O(n), no merkle tree |
| Redis for rate limiting | Fast, distributed, supports sliding window | Additional infrastructure dependency |
| JSON-RPC 2.0 over HTTP | MCP compatibility, firewall-friendly | Not gRPC/WebSocket native |
| Sync upstream calls | Simplicity, correct ordering | Limits throughput vs async |

## Limitations

1. **ML Classifier Disabled by Default**: Requires `ENABLE_ML_CLASSIFIER=true` and model at `ML_MODEL_PATH`. Without it, sophisticated obfuscated attacks may bypass heuristics.

2. **Encoding Detection Coverage**: Current implementation handles base64, URL, unicode, HTML, hex, octal. Novel encodings (e.g., custom ciphers, steganography) not detected.

3. **Tool Smuggling**: Argument pattern matching is regex-based. Deeply nested or polymorphic payloads may evade detection.

4. **Egress Control**: Allowlist is static (configured at startup). Dynamic allowlist updates require gateway restart.

5. **Audit Log Scalability**: Hash chain verification is O(n). For high-volume deployments, consider periodic checkpoints or Merkle tree.

6. **Single-Region Deployment**: No built-in multi-region HA. For production, deploy behind load balancer with shared PostgreSQL/Redis.

7. **No Encryption at Rest**: Audit logs stored in plaintext in PostgreSQL. Enable disk encryption for compliance.

8. **Limited Policy Expressiveness**: Policies support regex on string args only. Complex conditions (numeric ranges, cross-field) not supported.

## Known Bypasses

| Bypass | Category | Status |
|--------|----------|--------|
| Nested JSON with injection in deep fields | Tool Smuggling | Partial - only top-level args checked |
| Homoglyph attacks (lookalike chars) | Encoding | Not detected |
| Multi-turn injection across calls | Injection | Not detected (stateless per-call) |
| Timing-based exfiltration | Exfiltration | Not detected |
| Policy confusion via tool aliasing | Policy | Possible if tool names similar |
| Exfiltration patterns not in threat detector | Exfiltration | 0% recall in threat detector (gateway uses egress controls) |
| Novel encoding schemes | Encoding | Not detected by heuristic patterns |

## License

MIT License - see [LICENSE](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `make test`
4. Run linting: `make lint`
5. Submit a PR