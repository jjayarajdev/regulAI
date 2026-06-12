import { Home, FileText, Shield, BookOpen, Calendar, Database, ArrowLeft } from 'lucide-react';

interface ReguAISidebarProps {
  activeView: string;
  onNavigate: (view: string) => void;
  selectedPeriod?: string;
  onSwitchToUnderwriting?: () => void;
}

const periods = [
  { id: 'TPA-Q4-2025', label: 'TPA-Q4-2025', status: 'active' },
  { id: 'BOP-MAY-2025', label: 'BOP-MAY-2025', status: 'recent' },
  { id: 'CL-Q4-2025', label: 'CL-Q4-2025', status: 'archived' },
];

const knowledgeItems = [
  { id: 'knowledge-graph', label: 'Knowledge graph', count: 0 },
  { id: 'snowflake', label: 'Snowflake', status: 'active' },
  { id: 'sharedfine', label: 'Sharedfine', count: 0 },
];

export function ReguAISidebar({ activeView, onNavigate, selectedPeriod = 'TPA-Q4-2025', onSwitchToUnderwriting }: ReguAISidebarProps) {
  return (
    <div className="w-64 bg-white border-r border-gray-200 h-screen fixed left-0 top-0 overflow-y-auto">
      {/* Logo/Brand */}
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-2xl mb-1" style={{ fontFamily: 'Georgia, serif' }}>
          Regu<span className="text-blue-600">AI</span>
        </h1>
        <p className="text-xs text-gray-500">Lone Star Mutual</p>
        {onSwitchToUnderwriting && (
          <button
            onClick={onSwitchToUnderwriting}
            className="mt-3 w-full flex items-center gap-2 px-3 py-2 text-xs bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700"
          >
            <ArrowLeft className="w-3 h-3" />
            <span>Switch to Underwriting</span>
          </button>
        )}
      </div>

      {/* Main Navigation */}
      <div className="p-4">
        <nav className="space-y-1">
          <button
            onClick={() => onNavigate('overview')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              activeView === 'overview'
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Home className="w-4 h-4" />
            <span>Overview</span>
          </button>

          <button
            onClick={() => onNavigate('filing')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              activeView === 'filing'
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Filing</span>
            <span className="ml-auto text-xs">5</span>
          </button>

          <button
            onClick={() => onNavigate('regulations')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              activeView === 'regulations'
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Shield className="w-4 h-4" />
            <span>Regulations</span>
            <span className="ml-auto text-xs">14</span>
          </button>

          <button
            onClick={() => onNavigate('bulletins')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              activeView === 'bulletins'
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Bulletins</span>
            <span className="ml-auto text-xs">3</span>
          </button>

          <button
            onClick={() => onNavigate('audit-log')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              activeView === 'audit-log'
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Calendar className="w-4 h-4" />
            <span>Audit log</span>
          </button>
        </nav>

        {/* Divider */}
        <div className="my-4 border-t border-gray-200" />

        {/* Periods Section */}
        <div className="mb-6">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 px-3">My Filings</p>
          <div className="space-y-1">
            {periods.map((period) => (
              <button
                key={period.id}
                onClick={() => onNavigate('filing')}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm ${
                  period.id === selectedPeriod
                    ? 'bg-purple-600 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span>{period.label}</span>
                {period.status === 'active' && (
                  <span className="w-2 h-2 bg-green-400 rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Sources Section */}
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 px-3">Sources</p>
          <div className="space-y-1">
            {knowledgeItems.map((item) => (
              <button
                key={item.id}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-100"
              >
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-gray-400" />
                  <span>{item.label}</span>
                </div>
                {item.count !== undefined && (
                  <span className="text-xs text-gray-400">{item.count}</span>
                )}
                {item.status === 'active' && (
                  <span className="text-xs text-green-600">active</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
