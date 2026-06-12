import { FileText, AlertCircle, Calendar, Filter, Bell, User, CheckCircle, Circle, Clock, ChevronDown } from 'lucide-react';
import { ReguAISidebar } from './ReguAISidebar';
import { useState } from 'react';
import { useApprovalStates, useFilings, useValidateAll } from '../../api/hooks';
import type { FilingStatus } from '../../api/types';

interface ReguAIOverviewProps {
  onNavigateToFiling: (filingId: string) => void;
  onNavigateToValidation: (filingId: string) => void;
  onNavigate?: (view: string) => void;
  onSwitchToUnderwriting?: () => void;
}

// Sign-off chain position → progress % and phase label for the filing row.
const STATUS_META: Record<FilingStatus, { progress: number; phase: string }> = {
  draft:            { progress: 10,  phase: 'Draft' },
  validating:       { progress: 30,  phase: 'Validating' },
  validated:        { progress: 50,  phase: 'Validated' },
  analyst_signed:   { progress: 65,  phase: 'Analyst signed' },
  actuary_approved: { progress: 80,  phase: 'Actuary approved' },
  officer_approved: { progress: 90,  phase: 'Officer approved' },
  submitted:        { progress: 100, phase: 'TDI Review' },
  acked:            { progress: 100, phase: 'Acknowledged' },
};

const NUMBER_WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine'];

const daysUntil = (isoDate: string) =>
  Math.round((new Date(isoDate + 'T00:00:00').getTime() - Date.now()) / 86_400_000);

