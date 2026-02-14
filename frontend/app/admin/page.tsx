'use client';

import { useCallback, useEffect, useState } from 'react';
import { API_BASE_URL } from '@/lib/constants';

interface HealthStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'checking';
  message: string;
  latency?: number;
  lastChecked: Date;
}

interface VersionInfo {
  git_sha?: string;
  environment?: string;
  build_time?: string;
  service?: string;
  version?: string;
}

export default function AdminDashboard() {
  const [services, setServices] = useState<HealthStatus[]>([
    { name: 'Backend API', status: 'checking', message: 'Checking...', lastChecked: new Date() },
    { name: 'Database', status: 'checking', message: 'Checking...', lastChecked: new Date() },
    { name: 'Authentication', status: 'checking', message: 'Checking...', lastChecked: new Date() },
  ]);
  const [version, setVersion] = useState<VersionInfo | null>(null);

  const updateService = useCallback((name: string, status: HealthStatus['status'], message: string, latency?: number) => {
    setServices(prev => prev.map(s =>
      s.name === name
        ? { ...s, status, message, latency, lastChecked: new Date() }
        : s
    ));
  }, []);

  const checkAllServices = useCallback(async () => {
    try {
      const healthRes = await fetch(`${API_BASE_URL}/health`, {
        signal: AbortSignal.timeout(5000)
      });
      
      updateService('Backend API', 
        healthRes.ok ? 'healthy' : 'unhealthy',
        healthRes.ok ? 'Responding' : `HTTP ${healthRes.status}`
      );

      if (healthRes.ok) {
        // Deep diagnostics are intentionally separated from `/health`
        // to keep liveness probes lightweight.
        try {
          const deepRes = await fetch(`${API_BASE_URL}/health/deep`, {
            signal: AbortSignal.timeout(5000)
          });
          if (deepRes.ok) {
            const deepData = await deepRes.json();
            updateService(
              'Database',
              deepData.ingestion_diagnostics_schema?.available ? 'healthy' : 'degraded',
              deepData.ingestion_diagnostics_schema?.available ? 'Connected' : 'Schema unavailable'
            );
          } else {
            updateService('Database', 'degraded', 'Diagnostics unavailable');
          }
        } catch {
          updateService('Database', 'degraded', 'Diagnostics unavailable');
        }
      }
    } catch {
      updateService('Backend API', 'unhealthy', 'Connection failed');
      updateService('Database', 'unhealthy', 'Cannot reach backend');
    }

    // Check Auth
    try {
      const versionRes = await fetch(`${API_BASE_URL}/version`, {
        signal: AbortSignal.timeout(5000)
      });
      
      if (versionRes.ok) {
        const data: VersionInfo = await versionRes.json();
        setVersion(data);
        updateService('Authentication', 'healthy', 'Service available');
      } else {
        updateService('Authentication', 'unhealthy', `HTTP ${versionRes.status}`);
      }
    } catch {
      updateService('Authentication', 'unhealthy', 'Connection failed');
    }
  }, [updateService]);

  useEffect(() => {
    void checkAllServices();
    const interval = setInterval(() => {
      void checkAllServices();
    }, 30000);
    return () => clearInterval(interval);
  }, [checkAllServices]);

  const getStatusColor = (status: HealthStatus['status']) => {
    switch (status) {
      case 'healthy': return 'bg-green-100 text-green-800 border-green-200';
      case 'degraded': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'unhealthy': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  const getStatusIcon = (status: HealthStatus['status']) => {
    switch (status) {
      case 'healthy': return '✓';
      case 'degraded': return '!';
      case 'unhealthy': return '✕';
      default: return '⋯';
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">System Health</h2>
        <p className="text-slate-500 mt-1">
          Monitor API and service status
        </p>
      </div>

      {/* Service Status Grid */}
      <div className="grid md:grid-cols-3 gap-6">
        {services.map((service) => (
          <div
            key={service.name}
            className={`p-6 rounded-xl border ${getStatusColor(service.status)}`}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{service.name}</h3>
              <span className="text-2xl">{getStatusIcon(service.status)}</span>
            </div>
            <p className="mt-2 text-sm opacity-75">{service.message}</p>
            {service.latency && (
              <p className="mt-1 text-xs opacity-50">
                Latency: {service.latency}ms
              </p>
            )}
            <p className="mt-3 text-xs opacity-40">
              Last checked: {service.lastChecked.toLocaleTimeString()}
            </p>
          </div>
        ))}
      </div>

      {/* Version Info */}
      {version && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Deployment Info</h3>
          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-slate-500">Git SHA:</span>
              <code className="ml-2 bg-slate-100 px-2 py-1 rounded">{version.git_sha}</code>
            </div>
            <div>
              <span className="text-slate-500">Environment:</span>
              <span className="ml-2 capitalize">{version.environment}</span>
            </div>
            <div>
              <span className="text-slate-500">Build Time:</span>
              <span className="ml-2">
                {version.build_time && version.build_time !== 'unknown'
                  ? new Date(version.build_time).toLocaleString()
                  : 'Unknown'}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Service:</span>
              <span className="ml-2">{version.service}</span>
            </div>
            <div>
              <span className="text-slate-500">Version:</span>
              <span className="ml-2">{version.version}</span>
            </div>
          </div>
        </div>
      )}

      {/* CORS Configuration */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">CORS Configuration</h3>
        <div className="space-y-4">
          <div>
            <span className="text-sm text-slate-500">API Base URL:</span>
            <code className="ml-2 text-sm bg-slate-100 px-2 py-1 rounded block mt-1">{API_BASE_URL}</code>
          </div>
          <div className="flex gap-3">
            <a
              href={`${API_BASE_URL}/cors-test`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-slate-900 text-white text-sm rounded-lg hover:bg-slate-800"
            >
              Test CORS
            </a>
            <a
              href={`${API_BASE_URL}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 border border-slate-300 text-slate-700 text-sm rounded-lg hover:bg-slate-50"
            >
              API Docs
            </a>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={checkAllServices}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700"
          >
            Refresh Health Check
          </button>
          <button
            onClick={() => window.open(`${API_BASE_URL}/health`, '_blank')}
            className="px-4 py-2 border border-slate-300 text-slate-700 text-sm rounded-lg hover:bg-slate-50"
          >
            View /health
          </button>
          <button
            onClick={() => window.open(`${API_BASE_URL}/version`, '_blank')}
            className="px-4 py-2 border border-slate-300 text-slate-700 text-sm rounded-lg hover:bg-slate-50"
          >
            View /version
          </button>
        </div>
      </div>
    </div>
  );
}
