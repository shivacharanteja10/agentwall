import axios from 'axios';
import type { Agent, ToolServer, Tool, Policy, ToolCall, ApprovalRequest, AuditStats, ApprovalStats, HealthResponse } from './types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE}/admin`,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('agentwall_api_key');
  if (token) {
    config.headers['X-API-Key'] = token;
  }
  return config;
});

export const apiClient = {
  // Health
  async health(): Promise<HealthResponse> {
    const res = await api.get('/health');
    return res.data;
  },

  // Agents
  async listAgents(): Promise<Agent[]> {
    const res = await api.get('/agents');
    return res.data;
  },

  async createAgent(data: { name: string; role: Agent['role'] }): Promise<Agent & { api_key: string }> {
    const res = await api.post('/agents', data);
    return res.data;
  },

  async deleteAgent(id: number): Promise<void> {
    await api.delete(`/agents/${id}`);
  },

  // Tool Servers
  async listToolServers(): Promise<ToolServer[]> {
    const res = await api.get('/tool-servers');
    return res.data;
  },

  async createToolServer(data: { name: string; base_url: string; description?: string }): Promise<ToolServer> {
    const res = await api.post('/tool-servers', data);
    return res.data;
  },

  async syncToolServer(id: number): Promise<{ synced: number; tools: string[] }> {
    const res = await api.post(`/tool-servers/${id}/sync`);
    return res.data;
  },

  // Tools
  async listTools(params?: { server_id?: number; active_only?: boolean }): Promise<Tool[]> {
    const res = await api.get('/tools', { params });
    return res.data;
  },

  // Policies
  async listPolicies(params?: { role?: string; active_only?: boolean }): Promise<Policy[]> {
    const res = await api.get('/policies', { params });
    return res.data;
  },

  async createPolicy(data: {
    name: string;
    description?: string;
    role: Policy['role'];
    tool_name?: string;
    action: Policy['action'];
    argument_pattern?: Record<string, any>;
    time_window_start?: string;
    time_window_end?: string;
    priority?: number;
  }): Promise<Policy> {
    const res = await api.post('/policies', data);
    return res.data;
  },

  async updatePolicy(id: number, data: Partial<Policy>): Promise<Policy> {
    const res = await api.patch(`/policies/${id}`, data);
    return res.data;
  },

  async deletePolicy(id: number): Promise<void> {
    await api.delete(`/policies/${id}`);
  },

  // Approvals
  async listApprovals(params?: { status?: string; limit?: number; offset?: number }): Promise<ApprovalRequest[]> {
    const res = await api.get('/approvals', { params });
    return res.data;
  },

  async getApproval(uuid: string): Promise<ApprovalRequest> {
    const res = await api.get(`/approvals/${uuid}`);
    return res.data;
  },

  async decideApproval(uuid: string, decision: { approve: boolean; reason?: string }): Promise<ApprovalRequest> {
    const res = await api.post(`/approvals/${uuid}/decide`, decision);
    return res.data;
  },

  async getApprovalStats(): Promise<ApprovalStats> {
    const res = await api.get('/approvals/stats');
    return res.data;
  },

  // Audit
  async listAudit(params?: {
    agent_id?: number;
    tool_name?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<ToolCall[]> {
    const res = await api.get('/audit', { params });
    return res.data;
  },

  async getAuditStats(): Promise<AuditStats> {
    const res = await api.get('/audit/stats');
    return res.data;
  },

  async verifyAuditChain(limit?: number): Promise<{ valid: boolean; issues_count: number; issues: any[] }> {
    const res = await api.post('/audit/verify', null, { params: { limit } });
    return res.data;
  },
};

export default apiClient;