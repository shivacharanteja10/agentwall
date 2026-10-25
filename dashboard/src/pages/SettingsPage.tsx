import { useState } from 'react';
import { Shield, Database, Server, Bell, Key, User, Save, Loader2 } from 'lucide-react';
import { apiClient } from '../api';
import { formatRelativeTime } from '../lib/utils';

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'security' | 'integrations' | 'about'>('general');
  const [saving, setSaving] = useState(false);

  const tabs = [
    { id: 'general', label: 'General', icon: Shield },
    { id: 'security', label: 'Security', icon: Key },
    { id: 'integrations', label: 'Integrations', icon: Server },
    { id: 'about', label: 'About', icon: Database },
  ];

  const handleSave = async () => {
    setSaving(true);
    await new Promise(r => setTimeout(r, 1000));
    setSaving(false);
    alert('Settings saved (demo)');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500">Configure AgentWall gateway and dashboard settings</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Tab Navigation */}
        <div className="border-b border-gray-200">
          <nav className="flex overflow-x-auto" aria-label="Settings tabs">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as typeof activeTab)}
                  className={cn(
                    'flex items-center gap-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                    activeTab === tab.id
                      ? 'border-primary-600 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'general' && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Gateway Configuration</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Gateway Name</label>
                    <input type="text" defaultValue="AgentWall" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Default Rate Limit (req/min)</label>
                    <input type="number" defaultValue="100" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Approval Timeout (seconds)</label>
                    <input type="number" defaultValue="300" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
                  </div>
                  <div className="flex items-center gap-3">
                    <input type="checkbox" id="enable-dlp" defaultChecked className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label htmlFor="enable-dlp" className="text-sm text-gray-700">Enable Data Loss Prevention (DLP)</label>
                  </div>
                  <div className="flex items-center gap-3">
                    <input type="checkbox" id="enable-ml" className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label htmlFor="enable-ml" className="text-sm text-gray-700">Enable ML-based threat classifier (requires model)</label>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Egress Allowlist</h2>
                <p className="text-sm text-gray-500 mb-3">Comma-separated list of allowed outbound URL bases</p>
                <textarea
                  defaultValue="http://localhost:8001,http://localhost:8002,http://localhost:8003"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm"
                  rows={3}
                />
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Authentication</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">JWT Secret Key</label>
                    <div className="flex gap-2">
                      <input type="password" defaultValue="dev-secret-key-change-in-production" className="flex-1 px-3 py-2 border border-gray-300 rounded-lg" />
                      <button className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">Rotate</button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Rotate secret key. Existing tokens will be invalidated.</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Access Token Expiry (minutes)</label>
                    <input type="number" defaultValue="30" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
                  </div>
                  <div className="flex items-center gap-3">
                    <input type="checkbox" id="require-https" defaultChecked className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label htmlFor="require-https" className="text-sm text-gray-700">Require HTTPS in production</label>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Default Deny Policy</h2>
                <p className="text-sm text-gray-500 mb-3">When no policy matches, tool calls are denied by default.</p>
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-sm text-yellow-800">Default-deny is enforced and cannot be disabled. Create explicit allow policies for agents to access tools.</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Upstream Tool Servers</h2>
                <p className="text-sm text-gray-500 mb-4">Manage tool servers from the Tool Servers page.</p>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600">Configured servers will appear here after adding them via the Tool Servers page.</p>
                </div>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Notification Webhooks</h2>
                <div className="space-y-4">
                  <div className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg">
                    <input type="checkbox" id="webhook-approvals" className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label htmlFor="webhook-approvals" className="text-sm font-medium text-gray-700">Send webhook on approval requests</label>
                  </div>
                  <div className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg">
                    <input type="checkbox" id="webhook-threats" className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label htmlFor="webhook-threats" className="text-sm font-medium text-gray-700">Send webhook on threat detection</label>
                  </div>
                  <div className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg">
                    <input type="checkbox" id="webhook-dlp" className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                    <label htmlFor="webhook-dlp" className="text-sm font-medium text-gray-700">Send webhook on DLP redaction</label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'about' && (
            <div className="max-w-2xl space-y-6">
              <div className="text-center py-8">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary-100 mb-4">
                  <Shield className="w-10 h-10 text-primary-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900">AgentWall</h2>
                <p className="text-gray-500 mt-1">Version 0.1.0</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <h3 className="font-medium text-gray-900 mb-2">Components</h3>
                  <ul className="text-sm text-gray-600 space-y-1">
                    <li>Gateway: FastAPI + Python 3.11</li>
                    <li>Database: PostgreSQL 16</li>
                    <li>Cache/Queue: Redis 7</li>
                    <li>Dashboard: React 18 + TypeScript + Tailwind</li>
                    <li>Tool Servers: 3 demo servers (FS, DB, Web)</li>
                  </ul>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <h3 className="font-medium text-gray-900 mb-2">Security Features</h3>
                  <ul className="text-sm text-gray-600 space-y-1">
                    <li>Zero-trust agent authentication</li>
                    <li>Policy-as-code (YAML/DB)</li>
                    <li>Prompt injection detection</li>
                    <li>Data loss prevention (DLP)</li>
                    <li>Hash-chained audit logs</li>
                    <li>Human-in-the-loop approvals</li>
                  </ul>
                </div>
              </div>

              <div className="p-4 bg-gray-50 rounded-lg">
                <h3 className="font-medium text-gray-900 mb-2">Links</h3>
                <div className="space-y-2 text-sm">
                  <a href="https://github.com/shivacharanteja10/agentwall" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline flex items-center gap-2">
                    <GitHub className="w-4 h-4" /> GitHub Repository
                  </a>
                  <a href="#" className="text-primary-600 hover:underline flex items-center gap-2">
                    <FileText className="w-4 h-4" /> Documentation
                  </a>
                  <a href="#" className="text-primary-600 hover:underline flex items-center gap-2">
                    <Bug className="w-4 h-4" /> Report Issue
                  </a>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Save Bar */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-end">
          <button onClick={handleSave} disabled={saving} className="px-6 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            <span>Save Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
}

import { cn } from '../lib/utils';
import { GitHub, Bug, FileText } from 'lucide-react';