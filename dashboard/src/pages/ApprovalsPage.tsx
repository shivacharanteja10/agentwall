import { useEffect, useState } from 'react';
import { RefreshCw, Clock, CheckCircle, XCircle, Eye, Loader2, AlertTriangle } from 'lucide-react';
import { apiClient } from '../api';
import { formatRelativeTime, getStatusColor, jsonStringify, truncate } from '../lib/utils';
import type { ApprovalRequest } from '../types';

export function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
  const [processing, setProcessing] = useState<string | null>(null);

  const fetchApprovals = async () => {
    try {
      const data = await apiClient.listApprovals({ status: statusFilter === 'all' ? undefined : statusFilter });
      setApprovals(data);
    } catch (err) {
      console.error('Failed to fetch approvals:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
    const interval = setInterval(fetchApprovals, 10000);
    return () => clearInterval(interval);
  }, [statusFilter]);

  const handleDecision = async (uuid: string, approve: boolean) => {
    setProcessing(uuid);
    try {
      await apiClient.decideApproval(uuid, { approve, reason: approve ? 'Approved via dashboard' : 'Denied via dashboard' });
      fetchApprovals();
    } catch (err) {
      alert('Failed to process approval');
    } finally {
      setProcessing(null);
    }
  };

  const isExpired = (expiresAt: string) => new Date(expiresAt) < new Date();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Approval Queue</h1>
          <p className="text-gray-500">Review and decide on pending tool call approvals</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          >
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="denied">Denied</option>
            <option value="expired">Expired</option>
            <option value="all">All</option>
          </select>
          <button
            onClick={fetchApprovals}
            disabled={loading}
            className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            aria-label="Refresh"
          >
            <RefreshCw className={cn('w-5 h-5', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {approvals.length === 0 && statusFilter === 'pending' && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No pending approvals</h3>
          <p className="text-gray-500">All caught up! New approval requests will appear here.</p>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tool</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Agent</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Reason</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Expires</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {approvals.map((approval) => (
                <tr key={approval.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{approval.tool_name}</div>
                    <div className="text-sm text-gray-500 max-w-xs truncate" title={jsonStringify(approval.arguments)}>
                      {truncate(jsonStringify(approval.arguments), 60)}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">Agent #{approval.agent_id ?? 'N/A'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 max-w-md truncate" title={approval.reason}>
                    {approval.reason}
                  </td>
                  <td className="px-4 py-3">
                    <div className={cn('text-sm font-medium', isExpired(approval.expires_at) && approval.status === 'pending' ? 'text-red-600' : 'text-gray-600')}>
                      {formatRelativeTime(approval.expires_at)}
                    </div>
                    <div className="text-xs text-gray-400">{approval.created_at}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('px-2 py-1 rounded text-xs font-medium', getStatusColor(approval.status))}>
                      {approval.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {approval.status === 'pending' && !isExpired(approval.expires_at) ? (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleDecision(approval.uuid, true)}
                          disabled={processing === approval.uuid}
                          className="px-3 py-1.5 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-1"
                        >
                          {processing === approval.uuid ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                          <span className="hidden sm:inline">Approve</span>
                        </button>
                        <button
                          onClick={() => handleDecision(approval.uuid, false)}
                          disabled={processing === approval.uuid}
                          className="px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-1"
                        >
                          {processing === approval.uuid ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                          <span className="hidden sm:inline">Deny</span>
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setSelectedApproval(approval)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                        aria-label="View details"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {loading && (
          <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-center gap-2 text-sm text-gray-500">
            <span className="animate-spin">⟳</span> Loading...
          </div>
        )}
      </div>
    </div>
  );
}

import { cn } from '../lib/utils';