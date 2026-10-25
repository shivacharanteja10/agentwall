import { useEffect, useState, useRef } from 'react';
import { Search, Filter, Pause, Play, Trash2, Download, Shield, AlertTriangle, Eye, FileText, Clock } from 'lucide-react';
import { apiClient } from '../api';
import { formatRelativeTime, getStatusColor, truncate, jsonStringify } from '../lib/utils';
import type { ToolCall } from '../types';

export function LiveFeedPage() {
  const [calls, setCalls] = useState<ToolCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [paused, setPaused] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedCall, setSelectedCall] = useState<ToolCall | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchCalls = async () => {
    if (paused) return;
    try {
      const data = await apiClient.listAudit({ limit: 100 });
      setCalls(data);
    } catch (err) {
      console.error('Failed to fetch calls:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
    if (autoRefresh && !paused) {
      refreshIntervalRef.current = setInterval(fetchCalls, 5000);
    }
    return () => {
      if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current);
    };
  }, [autoRefresh, paused]);

  const filteredCalls = calls.filter((call) => {
    if (statusFilter !== 'all' && call.status !== statusFilter) return false;
    if (search) {
      const searchLower = search.toLowerCase();
      return (
        call.tool_name.toLowerCase().includes(searchLower) ||
        JSON.stringify(call.arguments).toLowerCase().includes(searchLower) ||
        (call.result && JSON.stringify(call.result).toLowerCase().includes(searchLower))
      );
    }
    return true;
  });

  const statusOptions = ['all', 'allowed', 'denied', 'pending_approval', 'approved', 'redacted', 'error'];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Live Feed</h1>
          <p className="text-gray-500">Real-time tool call monitoring</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search calls..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg w-64 sm:w-80 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          >
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s === 'all' ? 'All Statuses' : s.replace('_', ' ')}
              </option>
            ))}
          </select>
          <button
            onClick={() => setPaused(!paused)}
            className={cn('px-4 py-2 rounded-lg flex items-center gap-2', paused ? 'bg-gray-100 text-gray-700' : 'bg-primary-600 text-white')}
          >
            {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            <span className="hidden sm:inline">{paused ? 'Resume' : 'Pause'}</span>
          </button>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            Auto-refresh
          </label>
        </div>
      </div>

      {/* Calls Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tool</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Arguments</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Threats</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">DLP</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredCalls.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-500">
                    {loading ? 'Loading...' : 'No tool calls found'}
                  </td>
                </tr>
              ) : (
                filteredCalls.map((call) => (
                  <tr key={call.id} className="hover:bg-gray-50" onClick={() => setSelectedCall(call)}>
                    <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                      {formatRelativeTime(call.created_at)}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs truncate">
                      {call.tool_name}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 max-w-md truncate" title={jsonStringify(call.arguments)}>
                      {truncate(jsonStringify(call.arguments), 80)}
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
                          <span className="text-sm font-medium">Detected</span>
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-green-600">
                          <Shield className="w-4 h-4" />
                          <span className="text-sm font-medium">Clean</span>
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
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedCall(call); }}
                        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                        aria-label="View details"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )
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