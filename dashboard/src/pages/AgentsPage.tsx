import { useEffect, useState } from 'react';
import { Plus, Trash2, RefreshCw, Copy, Check, Loader2, Key, Shield, User, Bot, Eye } from 'lucide-react';
import { apiClient } from '../api';
import { getRoleColor, formatRelativeTime } from '../lib/utils';
import type { Agent } from '../types';

export function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ name: '', role: 'viewer' as Agent['role'] });
  const [submitting, setSubmitting] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);

  const fetchAgents = async () => {
    try {
      const data = await apiClient.listAgents();
      setAgents(data);
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const result = await apiClient.createAgent(formData);
      setNewApiKey(result.api_key);
      setShowModal(false);
      fetchAgents();
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Failed to create agent');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this agent? This will revoke their API key.')) return;
    try {
      await apiClient.deleteAgent(id);
      fetchAgents();
    } catch (err) {
      alert('Failed to delete agent');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopySuccess('Copied!');
    setTimeout(() => setCopySuccess(null), 2000);
  };

  const openCreateModal = () => {
    setFormData({ name: '', role: 'viewer' });
    setNewApiKey(null);
    setShowModal(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
          <p className="text-gray-500">Manage agent identities and API keys</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchAgents}
            disabled={loading}
            className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            aria-label="Refresh"
          >
            <RefreshCw className={cn('w-5 h-5', loading && 'animate-spin')} />
          </button>
          <button onClick={openCreateModal} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Create Agent
          </button>
        </div>
      </div>

      {newApiKey && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-6" role="alert">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-medium text-green-900">Agent created successfully!</h3>
              <p className="text-green-700 mt-1">Save this API key now - it won't be shown again.</p>
              <div className="mt-4 flex items-center gap-3">
                <code className="flex-1 bg-green-100 px-3 py-2 rounded font-mono text-sm break-all" id="new-key">{newApiKey}</code>
                <button
                  onClick={() => copyToClipboard(newApiKey)}
                  className="px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 flex items-center gap-2"
                >
                  <Copy className="w-4 h-4" />
                  {copySuccess === 'Copied!' ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <button
                onClick={() => setNewApiKey(null)}
                className="mt-3 text-sm text-green-600 hover:underline"
              >
                I've saved the key, continue
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {agents.length === 0 ? (
          <div className="p-12 text-center">
            <Key className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No agents yet</h3>
            <p className="text-gray-500 mb-4">Create your first agent to start using AgentWall</p>
            <button onClick={openCreateModal} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700">
              Create Agent
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Last Seen</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Created</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {agents.map((agent) => (
                  <tr key={agent.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className={cn('w-10 h-10 rounded-full flex items-center justify-center',
                          agent.role === 'admin' ? 'bg-purple-100' :
                          agent.role === 'operator' ? 'bg-blue-100' :
                          agent.role === 'automated' ? 'bg-gray-100' : 'bg-green-100'
                        )}>
                          {agent.role === 'automated' ? (
                            <Bot className={cn('w-5 h-5', agent.role === 'automated' ? 'text-gray-600' : agent.role === 'admin' ? 'text-purple-600' : agent.role === 'operator' ? 'text-blue-600' : 'text-green-600')} />
                          ) : (
                            <User className={cn('w-5 h-5', agent.role === 'admin' ? 'text-purple-600' : agent.role === 'operator' ? 'text-blue-600' : 'text-green-600')} />
                          )}
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">{agent.name}</div>
                          <div className="text-xs text-gray-500 font-mono">{agent.uuid.slice(0, 8)}...</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn('px-2 py-1 rounded text-xs font-medium', getRoleColor(agent.role))}>
                        {agent.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn('inline-flex items-center gap-1.5 text-sm',
                        agent.is_active ? 'text-green-700' : 'text-gray-500'
                      )}>
                        <span className={cn('w-2 h-2 rounded-full', agent.is_active ? 'bg-green-500' : 'bg-gray-400')} />
                        {agent.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {agent.last_seen_at ? formatRelativeTime(agent.last_seen_at) : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatRelativeTime(agent.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleDelete(agent.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        aria-label="Delete agent"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Agent Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-xl max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">Create Agent</h2>
              <button onClick={() => setShowModal(false)} className="p-1 text-gray-400 hover:text-gray-600">×</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Role *</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value as Agent['role'] })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                >
                  <option value="viewer">Viewer (read-only)</option>
                  <option value="operator">Operator (read + approve)</option>
                  <option value="admin">Admin (full access)</option>
                  <option value="automated">Automated (machine agent)</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200">
                  Cancel
                </button>
                <button type="submit" disabled={submitting} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2">
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Create Agent</span>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="bg-gray-50 rounded-xl p-6 border border-gray-200">
        <h3 className="text-lg font-medium text-gray-900 mb-3">API Key Usage</h3>
        <p className="text-gray-600 mb-4">Include the API key in requests via the <code className="bg-white px-2 py-1 rounded font-mono text-sm">X-API-Key</code> header:</p>
        <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto text-sm">
{`curl -X POST http://localhost:8000/api/v1/rpc \
  -H "Content-Type: application/json" \
  -H "X-API-Key: aw_your_api_key_here" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "fs_read",
      "arguments": { "path": "test.txt" }
    },
    "id": 1
  }'`}
        </pre>
      </div>
    </div>
  );
}

import { cn } from '../lib/utils';
import { CheckCircle } from 'lucide-react';