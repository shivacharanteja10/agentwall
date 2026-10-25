import { useEffect, useState } from 'react';
import { Plus, RefreshCw, Server, Database, Globe, Loader2, CheckCircle, AlertCircle, Edit, Trash2 } from 'lucide-react';
import { apiClient } from '../api';
import { formatRelativeTime } from '../lib/utils';
import type { ToolServer, Tool } from '../types';

export function ToolServersPage() {
  const [servers, setServers] = useState<ToolServer[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<number | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ name: '', base_url: '', description: '' });
  const [submitting, setSubmitting] = useState(false);
  const [selectedServer, setSelectedServer] = useState<ToolServer | null>(null);

  const fetchData = async () => {
    try {
      const [s, t] = await Promise.all([
        apiClient.listToolServers(),
        apiClient.listTools(),
      ]);
      setServers(s);
      setTools(t);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiClient.createToolServer(formData);
      setShowModal(false);
      setFormData({ name: '', base_url: '', description: '' });
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Failed to create tool server');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSync = async (serverId: number) => {
    setSyncing(serverId);
    try {
      await apiClient.syncToolServer(serverId);
      fetchData();
    } catch (err) {
      alert('Failed to sync tools');
    } finally {
      setSyncing(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this tool server?')) return;
    // Note: Delete endpoint not implemented in API yet
    alert('Delete not implemented yet');
  };

  const getServerTools = (serverId: number) => tools.filter(t => t.server_id === serverId);

  const getIcon = (name: string) => {
    if (name.includes('filesystem') || name.includes('fs')) return <Database className="w-5 h-5" />;
    if (name.includes('database') || name.includes('db')) return <Database className="w-5 h-5" />;
    if (name.includes('web') || name.includes('fetch')) return <Globe className="w-5 h-5" />;
    return <Server className="w-5 h-5" />;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tool Servers</h1>
          <p className="text-gray-500">Manage upstream tool servers and sync tool definitions</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            aria-label="Refresh"
          >
            <RefreshCw className={cn('w-5 h-5', loading && 'animate-spin')} />
          </button>
          <button onClick={() => { setFormData({ name: '', base_url: '', description: '' }); setShowModal(true); }} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Add Server
          </button>
        </div>
      </div>

      {servers.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Server className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No tool servers configured</h3>
          <p className="text-gray-500 mb-4">Add your first upstream tool server to get started</p>
          <button onClick={() => setShowModal(true)} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700">
            Add Server
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {servers.map((server) => (
            <div key={server.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="p-6">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-primary-100 rounded-lg">
                      {getIcon(server.name)}
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">{server.name}</h3>
                      <p className="text-sm text-gray-500">{server.base_url}</p>
                      {server.description && <p className="text-sm text-gray-500 mt-1">{server.description}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={cn('px-3 py-1 rounded-full text-sm font-medium',
                      server.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    )}>
                      {server.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <button
                      onClick={() => handleSync(server.id)}
                      disabled={syncing === server.id}
                      className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
                    >
                      {syncing === server.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                      <span className="hidden sm:inline">Sync Tools</span>
                    </button>
                    <button
                      onClick={() => handleDelete(server.id)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                      aria-label="Delete server"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Tools for this server */}
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h4 className="text-sm font-medium text-gray-700 mb-3">Available Tools ({getServerTools(server.id).length})</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {getServerTools(server.id).map((tool) => (
                      <div key={tool.id} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                        <div className="font-medium text-gray-900 text-sm">{tool.name}</div>
                        {tool.description && <div className="text-xs text-gray-500 mt-1 truncate">{tool.description}</div>}
                        <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
                          <span className="px-2 py-0.5 bg-gray-200 rounded">Input: {Object.keys(tool.input_schema?.properties || {}).length} fields</span>
                          {tool.output_schema && Object.keys(tool.output_schema?.properties || {}).length > 0 && (
                            <span className="px-2 py-0.5 bg-gray-200 rounded">Output: {Object.keys(tool.output_schema.properties).length} fields</span>
                          )}
                        </div>
                      </div>
                    ))}
                    {getServerTools(server.id).length === 0 && (
                      <div className="col-span-full text-center py-4 text-gray-500 text-sm">
                        No tools synced yet. Click "Sync Tools" to fetch tool definitions.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Server Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-xl max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">Add Tool Server</h2>
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
                  placeholder="filesystem"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Base URL *</label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  required
                  placeholder="http://localhost:8001"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                  rows={2}
                  placeholder="Optional description"
                />
              </div>
              <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200">
                  Cancel
                </button>
                <button type="submit" disabled={submitting} className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2">
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Add Server</span>}
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