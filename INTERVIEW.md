# INTERVIEW.md - 20 Likely Interview Questions

## Security & Threat Modeling

### 1. What is the threat model for AgentWall? What are you defending against?

**Answer:** AgentWall defends against compromised or malicious AI agents making tool calls. The threat model assumes:
- Agents authenticate via API keys/JWT but may be tricked (prompt injection)
- Upstream tool servers are trusted but may expose sensitive operations
- Network between gateway and tools is semi-trusted (hence egress allowlist)
- Audit logs must be tamper-evident even if database is compromised

Key threats: direct/indirect prompt injection, data exfiltration, privilege escalation, tool argument smuggling, encoding evasion, runaway loops.

### 2. Explain the types of prompt injection AgentWall detects. How does the layered detector work?

**Answer:** Three layers:

1. **Heuristic patterns** (regex): Direct injection (`ignore previous instructions`, `system:`), indirect (`exfiltrate`, `send data to`), role escalation (`admin`, `sudo`, `bypass auth`), code execution (`eval`, `exec`, `subprocess`).

2. **Encoding detection**: Recursively decodes base64, URL encoding, unicode escapes, HTML entities, hex/octal escapes, then re-scans decoded content.

3. **Optional ML classifier**: Transformer-based (DistilBERT) for semantic detection, disabled by default for offline operation.

Each layer produces confidence scores; combined threshold >0.5 triggers block.

### 3. Why default-deny instead of default-allow for policies?

**Answer:** Zero-trust principle. In a security gateway, unknown tool calls should be rejected. Default-allow would require anticipating every possible attack to write deny rules—impossible. Default-deny forces explicit authorization, reducing blast radius of policy gaps. Operators must consciously approve each tool/role combination.

### 4. How does the hash-chained audit log provide tamper evidence?

**Answer:** Each audit record stores:
- `request_hash`: SHA256 of canonical request data
- `previous_hash`: Chain hash of previous record
- `chain_hash`: SHA256(previous_hash + ":" + request_hash) — or just request_hash for first record

Verification recomputes all three values sequentially. Any modification to request data, deletion, reordering, or insertion breaks the chain at that point and all subsequent records. Detection is O(n) with single pass.

### 5. What's the difference between DLP redaction and threat blocking?

**Answer:**
- **Threat blocking**: Stops the tool call entirely before it reaches upstream. Returns error to agent. Used for prompt injection, policy violations, loop detection.
- **DLP redaction**: Allows call to proceed, but scrubs sensitive data (API keys, PII, secrets) from the *response* before returning to agent. Used for accidental leakage in legitimate tool outputs.

Both are logged in audit trail with `threat_detected` and `dlp_redacted` flags.

## Architecture & Design

### 6. Why JSON-RPC 2.0 over HTTP instead of gRPC or WebSockets?

**Answer:** MCP (Model Context Protocol) uses JSON-RPC 2.0. HTTP/JSON is:
- Firewall/proxy friendly (port 80/443)
- Human-readable for debugging
- Language-agnostic, no codegen needed
- Works with existing MCP tool servers
- Stateless, scales horizontally easily

gRPC would require protobuf schemas and HTTP/2; WebSockets add connection state complexity.

### 7. How does the policy engine evaluate rules? What's the priority order?

**Answer:** Policies filtered by agent role, ordered by `priority DESC, id ASC`. First match wins:
1. `allow` → ALLOWED
2. `deny` → DENIED
3. `require_approval` → PENDING_APPROVAL
4. No match → DENIED (default)

Time window and argument pattern (regex on string args) are additional match conditions.

### 8. How does the approval queue work? What prevents indefinite hanging?

**Answer:** When policy requires approval:
1. Tool call logged with `PENDING_APPROVAL` status
2. ApprovalRequest created in Redis/PostgreSQL with `expires_at` (default 5 min)
3. Agent receives structured response with `approval_id` and `expires_at`
4. Human reviews via dashboard/API, calls `/decide` with approve/deny
5. On approve: tool call proceeds to upstream; on deny/expire: DENIED

Timeout-to-deny prevents indefinite blocking. Background job expires stale requests.

### 9. How does rate limiting work? Sliding window or fixed?

**Answer:** Sliding window using Redis sorted sets (or INCR with time-bucketed keys). Each agent has a counter per time window. Key: `ratelimit:{agent_id}:{window_number}`. Expires after 2 windows. Allows burst at window boundaries but enforces average rate. Configurable per-agent via policy (future) or global settings.

### 10. How do you handle egress control for outbound HTTP calls?

