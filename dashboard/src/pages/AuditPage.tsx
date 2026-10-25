import { useEffect, useState } from 'react';
import { RefreshCw, Shield, AlertTriangle, FileText, CheckCircle, Loader2, Search, Filter, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { apiClient } from '../api';
import { formatRelativeTime, getStatusColor, jsonStringify, truncate } from '../lib/utils';
import type { ToolCall } from '../types';

export function AuditPage() {
  const [calls, setCalls] = useState<ToolCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean; issues_count: number; issues: any[] } | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedCall, setSelectedCall] = useState<ToolCall | null>(null);

  const fetchCalls = async () => {
    try {
      const data = await apiClient.listAudit({ limit: pageSize, offset: (page - 1) * pageSize });
      setCalls(data);
      // Estimate total pages (in real app, API would return total count)
      setTotalPages(Math.max(1, Math.ceil(data.length / pageSize) + (page - 1)));
    } catch (err) {
      console.error('Failed to fetch audit log:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const result = await apiClient.verifyAuditChain();
      setVerifyResult(result);
    } catch (err) {
      alert('Failed to verify audit chain');
    } finally {
      setVerifying(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, [page]);

  const statusOptions = ['all', 'allowed', 'denied', 'pending_approval', 'approved', 'redacted', 'error'];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-gray-500">Tamper-evident audit trail with hash chaining</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
          >
            {verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
            <span>Verify Chain</span>
          </button>
          <button
            onClick={fetchCalls}
            disabled={loading}
            className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            aria-label="Refresh"
          >
            <RefreshCw className={cn('w-5 h-5', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {verifyResult && (
        <div className={cn('p-4 rounded-lg border flex items-center justify-between', verifyResult.valid ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200')}>
          <div className="flex items-center gap-3">
            {verifyResult.valid ? (
              <CheckCircle className="w-6 h-6 text-green-600" />
            ) : (
              <AlertTriangle className="w-6 h-6 text-red-600" />
            )}
            <div>
              <p className="font-medium text-gray-900">
                {verifyResult.valid ? 'Audit chain is valid' : 'Audit chain integrity compromised!'}
              </p>
              <p className="text-sm text-gray-500">
                {verifyResult.valid ? 'All hash chains verified successfully' : `${verifyResult.issues_count} issue(s) detected`}
              </p>
            </div>
          </div>
          {!verifyResult.valid && (
            <button className="px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700">
              View Issues
            </button>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search tool name, arguments, result..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none w-full sm:w-48"
          >
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s === 'all' ? 'All Statuses' : s.replace('_', ' ')}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Audit Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tool</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Agent</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Arguments</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Threats</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">DLP</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Chain</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {calls.map((call) => (
                <tr key={call.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setSelectedCall(call)}>
                  <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                    {formatRelativeTime(call.created_at)}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{call.tool_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {call.agent_id ? `Agent #${call.agent_id}` : 'Unknown'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 max-w-md truncate" title={jsonStringify(call.arguments)}>
                    {truncate(jsonStringify(call.arguments), 60)}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('px-2 py-1 rounded text-xs font-medium', getStatusColor(call.status))}>
                      {call.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {call.threat_detected ? (
                      <span className="flex items-center gap-1 text-red-600">
                        <AlertTriangle className="w-4 h-4" />
                        <span className="text-sm font-medium">Yes</span>
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-green-600">
                        <Shield className="w-4 h-4" />
                        <span className="text-sm font-medium">No</span>
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {call.dlp_redacted ? (
                      <span className="flex items-center gap-1 text-purple-600">
                        <FileText className="w-4 h-4" />
                        <span className="text-sm font-medium">Redacted</span>
                      </span>
                    ) : (
                      <span className="text-sm text-gray-500">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <code className="text-xs font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded">
                      {call.chain_hash.slice(0, 12)}...
                    </code>
                  </td>
                </tr>
              ))}
              {calls.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                    {loading ? 'Loading...' : 'No audit entries found'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1 || loading}
              className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page === totalPages || loading}
              className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

import { cn } from '../lib/utils';