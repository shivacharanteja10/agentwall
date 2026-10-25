import { useEffect, useState } from 'react';
import { Plus, Edit, Trash2, RefreshCw, Shield, AlertTriangle, CheckCircle, XCircle, FileText } from 'lucide-react';
import { apiClient } from '../api';
import { getRoleColor, getStatusColor } from '../lib/utils';
import type { Policy } from '../types';

export function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<Policy | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    role: 'viewer' as Policy['role'],
    tool_name: '',
    action: 'allow' as Policy['action'],
    argument_pattern: '',
    time_window_start: '',
    time_window_end: '',
    priority: 0,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const fetchPolicies = async () => {
    try {
      const data = await apiClient.listPolicies({ active_only: false });
      setPolicies(data);
    } catch (err) {
      console.error('Failed to fetch policies:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      role: 'viewer',
      tool_name: '',
      action: 'allow',
      argument_pattern: '',
      time_window_start: '',
      time_window_end: '',
      priority: 0,
    });
    setEditingPolicy(null);
    setError('');
  };

  const openCreateModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (policy: Policy) => {
    setFormData({
      name: policy.name,
      description: policy.description ?? '',
      role: policy.role,
      tool_name: policy.tool_name ?? '',
      action: policy.action,
      argument_pattern: policy.argument_pattern ? JSON.stringify(policy.argument_pattern, null, 2) : '',
      time_window_start: policy.time_window_start ?? '',
      time_window_end: policy.time_window_end ?? '',
      priority: policy.priority,
    });
    setEditingPolicy(policy);
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      let argPattern: Record<string, any> | undefined;
      if (formData.argument_pattern.trim()) {
        try {
          argPattern = JSON.parse(formData.argument_pattern);
        } catch {
          setError('Invalid JSON in argument pattern');
          setSubmitting(false);
          return;
        }
      }

      const data = {
        name: formData.name,
        description: formData.description || undefined,
        role: formData.role,
        tool_name: formData.tool_name || undefined,
        action: formData.action,
        argument_pattern: argPattern,
        time_window_start: formData.time_window_start || undefined,
        time_window_end: formData.time_window_end || undefined,
        priority: formData.priority,
      };

      if (editingPolicy) {
        await apiClient.updatePolicy(editingPolicy.id, data);
      } else {
        await apiClient.createPolicy(data);
      }

      setShowModal(false);
      fetchPolicies();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Failed to save policy');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this policy?')) return;
    try {
      await apiClient.deletePolicy(id);
      fetchPolicies();
    } catch (err) {
      alert('Failed to delete policy');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Policies</h1>
          <p className="text-gray-500">Manage access control policies for agents and tools</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchPolicies}
            disabled={loading}
            className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            aria-label="Refresh"
          >
            <RefreshCw className={cn('w-5 h-5', loading && 'animate-spin')} />
          </button>
          <button onClick={openCreateModal} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Create Policy
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tool</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Action</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Time Window</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Priority</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {policies.map((policy) => (
                <tr key={policy.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{policy.name}</div>
                    {policy.description && (
                      <div className="text-sm text-gray-500 max-w-xs truncate" title={policy.description}>
                        {policy.description}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('px-2 py-1 rounded text-xs font-medium', getRoleColor(policy.role))}>
                      {policy.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {policy.tool_name || <span className="text-gray-400">All tools</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('px-2 py-1 rounded text-xs font-medium',
                      policy.action === 'allow' ? 'bg-green-100 text-green-800' :
                      policy.action === 'deny' ? 'bg-red-100 text-red-800' :
                      'bg-yellow-100 text-yellow-800'
                    )}>
                      {policy.action.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {policy.time_window_start && policy.time_window_end
                      ? `${policy.time_window_start} - ${policy.time_window_end}`
                      : policy.time_window_start
                      ? `From ${policy.time_window_start}`
                      : policy.time_window_end
                      ? `Until ${policy.time_window_end}`
                      : <span className="text-gray-400">Always</span>}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{policy.priority}</td>
                  <td className="px-4 py-3">
                    <span className={cn('px-2 py-1 rounded text-xs font-medium',
                      policy.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    )}>
                      {policy.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openEditModal(policy)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                        aria-label="Edit policy"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(policy.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        aria-label="Delete policy"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {policies.length === 0 && (
          <div className="p-12 text-center">
            <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No policies yet</h3>
            <p className="text-gray-500 mb-4">Create your first policy to start controlling agent access</p>
            <button onClick={openCreateModal} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700">
              Create Policy
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">{editingPolicy ? 'Edit Policy' : 'Create Policy'}</h2>
              <button onClick={() => setShowModal(false)} className="p-1 text-gray-400 hover:text-gray-600">×</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {error && <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as Policy['role'] })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  >
                    <option value="admin">Admin</option>
                    <option value="operator">Operator</option>
                    <option value="viewer">Viewer</option>
                    <option value="automated">Automated</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  rows={2}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tool Name (optional)</label>
                  <input
                    type="text"
                    value={formData.tool_name}
                    onChange={(e) => setFormData({ ...formData, tool_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                    placeholder="Leave empty for all tools"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Action *</label>
                  <select
                    value={formData.action}
                    onChange={(e) => setFormData({ ...formData, action: e.target.value as Policy['action'] })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  >
                    <option value="allow">Allow</option>
                    <option value="deny">Deny</option>
                    <option value="require_approval">Require Approval</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Argument Pattern (JSON, optional)</label>
                <textarea
                  value={formData.argument_pattern}
                  onChange={(e) => setFormData({ ...formData, argument_pattern: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none font-mono text-sm"
                  rows={3}
                  placeholder='{"path": ".*secret.*"}'
                />
                <p className="text-xs text-gray-500 mt-1">Regex patterns on argument values. Leave empty for no filtering.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Time Window Start (HH:MM)</label>
                  <input
                    type="time"
                    value={formData.time_window_start}
                    onChange={(e) => setFormData({ ...formData, time_window_start: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Time Window End (HH:MM)</label>
                  <input
                    type="time"
                    value={formData.time_window_end}
                    onChange={(e) => setFormData({ ...formData, time_window_end: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                  <input
                    type="number"
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200">
                  Cancel
                </button>
                <button type="submit" disabled={submitting} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2">
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>{editingPolicy ? 'Update' : 'Create'}</span>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

import { cn } from '../lib/utils';
import { Loader2 } from 'lucide-react';