**Answer:** Three layers:
1. **Allowlist**: Only pre-configured URL bases (scheme+host) permitted. Checked before any outbound request.
2. **Rate/size limits**: Per-agent per-URL rate limiting (default 10/min), response size limit (default 10MB).
3. **Loop detection**: Tracks call patterns per agent; flags alternating A→B→A→B or high-frequency same-tool calls.

All enforced in gateway before proxying to upstream tool servers.

## Implementation Details

### 11. How do you validate tool arguments against JSON Schema?

**Answer:** Basic validation in `policy_engine.validate_arguments_against_schema()`:
- Checks required fields present
- Validates primitive types (string, number, integer, boolean, array, object, null)
- Does NOT validate complex constraints (enum, format, min/max, pattern, additionalProperties)

Production would use `jsonschema` library. Current implementation catches obvious errors fast.

### 12. How is agent identity established? API keys vs JWT?

**Answer:** Two methods:
- **API Key**: `X-API-Key` header, hashed with bcrypt in DB. Long-lived, suitable for automated agents.
- **JWT**: `Authorization: Bearer <token>`, signed with HS256. Short-lived (30 min default), includes `sub` (agent UUID) and `role`.

Both validated in `get_current_agent` dependency. API keys preferred for machine agents; JWT for human-in-the-loop scenarios.

### 13. How do you handle database migrations?

**Answer:** Alembic with async SQLAlchemy. Migration files in `gateway/app/alembic/versions/`. Run with `alembic upgrade head` on startup (via `init_db()`) or manually via `make migrate`. Models defined in `app/models/__init__.py` with declarative base.

### 14. How does the dashboard communicate with the gateway?

**Answer:** REST API calls to `/admin/*` endpoints with same `X-API-Key` authentication. Dashboard is a SPA (React + Vite) served by nginx, which proxies `/api` to gateway. Real-time updates via polling (5s for live feed, 10s for approvals). WebSocket support planned for future.

### 15. What's the deployment topology for production?

**Answer:** Recommended:
- Gateway: 3+ replicas behind load balancer (AWS ALB, GCP Cloud Load Balancing)
- PostgreSQL: Managed (RDS, Cloud SQL) with read replicas
- Redis: Managed (ElastiCache, Memorystore) with replication
- Tool servers: Separate scaling per tool type
- Dashboard: Static files on CDN (S3+CloudFront, GCS+Cloud CDN)
- Secrets: External secret manager (AWS Secrets Manager, HashiCorp Vault)

## Operations & Observability

### 16. How do you monitor AgentWall in production?

**Answer:** 
- **Metrics**: Prometheus `/metrics` endpoint (request count, latency, policy decisions, threat detections, approval queue depth)
- **Logs**: Structured JSON logs via structlog (request ID, agent ID, tool, verdict, latency)
- **Health**: `/admin/health` checks DB, Redis, upstream tool servers
- **Audit verification**: Periodic `verify_chain` job alerts on integrity failures
- **Alerting**: High threat detection rate, approval queue backlog, error rate spikes

### 17. How do you rotate secrets (API keys, JWT secret)?

**Answer:**
- **Agent API keys**: Create new agent, migrate callers, delete old agent. Keys never rotated in-place.
- **JWT secret**: Set new `SECRET_KEY` in env, deploy. Existing tokens invalid immediately (stateless). Plan for brief auth disruption.
- **Database password**: Use managed DB rotation (AWS RDS rotation) or manual: update `.env`, restart gateway.

### 18. How do you handle gateway upgrades without downtime?

**Answer:** Blue-green or rolling deployment:
1. New version starts, runs migrations (backward-compatible)
2. Health checks pass
3. Load balancer shifts traffic
4. Old version drains connections, stops
5. Audit chain continues (same DB)

Database migrations must be additive-only (new columns/tables, no drops/renames in same version).

## Trade-offs & Future Work

### 19. What are the latency vs. security trade-offs in your design?

**Answer:** 
- **Added latency**: ~8-19ms median overhead (policy + threat + DLP + audit)
- **Throughput**: Sync upstream proxy limits RPS; async would improve but adds complexity
- **False positives**: Heuristic detection tuned for recall over precision; some benign calls blocked
- **ML classifier**: Would improve precision but adds ~50-100ms latency and model dependency

### 20. What would you improve next?

**Answer:**
1. **Async upstream proxy** with connection pooling for higher throughput
2. **ML classifier integration** (DistilBERT fine-tuned on injection data) with ONNX Runtime for low latency
3. **Merkle tree audit log** for O(log n) verification and incremental checkpoints
4. **Dynamic policy updates** via config map / etcd without restart
5. **Multi-region active-active** with conflict-free audit log replication
6. **Policy testing sandbox** in dashboard (dry-run mode)
7. **Structured DLP rules** (YAML) instead of hardcoded regex
8. **OpenTelemetry tracing** across gateway → tool servers