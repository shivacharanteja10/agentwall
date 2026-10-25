import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { Menu, X, LogOut, Shield, Activity, Inbox, FileText, Users, Server, Database, Settings, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { cn } from '../lib/utils';

export function Layout() {
  const { logout, apiKey } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Activity },
    { path: '/live', label: 'Live Feed', icon: Shield },
    { path: '/approvals', label: 'Approvals', icon: Inbox },
    { path: '/policies', label: 'Policies', icon: FileText },
    { path: '/agents', label: 'Agents', icon: Users },
    { path: '/tool-servers', label: 'Tool Servers', icon: Server },
    { path: '/audit', label: 'Audit Log', icon: Database },
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile menu button */}
      <button
        className="fixed top-4 left-4 z-50 lg:hidden p-2 bg-white rounded-lg shadow"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label="Toggle menu"
      >
        {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 bg-white border-r border-gray-200 transition-all duration-300 lg:translate-x-0',
          sidebarOpen ? 'w-64' : 'w-20',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
            <div className={cn('flex items-center gap-2', sidebarOpen ? 'opacity-100' : 'opacity-0')}>
              <Shield className="w-8 h-8 text-primary-600" />
              <span className="font-semibold text-lg">AgentWall</span>
            </div>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1 rounded hover:bg-gray-100"
              aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-1" aria-label="Main navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                      !sidebarOpen && 'justify-center'
                    )
                  }
                  title={sidebarOpen ? undefined : item.label}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  {sidebarOpen && <span>{item.label}</span>}
                </NavLink>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-gray-200">
            <div className={cn('flex items-center gap-3', sidebarOpen ? 'opacity-100' : 'opacity-0')}>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 truncate">API Key: {apiKey?.slice(0, 8)}...</p>
                <p className="text-xs text-gray-400 truncate">Connected</p>
              </div>
              <button
                onClick={handleLogout}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main content */}
      <main
        className={cn(
          'transition-all duration-300 lg:ml-64',
          sidebarOpen ? 'ml-64' : 'ml-20'
        )}
      >
        <div className="p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

import { useState } from 'react';