export function ReguAIOverview({ onNavigateToFiling, onNavigateToValidation, onNavigate, onSwitchToUnderwriting }: ReguAIOverviewProps) {
  const [expandedFiling, setExpandedFiling] = useState<string | null>(null);
  const [showNewFilingModal, setShowNewFilingModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);

  const filingsQuery = useFilings();
  const filingList = filingsQuery.data?.filings ?? [];
  const filingIds = filingList.map((f) => f.id);
  const validations = useValidateAll(filingIds);
  const approvals = useApprovalStates(filingIds);

  // View-model the filing rows: registry metadata + validation counts +
  // sign-off chain position, with per-row loading placeholders while the
  // slower queries hydrate.
  const activeFilings = filingList.map((f, i) => {
    const val = validations[i]?.data;
    const ap = approvals[i]?.data;
    const meta = ap ? STATUS_META[ap.status] : null;
    return {
      id: f.id,
      name: f.plan_name,
      bureau: f.jurisdiction_code === 'US-TX' ? 'TDI' : f.jurisdiction_code,
      status: !ap ? 'Pending' : ap.status === 'submitted' || ap.status === 'acked' ? 'Submitted' : 'In Progress',
      daysLeft: daysUntil(f.due_date),
      phase: meta?.phase ?? 'Loading…',
      progress: meta?.progress ?? 0,
      items: val?.summary.rules_run ?? 0,
      violations: val?.summary.total_violations ?? 0,
      lastActivity: f.cadence,
      assignee: !ap ? '…' : ap.next_role ? `Awaiting ${ap.next_role}` : ap.can_seal ? 'Ready to seal' : 'Complete',
    };
  });

  const upcomingDeadlines = [...filingList]
    .sort((a, b) => a.due_date.localeCompare(b.due_date))
    .map((f) => {
      const days = daysUntil(f.due_date);
      return {
        name: f.id,
        type: `${f.cadence} Statistical · ${f.plan_name}`,
        bureau: f.channel,
        dueDate: new Date(f.due_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
        daysUntil: days,
        priority: days < 20 ? 'high' : days < 40 ? 'medium' : 'low',
      };
    });

  // Headline metrics, derived from live data.
  const totalViolations = activeFilings.reduce((n, f) => n + f.violations, 0);
  const inFlight = activeFilings.filter((f) => f.status !== 'Submitted').length;
  const rulesRun = validations.reduce((n, q) => n + (q.data?.summary.rules_run ?? 0), 0);
  const rulesPassing = validations.reduce((n, q) => n + (q.data?.summary.rules_passing ?? 0), 0);
  const complianceRate = rulesRun ? Math.round((rulesPassing / rulesRun) * 100) : null;
  const soonestDays = upcomingDeadlines.length ? upcomingDeadlines[0].daysUntil : null;

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  });

  if (filingsQuery.isError) {
    return (
      <div className="min-h-screen bg-gray-50 flex">
        <ReguAISidebar
          activeView="overview"
          onNavigate={onNavigate || (() => {})}
          selectedPeriod=""
          onSwitchToUnderwriting={onSwitchToUnderwriting}
        />
        <div className="ml-64 flex-1 flex items-center justify-center">
          <div className="bg-white border-2 border-red-300 rounded-xl p-8 max-w-md text-center">
            <AlertCircle className="w-10 h-10 text-red-600 mx-auto mb-4" />
            <h3 className="text-2xl mb-2" style={{ fontFamily: 'Georgia, serif' }}>Backend unreachable</h3>
            <p className="text-sm text-gray-600 mb-4">Could not load the filing registry from /api/rhs/filings.</p>
            <button
              onClick={() => filingsQuery.refetch()}
              className="px-5 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 text-sm font-medium"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* New Filing Modal */}
      {showNewFilingModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center animate-in fade-in duration-200">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-2xl font-medium" style={{ fontFamily: 'Georgia, serif' }}>New Filing</h3>
              <p className="text-sm text-gray-600 mt-1">Create a new regulatory submission</p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Bureau</label>
                <select className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none transition-all">
                  <option>TDI - Texas Department of Insurance</option>
                  <option>NCCI - National Council on Compensation Insurance</option>
                  <option>ISO - Insurance Services Office</option>
                  <option>ALB - American Life Bureau</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Filing Type</label>
                <select className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none transition-all">
                  <option>Quarterly Statistical</option>
                  <option>Annual Rate Filing</option>
                  <option>Monthly Statistical</option>
                  <option>Policy Count Report</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Period</label>
                <input type="text" placeholder="Q2 2026" className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none transition-all" />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex gap-3">
              <button
                onClick={() => setShowNewFilingModal(false)}
                className="flex-1 px-4 py-2 border-2 border-gray-300 rounded-lg hover:bg-gray-50 font-medium transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => setShowNewFilingModal(false)}
                className="flex-1 px-4 py-2 bg-gradient-to-r bg-gray-900 text-white rounded-lg hover:bg-gray-800 font-medium shadow-sm hover:shadow transition-all active:scale-95"
              >
                Create Filing
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import Data Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center animate-in fade-in duration-200">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-2xl font-medium" style={{ fontFamily: 'Georgia, serif' }}>Import Data</h3>
              <p className="text-sm text-gray-600 mt-1">Upload filing data from external source</p>
            </div>
            <div className="p-6">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-purple-400 transition-colors cursor-pointer">
                <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <FileText className="w-8 h-8 text-gray-700" />
                </div>
                <p className="text-sm font-medium text-gray-900 mb-1">Drop files here or click to browse</p>
                <p className="text-xs text-gray-500">CSV, XLSX, or TXT files supported</p>
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex gap-3">
              <button
                onClick={() => setShowImportModal(false)}
                className="flex-1 px-4 py-2 border-2 border-gray-300 rounded-lg hover:bg-gray-50 font-medium transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => setShowImportModal(false)}
                className="flex-1 px-4 py-2 bg-gradient-to-r bg-gray-900 text-white rounded-lg hover:bg-gray-800 font-medium shadow-sm hover:shadow transition-all active:scale-95"
              >
                Upload
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Sidebar */}
      <ReguAISidebar
        activeView="overview"
        onNavigate={onNavigate || (() => {})}
        selectedPeriod="TPA-Q4-2025"
        onSwitchToUnderwriting={onSwitchToUnderwriting}
      />

      {/* Main Content */}
      <div className="ml-64 flex-1">
        {/* Top Header */}
        <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-xs text-gray-500">Lone Star Mutual</p>
                <p className="text-sm text-gray-900">
                  UEE76 · {filingsQuery.data?.default ?? '…'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button className="p-2 hover:bg-gray-100 rounded-lg relative">
                <Bell className="w-5 h-5 text-gray-600" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
              </button>
              <div className="flex items-center gap-2 pl-4 border-l border-gray-200">
                <div className="w-8 h-8 bg-gray-900 rounded-full flex items-center justify-center">
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
        {/* Hero Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <p className="text-sm text-gray-500 mb-3">{today}</p>
              <h1 className="text-6xl leading-tight mb-2" style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>
                {NUMBER_WORDS[inFlight] ?? inFlight} filing{inFlight === 1 ? '' : 's'} in flight.
              </h1>
              <h2 className="text-6xl leading-tight mb-6" style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontWeight: 400 }}>
                <span className="text-gray-600">
                  {soonestDays !== null ? `${soonestDays} days` : '— days'}
                </span> to file.
              </h2>
              <p className="text-gray-600 max-w-3xl text-lg leading-relaxed">
                All in-progress submissions, the soonest waiting to be acknowledged, and the
                bureaus and check submission—Your total state of play, at one place.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => setShowNewFilingModal(true)}
                className="px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800 font-medium transition-colors"
              >
                + New Filing
              </button>
              <button
                onClick={() => setShowImportModal(true)}
                className="px-6 py-3 border-2 border-gray-300 rounded-lg hover:bg-gray-50 font-medium transition-colors"
              >
                Import Data
              </button>
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
          <button className="bg-white border-2 border-gray-300 rounded-lg p-6 hover:border-gray-400 hover:shadow-sm transition-all text-left group cursor-pointer">
            <p className="text-xs text-gray-600 uppercase tracking-wider mb-3 font-semibold">In-Progress Submissions</p>
            <p className="text-6xl mb-2 text-gray-900" style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>{inFlight}</p>
            <p className="text-sm text-gray-700">of {activeFilings.length} active filings</p>
          </button>

          <button
            onClick={() => activeFilings[0] && onNavigateToValidation(activeFilings[0].id)}
            className="bg-white border-2 border-gray-300 rounded-lg p-6 hover:border-gray-400 hover:shadow-sm transition-all text-left group cursor-pointer"
          >
            <p className="text-xs text-gray-600 uppercase tracking-wider mb-3 font-semibold">Open Blockers</p>
            <p className={`text-6xl mb-2 ${totalViolations > 0 ? 'text-red-600' : 'text-gray-900'}`} style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>{totalViolations}</p>
            <p className="text-sm text-gray-700">Violations across all filings</p>
          </button>

          <button className="bg-white border-2 border-gray-300 rounded-lg p-6 hover:border-gray-400 hover:shadow-sm transition-all text-left group cursor-pointer">
            <p className="text-xs text-gray-600 uppercase tracking-wider mb-3 font-semibold">Compliance Rate</p>
            <p className="text-6xl mb-2 text-gray-900" style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>
              {complianceRate !== null ? complianceRate : '—'}<span className="text-3xl">%</span>
            </p>
            <p className="text-sm text-gray-700">{rulesPassing} of {rulesRun} rules passing</p>
          </button>

          <button className="bg-white border-2 border-gray-300 rounded-lg p-6 hover:border-gray-400 hover:shadow-sm transition-all text-left group cursor-pointer">
            <p className="text-xs text-gray-600 uppercase tracking-wider mb-3 font-semibold">Next Deadline</p>
            <p className="text-6xl mb-2 text-gray-900" style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>
              {soonestDays !== null ? soonestDays : '—'}
            </p>
            <p className="text-sm text-gray-700">
              days · {upcomingDeadlines[0]?.name ?? 'no filings'}
            </p>
          </button>
        </div>

        {/* Active Filings Section */}
        <div className="bg-white border-2 border-gray-300 rounded-xl shadow-sm">
          <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-white">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-3xl mb-1" style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>Active filings</h3>
                <p className="text-sm text-gray-600">Track progress across all regulatory submissions</p>
              </div>
              <div className="flex gap-2">
                <button className="px-4 py-2 border-2 border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium flex items-center gap-2">
                  <Filter className="w-4 h-4" />
                  Filter
                </button>
                <button className="px-4 py-2 text-sm text-gray-700 hover:text-gray-800 font-medium">View all →</button>
              </div>
            </div>
          </div>

          {filingsQuery.isLoading && (
            <div className="divide-y divide-gray-200">
              {[0, 1, 2].map((i) => (
                <div key={i} className="p-6 animate-pulse">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-lg bg-gray-200" />
                    <div className="flex-1 space-y-3 py-1">
                      <div className="h-5 bg-gray-200 rounded w-1/3" />
                      <div className="h-3 bg-gray-100 rounded w-1/2" />
                      <div className="h-2.5 bg-gray-100 rounded w-full" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="divide-y divide-gray-200">
            {activeFilings.map((filing) => {
              const isExpanded = expandedFiling === filing.id;

              return (
                <div key={filing.id} className="p-6 hover:bg-gradient-to-r hover:from-gray-50/30 hover:to-transparent transition-all">
                  <div className="flex items-start justify-between mb-4">
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                      filing.status === 'Submitted' ? 'bg-green-100' :
                      filing.status === 'In Progress' ? 'bg-purple-100' :
                      'bg-gray-100'
                    }`}>
                      <FileText className={`w-6 h-6 ${
                        filing.status === 'Submitted' ? 'text-green-600' :
                        filing.status === 'In Progress' ? 'text-gray-700' :
                        'text-gray-600'
                      }`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <h4 className="text-xl font-medium text-gray-900" style={{ fontFamily: 'Georgia, serif' }}>
                          {filing.name}
                        </h4>
                        <span className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded font-medium">
                          {filing.bureau}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-600">
                        <span className="flex items-center gap-1">
                          <span className="font-medium">{filing.id}</span>
                        </span>
                        <span>·</span>
                        <span>{filing.phase}</span>
                        <span>·</span>
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {filing.assignee}
                        </span>
                        {filing.lastActivity !== '—' && (
                          <>
                            <span>·</span>
                            <span className="text-gray-500">Updated {filing.lastActivity}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {filing.status === 'Submitted' ? (
                      <span className="inline-flex items-center gap-2 px-4 py-2 bg-green-50 text-green-700 border-2 border-green-300 rounded-lg text-sm font-medium">
                        <CheckCircle className="w-4 h-4" />
                        Submitted
                      </span>
                    ) : filing.status === 'In Progress' ? (
                      <span className="inline-flex items-center gap-2 px-4 py-2 bg-gray-10 text-gray-800 border-2 border-gray-300 rounded-lg text-sm font-medium">
                        <Clock className="w-4 h-4" />
                        In Progress
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2 px-4 py-2 bg-gray-50 text-gray-700 border-2 border-gray-300 rounded-lg text-sm font-medium">
                        <Circle className="w-4 h-4" />
                        Pending
                      </span>
                    )}
                    <div className="text-right">
                      <p className={`text-2xl font-medium ${
                        filing.daysLeft < 30 ? 'text-red-600' :
                        filing.daysLeft < 60 ? 'text-orange-600' :
                        'text-gray-900'
                      }`} style={{ fontFamily: 'Georgia, serif' }}>
                        {filing.daysLeft}
                      </p>
                      <p className="text-xs text-gray-500">days left</p>
                    </div>
                  </div>
                </div>

                  <div className="flex items-center gap-6 pl-16">
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">{filing.items} validation items</span>
                        <span className="text-sm font-medium text-gray-900">{filing.progress}%</span>
                      </div>
                      <div className="h-2.5 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            filing.progress === 100 ? 'bg-gray-900' :
                            filing.progress > 60 ? 'bg-gray-700' :
                            filing.progress > 30 ? 'bg-gray-600' :
                            'bg-gray-400'
                          }`}
                          style={{ width: `${filing.progress}%` }}
                        />
                      </div>
                    </div>
                    {filing.violations > 0 && (
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 border border-red-200 rounded-lg animate-pulse">
                        <AlertCircle className="w-4 h-4 text-red-600" />
                        <span className="text-sm font-medium text-red-700">{filing.violations} violations</span>
                      </div>
                    )}
                    <div className="flex gap-2">
                      {filing.violations > 0 && (
                        <button
                          onClick={() => onNavigateToValidation(filing.id)}
                          className="px-4 py-2 border-2 border-red-300 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 hover:border-red-400 text-sm font-medium transition-all active:scale-95 shadow-sm hover:shadow"
                        >
                          Fix Issues
                        </button>
                      )}
                      <button
                        onClick={() => onNavigateToFiling(filing.id)}
                        className="px-5 py-2 bg-gradient-to-r bg-gray-900 text-white rounded-lg hover:bg-gray-800 text-sm font-medium shadow-sm hover:shadow-md transition-all active:scale-95"
                      >
                        {filing.status === 'Pending' ? 'Start Filing' : 'Continue →'}
                      </button>
                      <button
                        onClick={() => setExpandedFiling(isExpanded ? null : filing.id)}
                        className="p-2 border-2 border-gray-300 rounded-lg hover:bg-gray-50 transition-all"
                      >
                        <ChevronDown className={`w-4 h-4 text-gray-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                      </button>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="mt-4 pl-16 pt-4 border-t border-gray-200 animate-in fade-in slide-in-from-top-2 duration-200">
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-gray-50 rounded-lg p-4">
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Bureau Contact</p>
                          <p className="text-sm font-medium text-gray-900">{filing.bureau}</p>
                          <p className="text-xs text-gray-600 mt-1">Filing ID: {filing.id}</p>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-4">
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Last Modified</p>
                          <p className="text-sm font-medium text-gray-900">{filing.lastActivity}</p>
                          <p className="text-xs text-gray-600 mt-1">by {filing.assignee}</p>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-4">
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Compliance</p>
                          <p className="text-sm font-medium text-gray-900">{filing.violations === 0 ? 'Passing' : `${filing.violations} Issues`}</p>
                          <p className="text-xs text-gray-600 mt-1">{filing.items} rules checked</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Upcoming Deadlines */}
        <div className="mt-8 bg-white border-2 border-gray-300 rounded-xl shadow-sm">
          <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-white">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-3xl mb-1" style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>Upcoming deadlines</h3>
                <p className="text-sm text-gray-600">Stay ahead of regulatory submission dates</p>
              </div>
              <button className="px-4 py-2 border-2 border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium">
                Calendar View
              </button>
            </div>
          </div>
          <div className="divide-y divide-gray-200">
            {upcomingDeadlines.map((deadline, idx) => (
              <div key={idx} className="p-6 flex items-center justify-between hover:bg-gradient-to-r hover:from-gray-50/30 hover:to-transparent transition-colors">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                    deadline.priority === 'high' ? 'bg-red-100' :
                    deadline.priority === 'medium' ? 'bg-orange-100' :
                    'bg-gray-100'
                  }`}>
                    <Calendar className={`w-6 h-6 ${
                      deadline.priority === 'high' ? 'text-red-600' :
                      deadline.priority === 'medium' ? 'text-orange-600' :
                      'text-gray-600'
                    }`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <p className="text-xl font-medium text-gray-900" style={{ fontFamily: 'Georgia, serif' }}>
                        {deadline.name}
                      </p>
                      <span className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded font-medium">
                        {deadline.bureau}
                      </span>
                      {deadline.priority === 'high' && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-50 text-red-700 border border-red-200 rounded text-xs font-medium">
                          <AlertCircle className="w-3 h-3" />
                          Urgent
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600">{deadline.type}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-2xl font-medium mb-1 ${
                    deadline.daysUntil < 20 ? 'text-red-600' :
                    deadline.daysUntil < 40 ? 'text-orange-600' :
                    'text-gray-900'
                  }`} style={{ fontFamily: 'Georgia, serif' }}>
                    {deadline.daysUntil} days
                  </p>
                  <p className="text-sm text-gray-500">Due {deadline.dueDate}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Data-source indicator */}
        <div className="mt-8 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-900">
            <strong>Data source:</strong>{' '}
            {(import.meta.env.VITE_API_MODE ?? 'mock') === 'live'
              ? 'Live API (/api/rhs → FastAPI + Snowflake)'
              : 'Mock fixtures via MSW — set VITE_API_MODE=live in web/.env.development to use the real backend'}
          </p>
        </div>
        </div>
      </div>
    </div>
  );
}
