import { Shield, Download, Filter, Search, Bell, User } from 'lucide-react';
import { ReguAISidebar } from './ReguAISidebar';

interface AuditLogProps {
  filingId: string;
  onBack: () => void;
  onNavigate?: (view: string) => void;
  onSwitchToUnderwriting?: () => void;
}

const validationRuns = [
  {
    timestamp: '2025-01-15 14:43',
    user: 'system',
    duration: '14.8ms',
    rules: 14,
    violations: 13,
    status: 'completed'
  },
  {
    timestamp: '2025-01-15 14:38',
    user: 'system',
    duration: '12.1ms',
    rules: 14,
    violations: 13,
    status: 'completed'
  },
  {
    timestamp: '2025-01-15 14:34',
    user: 'system',
    duration: '15.2ms',
    rules: 14,
    violations: 13,
    status: 'completed'
  },
  {
    timestamp: '2025-01-15 14:22',
    user: 'system',
    duration: '13.7ms',
    rules: 14,
    violations: 13,
    status: 'completed'
  },
];

const dataEvents = [
  { timestamp: '2025-01-15 14:40', event: 'Data ingestion completed', records: '56 BOR events', source: 'TXBB' },
  { timestamp: '2025-01-15 14:35', event: 'Rule engine execution', records: '2 XT events', source: 'Engine' },
  { timestamp: '2025-01-15 14:30', event: 'Data transformation', records: 'EQLIB - TX-WS-PR', source: 'Pipeline' },
  { timestamp: '2025-01-15 14:20', event: 'Premium calculation', records: 'EQLIB - Cross-border mapping', source: 'Rating' },
];

export function AuditLog({ filingId, onBack, onNavigate, onSwitchToUnderwriting }: AuditLogProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      <ReguAISidebar
        activeView="audit-log"
        onNavigate={onNavigate || (() => {})}
        onSwitchToUnderwriting={onSwitchToUnderwriting}
      />
      <div className="ml-64 flex-1">
        <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Audit Trail</p>
              <p className="text-sm text-gray-900">Chain of custody: {filingId}</p>
            </div>
            <div className="flex items-center gap-4">
              <button className="p-2 hover:bg-gray-100 rounded-lg">
                <Bell className="w-5 h-5 text-gray-600" />
              </button>
              <div className="flex items-center gap-2 pl-4 border-l border-gray-200">
                <div className="w-8 h-8 bg-purple-600 rounded-full flex items-center justify-center">
                  <User className="w-4 h-4 text-white" />
                </div>
                <div>
                  <p className="text-sm text-gray-900">Diana Reyes</p>
                  <p className="text-xs text-gray-500">Compliance Analyst</p>
                </div>
              </div>
            </div>
          </div>
        </header>
        <div className="max-w-7xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={onBack}
            className="px-3 py-1 mb-4 border border-gray-300 rounded hover:bg-gray-100 text-sm"
          >
            ← Back
          </button>

          <div className="mb-4">
            <p className="text-sm text-gray-500 mb-2">Chain of custody: {filingId}</p>
            <h1 className="text-5xl mb-2" style={{ fontFamily: 'Georgia, serif' }}>
              Every byte
            </h1>
            <h2 className="text-5xl mb-6" style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic' }}>
              has a <span className="text-blue-600">trail</span>.
            </h2>
          </div>

          <div className="bg-white border-2 border-gray-300 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-3 text-sm text-gray-700">
              <Shield className="w-5 h-5 text-blue-600" />
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 bg-green-50 border border-green-300 rounded text-green-700">
                  <strong>56 BOR</strong> events
                </span>
                <span>+</span>
                <span className="px-2 py-1 bg-blue-50 border border-blue-300 rounded text-blue-700">
                  <strong>2 XT</strong> events
                </span>
                <span>from</span>
                <span className="text-blue-600">EQLIB, KNBIT, KNBIT_ACTION</span>
                <span>+</span>
                <span className="text-blue-600">extSecurity</span>
                <span>·</span>
                <span>4 open exceptions</span>
                <span>·</span>
                <span className="text-gray-500">last validation 2025-01-15T09:43:42.797000</span>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search events, users, or record types..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2">
            <Filter className="w-4 h-4" />
            <span className="text-sm">Filter</span>
          </button>
          <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2">
            <Download className="w-4 h-4" />
            <span className="text-sm">Export</span>
          </button>
        </div>

        {/* Validation Runs */}
        <div className="bg-white border-2 border-gray-300 rounded-lg mb-6">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-2xl" style={{ fontFamily: 'Georgia, serif' }}>Validation runs</h2>
            <p className="text-sm text-gray-500 mt-1">Automated validation execution history</p>
          </div>

          <div className="divide-y divide-gray-200">
            {validationRuns.map((run, idx) => (
              <div key={idx} className="p-6 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                      <Shield className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">VALIDATION RUN</p>
                      <div className="flex items-center gap-3 text-sm text-gray-600 mt-1">
                        <span>{run.user}</span>
                        <span>·</span>
                        <span>{run.duration}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <p className="text-sm text-gray-900">
                        <strong>{run.rules} rules</strong> - {run.violations} violations
                      </p>
                      <p className="text-xs text-gray-500">{run.timestamp}</p>
                    </div>
                    <button className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
                      View details
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Data Events Timeline */}
        <div className="bg-white border-2 border-gray-300 rounded-lg">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-2xl" style={{ fontFamily: 'Georgia, serif' }}>Data events</h2>
            <p className="text-sm text-gray-500 mt-1">Processing pipeline and transformation log</p>
          </div>

          <div className="divide-y divide-gray-200">
            {dataEvents.map((event, idx) => (
              <div key={idx} className="p-6 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-2 h-2 bg-blue-600 rounded-full" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{event.event}</p>
                      <div className="flex items-center gap-3 text-sm text-gray-600 mt-1">
                        <span>{event.records}</span>
                        <span>·</span>
                        <span className="text-gray-500">Source: {event.source}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500">{event.timestamp}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Compliance Footer */}
        <div className="mt-8 bg-blue-50 border-2 border-blue-300 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <Shield className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <p className="text-sm text-blue-900 mb-2">
                <strong>Audit trail integrity:</strong> All events are cryptographically signed and immutable
              </p>
              <p className="text-xs text-blue-700">
                Compliance: SOC 2 Type II · ISO 27001 · TDI Statistical Reporting Requirements · Retention: 7 years
              </p>
            </div>
          </div>
        </div>

        {/* Wireframe Label */}
        <div className="mt-6 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-900">
            <strong>Wireframe:</strong> Audit Log - Chain of custody tracking for filing {filingId}, showing validation runs, data events timeline, processing pipeline logs, and compliance certifications
          </p>
        </div>
        </div>
      </div>
    </div>
  );
}
