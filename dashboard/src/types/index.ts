export interface Agent {
  id: number;
  uuid: string;
  name: string;
  role: 'admin' | 'operator' | 'viewer' | 'automated';
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
}

export interface ToolServer {
  id: number;
  name: string;
  base_url: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Tool {
  id: number;
  server_id: number;
  name: string;
  description: string | null;
  input_schema: Record<string, any>;
  output_schema: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Policy {
  id: number;
  name: string;
  description: string | null;
  role: 'admin' | 'operator' | 'viewer' | 'automated';
  tool_name: string | null;
  action: 'allow' | 'deny' | 'require_approval';
  argument_pattern: Record<string, any> | null;
  time_window_start: string | null;
  time_window_end: string | null;
  priority: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ToolCall {
  id: number;
  uuid: string;
  agent_id: number | null;
  tool_name: string;
  arguments: Record<string, any>;
  result: Record<string, any> | null;
  status: 'allowed' | 'denied' | 'pending_approval' | 'approved' | 'redacted' | 'error';
  policy_id: number | null;
  approval_id: number | null;
  threat_detected: boolean;
  threat_details: Record<string, any> | null;
  dlp_redacted: boolean;
  dlp_details: Record<string, any> | null;
  created_at: string;
  completed_at: string | null;
}

export interface ApprovalRequest {
  id: number;
  uuid: string;
  tool_call_id: number;
  agent_id: number | null;
  tool_name: string;
  arguments: Record<string, any>;
  reason: string;
  status: 'pending' | 'approved' | 'denied' | 'expired';
  requested_by: number | null;
  decided_by: number | null;
  decision_reason: string | null;
  expires_at: string;
  created_at: string;
  decided_at: string | null;
}

export interface AuditStats {
  total_calls: number;
  by_status: Record<string, number>;
  threats_detected: number;
  dlp_redactions: number;
}

export interface ApprovalStats {
  pending: number;
  expired: number;
  approved: number;
  denied: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  redis: string;
  timestamp: string;
}