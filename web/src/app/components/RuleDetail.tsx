import { AlertCircle, Calendar, FileText, Code, Bell, User } from 'lucide-react';
import { ReguAISidebar } from './ReguAISidebar';

interface RuleDetailProps {
  ruleId: string;
  onBack: () => void;
  onNavigate?: (view: string) => void;
  onSwitchToUnderwriting?: () => void;
}

const relatedPolicies = [
  { period: 'JUL 2025 — JUL 2026', status: 'active', count: 142 },
  { period: 'JAN 2025 — JUN 2025', status: 'archived', count: 138 },
  { period: 'JUL 2024 — DEC 2024', status: 'archived', count: 145 },
  { period: 'JAN 2024 — JUN 2024', status: 'archived', count: 132 },
  { period: 'JUL 2023 — DEC 2023', status: 'archived', count: 128 },
];

const relatedRules = [
  { id: 'A.21', name: 'Company Number', relationship: 'Predecessor' },
  { id: 'A.23', name: 'Bureau and Company', relationship: 'Related' },
  { id: 'B.04', name: 'Company Grouping', relationship: 'Dependent' },
];

export function RuleDetail({ ruleId, onBack, onNavigate, onSwitchToUnderwriting }: RuleDetailProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      <ReguAISidebar
        activeView="regulations"
        onNavigate={onNavigate || (() => {})}
        onSwitchToUnderwriting={onSwitchToUnderwriting}
      />
      <div className="ml-64 flex-1">
        <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Regulations</p>
              <p className="text-sm text-gray-900">Rule {ruleId}</p>
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

          <div className="flex items-center gap-3 mb-2">
            <span className="text-sm text-gray-500">Section A / Rule A.22</span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {/* Rule Title */}
            <div className="mb-6">
              <h1 className="text-5xl mb-4" style={{ fontFamily: 'Georgia, serif' }}>
                Rule A.22— Company Number
              </h1>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span>Authority: <span className="text-blue-600">UTIL CODE Rule 5.3</span></span>
                <span>·</span>
                <span>Severity: <span className="text-red-600">critical</span></span>
                <span>·</span>
                <span>Trigger: M0-01, M2, M5, M5T, M5-PC-RCM-BB</span>
                <span>·</span>
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 border border-green-300 rounded">
                  ✓ compliant
                </span>
              </div>
            </div>

            {/* What Does This Mean */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-6 mb-6">
              <h2 className="text-2xl mb-4" style={{ fontFamily: 'Georgia, serif' }}>What this rule does</h2>
              <p className="text-gray-700 leading-relaxed">
                MUST: company number must be present and exactly 5 numeric digits.
              </p>
            </div>

            {/* Significant Dates */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-6 mb-6">
              <h2 className="text-2xl mb-4" style={{ fontFamily: 'Georgia, serif' }}>Significant dates</h2>
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">M Rule 1.B — G ( 0 )</p>
                    <p className="text-sm text-gray-600">1992-08-01 → forever</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Required Fields */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-6 mb-6">
              <h2 className="text-2xl mb-4" style={{ fontFamily: 'Georgia, serif' }}>Required fields</h2>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <Code className="w-4 h-4 text-gray-400" />
                  <code className="bg-gray-100 px-2 py-1 rounded text-gray-900">Record type</code>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Code className="w-4 h-4 text-gray-400" />
                  <code className="bg-gray-100 px-2 py-1 rounded text-gray-900">Company number (positions 14-18)</code>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Code className="w-4 h-4 text-gray-400" />
                  <code className="bg-gray-100 px-2 py-1 rounded text-gray-900">Record revision date</code>
                </div>
              </div>
            </div>

            {/* Error / Audit Alert */}
            <div className="bg-red-50 border-2 border-red-300 rounded-lg p-6">
              <div className="flex items-start gap-3 mb-4">
                <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
                <h2 className="text-2xl text-red-900" style={{ fontFamily: 'Georgia, serif' }}>
                  Error / Audit alert
                </h2>
              </div>
              <div className="bg-white border border-red-200 rounded p-4 mb-4">
                <p className="text-sm text-gray-600 mb-2">Raised when</p>
                <code className="block text-sm bg-gray-50 p-3 rounded text-gray-900 font-mono">
                  IF NOT ( M_REPT_CD IN ('M0', 'M1', 'M2', 'M3', 'M5') ) published in channel <span className="text-blue-600">stat.util.validation_txbb_wc</span> or <span className="text-blue-600">stat.util.validation_txbb_pc_pc-wc_attempted</span> THEN FAIL "M5 not valid at attempted reconciliation for {'{'}company_number{'}'} in record M5:m5_rec_id"
                </code>
              </div>

              <div className="bg-white border border-red-200 rounded p-4">
                <p className="text-sm text-gray-600 mb-2">Fix recommendations</p>
                <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                  <li>Verify company number is exactly 5 numeric digits</li>
                  <li>Check NAIC company directory for valid codes</li>
                  <li>Ensure record type matches expected format (M0, M1, M2, M3, M5)</li>
                  <li>Review record revision date for accuracy</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Policies Affected */}
            <div className="bg-white border-2 border-gray-300 rounded-lg">
              <div className="p-4 border-b border-gray-200">
                <h3 className="text-lg" style={{ fontFamily: 'Georgia, serif' }}>Policies</h3>
                <p className="text-xs text-gray-500 mt-1">Affected by this rule</p>
              </div>
              <div className="divide-y divide-gray-200">
                {relatedPolicies.map((policy, idx) => (
                  <div key={idx} className="p-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between mb-1">
                      <p className="text-sm font-medium text-gray-900">{policy.period}</p>
                      {policy.status === 'active' && (
                        <span className="inline-flex px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-300 rounded text-xs">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">{policy.count} policies</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Related Rules */}
            <div className="bg-white border-2 border-gray-300 rounded-lg">
              <div className="p-4 border-b border-gray-200">
                <h3 className="text-lg" style={{ fontFamily: 'Georgia, serif' }}>Related rules</h3>
              </div>
              <div className="divide-y divide-gray-200">
                {relatedRules.map((rule, idx) => (
                  <div key={idx} className="p-4 hover:bg-gray-50 cursor-pointer">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{rule.id}</p>
                        <p className="text-sm text-gray-600">{rule.name}</p>
                      </div>
                      <span className="text-xs text-gray-500">{rule.relationship}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Rule Metadata */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
              <h3 className="text-lg mb-3" style={{ fontFamily: 'Georgia, serif' }}>Metadata</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Last updated</span>
                  <span className="text-gray-900">2025-01-15</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Version</span>
                  <span className="text-gray-900">3.2.1</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Bureau</span>
                  <span className="text-gray-900">TDI</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Category</span>
                  <span className="text-gray-900">Data Validation</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Wireframe Label */}
        <div className="mt-8 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-900">
            <strong>Wireframe:</strong> Rule Detail - Comprehensive view of regulatory rule A.22 (Company Number), showing rule definition, authority, significant dates, required fields, error conditions, affected policies, and related rules
          </p>
        </div>
        </div>
      </div>
    </div>
  );
}
