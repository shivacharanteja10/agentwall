import { useEffect, useState } from 'react';
import { TrendingUp, AlertTriangle, CheckCircle, XCircle, Clock, RefreshCw, Shield, FileText, Users, Database } from 'lucide-react';
import { apiClient } from '../api';
import { formatRelativeTime, getStatusColor, getRoleColor } from '../lib/utils';
import type { AuditStats, ApprovalStats, HealthResponse } from '../types';

export function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [auditStats, setAuditStats] = useState<AuditStats | null>(null);
  const [approvalStats, setApprovalStats] = useState<ApprovalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [h, a, ap] = await Promise.all([
        apiClient.health(),
        apiClient.getAuditStats(),
        apiClient.getApprovalStats(),
      ]);
      setHealth(h);
      setAuditStats(a);
      setApprovalStats(ap);
      setError(null);
    } catch (err) {
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const statCards = [
    {
      label: 'Total Tool Calls',
      value: auditStats?.total_calls ?? 0,
      icon: FileText,
      color: 'text-blue-600 bg-blue-100',
      trend: '+12%',
    },
    {
      label: 'Threats Blocked',
      value: auditStats?.threats_detected ?? 0,
      icon: Shield,
      color: 'text-red-600 bg-red-100',
      trend: '+3%',
    },
    {
      label: 'DLP Redactions',
      value: auditStats?.dlp_redactions ?? 0,
      icon: AlertTriangle,
      color: 'text-purple-600 bg-purple-100',
      trend: '+1%',
    },
    {
      label: 'Pending Approvals',
      value: approvalStats?.pending ?? 0,
      icon: Clock,
      color: 'text-yellow-600 bg-yellow-100',
      trend: approvalStats && approvalStats.pending > 0 ? '⚠ Action needed' : 'All clear',
    },
  ];

  const statusBreakdown = auditStats?.by_status || {};

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500">Overview of AgentWall security gateway</p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          aria-label="Refresh data"
        >
          <RefreshCw className={cn('w-5 h-5', loading && 'animate-spin')} />
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* System Health */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className={cn('p-4 rounded-lg border', health?.database === 'healthy' ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50')}>
          <div className="flex items-center gap-3">
            <div className={cn('p-2 rounded', health?.database === 'healthy' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600')}>
              <Database className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">Database</p>
              <p className="text-sm text-gray-500 capitalize">{health?.database ?? 'unknown'}</p>
            </div>
          </div>
        </div>
        <div className={cn('p-4 rounded-lg border', health?.redis === 'healthy' ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50')}>
          <div className="flex items-center gap-3">
            <div className={cn('p-2 rounded', health?.redis === 'healthy' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600')}>
              <Server className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">Redis</p>
              <p className="text-sm text-gray-500 capitalize">{health?.redis ?? 'unknown'}</p>
            </div>
          </div>
        </div>
        <div className={cn('p-4 rounded-lg border', health?.status === 'healthy' ? 'border-green-200 bg-green-50' : 'border-yellow-200 bg-yellow-50')}>
          <div className="flex items-center gap-3">
            <div className={cn('p-2 rounded', health?.status === 'healthy' ? 'bg-green-100 text-green-600' : 'bg-yellow-100 text-yellow-600')}>
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">Gateway Status</p>
              <p className="text-sm text-gray-500 capitalize">{health?.status ?? 'unknown'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {statCards.map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{stat.value}</p>
                <p className="text-xs text-gray-500 mt-2">{stat.trend}</p>
              </div>
              <div className={cn('p-3 rounded-lg', stat.color)}>
                <stat.icon className="w-6 h-6" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Status Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Tool Call Status</h2>
          <div className="space-y-3">
            {Object.entries(statusBreakdown).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={cn('px-2 py-1 rounded text-xs font-medium', getStatusColor(status))}>
                    {status.replace('_', ' ')}
                  </span>
                </div>
                <span className="text-lg font-semibold text-gray-900">{count}</span>
              </div>
            ))}
            {Object.keys(statusBreakdown).length === 0 && (
              <p className="text-gray-500 text-center py-4">No data available</p>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Approval Queue</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800">Pending</span>
              <span className="text-lg font-semibold text-gray-900">{approvalStats?.pending ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">Approved</span>
              <span className="text-lg font-semibold text-gray-900">{approvalStats?.approved ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800">Denied</span>
              <span className="text-lg font-semibold text-gray-900">{approvalStats?.denied ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">Expired</span>
              <span className="text-lg font-semibold text-gray-900">{approvalStats?.expired ?? 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import { cn } from '../lib/utils';