import { CheckCircle, Circle, Clock, AlertCircle, User, Calendar, Bell, TrendingUp, Loader2, Check, X, FileText, Code, Info } from 'lucide-react';
import { ReguAISidebar } from './ReguAISidebar';
import { useState } from 'react';

interface ReasonCodeValidationProps {
  filingId: string;
  onBack: () => void;
  onNavigate?: (view: string) => void;
  onSwitchToUnderwriting?: () => void;
}

const validationSteps = [
  { id: 'sourcing', label: 'Sourcing', status: 'completed' },
  { id: 'reasoning', label: 'Reasoning', status: 'active' },
  { id: 'submitted', label: 'Submitted', status: 'pending' },
  { id: 'analyst-signed', label: 'Analyst signed off', status: 'pending' },
  { id: 'insurer-approved', label: 'Insurer approved', status: 'pending' },
  { id: 'officer-approved', label: 'Officer approved', status: 'pending' },
  { id: 'submitted-tdi', label: 'Submitted to TDI', status: 'pending' },
  { id: 'tdi-acked', label: 'TDI ACKed', status: 'pending' },
];

const reasonCodeSections = [
  {
    code: 'A',
    label: 'Assume',
    count: 3,
    color: 'red',
    description: 'Critical data validation errors',
    items: [
      {
        rule: 'A.27',
        description: 'Company Number',
        detail: 'MUST: Company Number must be present and exactly 5 numeric digits',
        status: 'error',
        affectedRecords: 12,
        severity: 'critical',
        autoFixable: true
      },
      {
        rule: 'A.12',
        description: 'Policy Effective Date',
        detail: 'Date format must be YYYY-MM-DD and within valid range',
        status: 'error',
        affectedRecords: 3,
        severity: 'high',
        autoFixable: false
      },
      {
        rule: 'A.05',
        description: 'Premium Amount Range',
        detail: 'Value exceeds maximum threshold for this line of business',
        status: 'error',
        affectedRecords: 1,
        severity: 'medium',
        autoFixable: false
      },
    ]
  },
  {
    code: 'Z',
    label: 'Provision',
    count: 2,
    color: 'green',
    description: 'Optional enhancements passed',
    items: [
      {
        rule: 'Z.12',
        description: 'Coverage Territory',
        detail: 'All territory codes validated against current TDI registry',
        status: 'valid',
        affectedRecords: 156,
        severity: 'info',
        autoFixable: false
      },
      {
        rule: 'Z.08',
        description: 'Rate Filing Linkage',
        detail: 'Successfully linked to approved rate filing RF-2025-0842',
        status: 'valid',
        affectedRecords: 156,
        severity: 'info',
        autoFixable: false
      },
    ]
  },
  {
    code: 'U',
    label: 'Link back',
    count: 1,
    color: 'purple',
    description: 'Cross-reference validation',
    items: [
      {
        rule: 'U.03',
        description: 'Prior Period Consistency',
        detail: 'WARNING: 8% variance from Q3 submission detected',
        status: 'warning',
        affectedRecords: 45,
        severity: 'medium',
        autoFixable: false
      },
    ]
  },
  {
    code: 'J',
    label: 'Audit cancel',
    count: 0,
    color: 'gray',
    description: 'No audit flags',
    items: []
  },
];

const activityLog = [
  {
    type: 'validation',
    user: 'System',
    action: 'Started 14-point validation',
    timestamp: '2025-06-13 14:35',
    icon: Circle,
    color: 'purple'
  },
  {
    type: 'issue',
    user: 'Claude AI',
    action: 'Pre-1990 NAIC: NAIC company code does not pre-exist until early 1990s',
    timestamp: '2025-06-13 14:34',
    icon: AlertCircle,
    color: 'purple'
  },
  {
    type: 'validation',
    user: 'System',
    action: 'M2 record: incorrect reason code Submitted to look for reasons and return',
    timestamp: '2025-06-13 14:33',
    icon: Circle,
    color: 'purple'
  },
  {
    type: 'insight',
    user: 'ExpoCheck',
    action: 'Texas Exposure - 1M4 records - 3 zeros',
    timestamp: '2025-06-13 14:30',
    icon: TrendingUp,
    color: 'blue'
  },
];

export function ReasonCodeValidation({ filingId, onBack, onNavigate, onSwitchToUnderwriting }: ReasonCodeValidationProps) {
  const [fixingRules, setFixingRules] = useState<Set<string>>(new Set());
  const [fixedRules, setFixedRules] = useState<Set<string>>(new Set());
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [selectedDetailRule, setSelectedDetailRule] = useState<any>(null);

  const handleAutoFix = async (ruleId: string, description: string) => {
    // Add to fixing state
    setFixingRules(prev => new Set(prev).add(ruleId));

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Move from fixing to fixed
    setFixingRules(prev => {
      const newSet = new Set(prev);
      newSet.delete(ruleId);
      return newSet;
    });
    setFixedRules(prev => new Set(prev).add(ruleId));

    // Show toast
    setToastMessage(`✓ Auto-fixed: ${description}`);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Toast Notification */}
      {showToast && (
        <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-right duration-300">
          <div className="bg-gradient-to-r from-green-600 to-green-500 text-white px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 min-w-[320px] border border-green-400">
            <div className="w-10 h-10 bg-green-400 rounded-full flex items-center justify-center shadow-lg">
              <Check className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <p className="font-semibold text-base">{toastMessage}</p>
              <p className="text-xs text-green-50 mt-1">Changes staged • Will apply on submit</p>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedDetailRule && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-red-50 to-orange-50 border-b-2 border-red-200 p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 bg-red-100 rounded-xl flex items-center justify-center">
                    <AlertCircle className="w-8 h-8 text-red-600" />
                  </div>
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-red-100 text-red-800 rounded-lg text-sm font-bold uppercase tracking-wider">
                        {selectedDetailRule.rule}
                      </span>
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium ${
                        selectedDetailRule.severity === 'critical' ? 'bg-red-200 text-red-900' :
                        selectedDetailRule.severity === 'high' ? 'bg-orange-100 text-orange-800' :
                        'bg-yellow-100 text-yellow-800'
                      }`}>
                        {selectedDetailRule.severity} severity
                      </span>
                    </div>
                    <h2 className="text-3xl font-medium text-gray-900 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
                      {selectedDetailRule.description}
                    </h2>
                    <p className="text-gray-600">{selectedDetailRule.detail}</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedDetailRule(null)}
                  className="p-2 hover:bg-red-100 rounded-lg transition-colors"
                >
                  <X className="w-6 h-6 text-gray-600" />
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
              {/* Impact Summary */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-red-50 border-2 border-red-200 rounded-xl p-4">
                  <p className="text-xs text-red-700 uppercase tracking-wider mb-1 font-semibold">Records Affected</p>
                  <p className="text-3xl font-medium text-red-900" style={{ fontFamily: 'Georgia, serif' }}>
                    {selectedDetailRule.affectedRecords}
                  </p>
                </div>
                <div className="bg-orange-50 border-2 border-orange-200 rounded-xl p-4">
                  <p className="text-xs text-orange-700 uppercase tracking-wider mb-1 font-semibold">Error Type</p>
                  <p className="text-lg font-medium text-orange-900">Data Validation</p>
                </div>
                <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-4">
                  <p className="text-xs text-blue-700 uppercase tracking-wider mb-1 font-semibold">Auto-Fix</p>
                  <p className="text-lg font-medium text-blue-900">
                    {selectedDetailRule.autoFixable ? '✓ Available' : '✗ Manual Fix Required'}
                  </p>
                </div>
              </div>

              {/* Error Details */}
              <div className="bg-gray-50 border-2 border-gray-300 rounded-xl p-6 mb-6">
                <div className="flex items-center gap-2 mb-4">
                  <Info className="w-5 h-5 text-blue-600" />
                  <h3 className="text-xl font-medium" style={{ fontFamily: 'Georgia, serif' }}>Error Details</h3>
                </div>
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-1">Validation Rule</p>
                    <p className="text-gray-900">{selectedDetailRule.detail}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-1">Bureau Requirement</p>
                    <p className="text-gray-900">TDI Statistical Reporting Manual Section 4.2.{selectedDetailRule.rule.split('.')[1]}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-1">Impact</p>
                    <p className="text-gray-900">Submission will be rejected if not corrected before filing deadline</p>
                  </div>
                </div>
              </div>

              {/* Sample Affected Records */}
              <div className="bg-white border-2 border-gray-300 rounded-xl overflow-hidden mb-6">
                <div className="bg-gray-100 border-b-2 border-gray-300 p-4">
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-gray-600" />
                    <h3 className="text-xl font-medium" style={{ fontFamily: 'Georgia, serif' }}>Sample Affected Records</h3>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b border-gray-300">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Record ID</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Policy Number</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Current Value</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Issue</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      <tr className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">REC-8472</td>
                        <td className="px-4 py-3 text-sm text-gray-900">POL-2026-003891</td>
                        <td className="px-4 py-3 text-sm font-mono text-red-600">NULL</td>
                        <td className="px-4 py-3 text-sm text-gray-700">Missing company number</td>
                      </tr>
                      <tr className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">REC-8473</td>
                        <td className="px-4 py-3 text-sm text-gray-900">POL-2026-003892</td>
                        <td className="px-4 py-3 text-sm font-mono text-red-600">12</td>
                        <td className="px-4 py-3 text-sm text-gray-700">Length &lt; 5 digits</td>
                      </tr>
                      <tr className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">REC-8474</td>
                        <td className="px-4 py-3 text-sm text-gray-900">POL-2026-003893</td>
                        <td className="px-4 py-3 text-sm font-mono text-red-600">A1234</td>
                        <td className="px-4 py-3 text-sm text-gray-700">Contains non-numeric characters</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div className="bg-gray-50 border-t border-gray-300 px-4 py-3">
                  <p className="text-xs text-gray-600">Showing 3 of {selectedDetailRule.affectedRecords} affected records</p>
                </div>
              </div>

              {/* Resolution Steps */}
              <div className="bg-blue-50 border-2 border-blue-300 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Code className="w-5 h-5 text-blue-600" />
                  <h3 className="text-xl font-medium" style={{ fontFamily: 'Georgia, serif' }}>Resolution Steps</h3>
                </div>
                {selectedDetailRule.autoFixable ? (
                  <div className="space-y-3">
                    <div className="flex gap-3">
                      <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">1</div>
                      <div>
                        <p className="font-medium text-gray-900">Click "Apply Auto-Fix" button</p>
                        <p className="text-sm text-gray-600">System will automatically correct all affected records</p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">2</div>
                      <div>
                        <p className="font-medium text-gray-900">Review staged changes</p>
                        <p className="text-sm text-gray-600">Verify corrections before final submission</p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">3</div>
                      <div>
                        <p className="font-medium text-gray-900">Submit to TDI</p>
                        <p className="text-sm text-gray-600">Changes will be applied during submission process</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex gap-3">
                      <div className="w-6 h-6 bg-orange-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">1</div>
                      <div>
                        <p className="font-medium text-gray-900">Export affected records</p>
                        <p className="text-sm text-gray-600">Download CSV with all validation failures</p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 bg-orange-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">2</div>
                      <div>
                        <p className="font-medium text-gray-900">Correct data in source system</p>
                        <p className="text-sm text-gray-600">Update values to meet validation requirements</p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 bg-orange-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">3</div>
                      <div>
                        <p className="font-medium text-gray-900">Re-import and validate</p>
                        <p className="text-sm text-gray-600">Upload corrected data and run validation again</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="border-t-2 border-gray-300 p-6 bg-gray-50 flex gap-3">
              <button
                onClick={() => setSelectedDetailRule(null)}
                className="flex-1 px-4 py-2.5 border-2 border-gray-300 rounded-lg hover:bg-gray-100 font-medium transition-all"
              >
                Close
              </button>
              {selectedDetailRule.autoFixable ? (
                <button
                  onClick={() => {
                    handleAutoFix(selectedDetailRule.rule, selectedDetailRule.description);
                    setSelectedDetailRule(null);
                  }}
                  className="flex-1 px-4 py-2.5 bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-lg hover:from-purple-700 hover:to-purple-800 font-medium shadow-sm hover:shadow transition-all active:scale-95"
                >
                  ⚡ Apply Auto-Fix Now
                </button>
              ) : (
                <button className="flex-1 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 font-medium shadow-sm hover:shadow transition-all active:scale-95">
                  Export Affected Records
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Sidebar */}
      <ReguAISidebar
        activeView="filing"
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
                <p className="text-sm text-gray-900">UEE76 · {filingId}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button className="p-2 hover:bg-gray-100 rounded-lg relative">
                <Bell className="w-5 h-5 text-gray-600" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
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
            className="px-4 py-2 mb-4 border-2 border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium flex items-center gap-2"
          >
            ← Back to overview
          </button>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="flex items-baseline gap-3 mb-3">
                <h1 className="text-5xl" style={{ fontFamily: 'Georgia, serif', fontWeight: 400 }}>
                  Reason-code{' '}
                  <span className="text-gray-600" style={{ fontStyle: 'italic' }}>validation</span>
                </h1>
              </div>
              <div className="flex items-center gap-2 flex-wrap text-sm">
                <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-lg font-medium">{filingId}</span>
                <span className="text-gray-400">·</span>
                <span className="text-gray-700">Section A · Reason code validation</span>
                <span className="text-gray-400">·</span>
                <span className="px-2 py-1 bg-red-50 text-red-700 border border-red-200 rounded font-medium">6 issues</span>
                <span className="text-gray-400">·</span>
                <span className="text-gray-600">162 records · 14 validation items</span>
              </div>
            </div>
            <div className="flex gap-2">
              <button className="px-4 py-2 border-2 border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium">
                Export Report
              </button>
              <button className="px-5 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 text-sm font-medium">
                Submit to TDI
              </button>
            </div>
          </div>
        </div>

        {/* Workflow Steps */}
        <div className="mb-8 bg-white border-2 border-gray-300 rounded-lg p-8">
          <div className="flex items-center justify-between">
            {validationSteps.map((step, idx) => (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center w-full">
                  <div className={`w-14 h-14 rounded-lg flex items-center justify-center mb-3 transition-all ${
                    step.status === 'completed' ? 'bg-gray-900 text-white' :
                    step.status === 'active' ? 'bg-gray-700 text-white ring-4 ring-gray-200' :
                    'bg-gray-200 text-gray-400'
                  }`}>
                    {step.status === 'completed' ? (
                      <CheckCircle className="w-7 h-7" />
                    ) : step.status === 'active' ? (
                      <Clock className="w-7 h-7" />
                    ) : (
                      <Circle className="w-6 h-6" />
                    )}
                  </div>
                  <span className={`text-sm text-center font-medium ${
                    step.status === 'completed' ? 'text-gray-900' :
                    step.status === 'active' ? 'text-gray-900' :
                    'text-gray-500'
                  }`}>
                    {step.label}
                  </span>
                </div>
                {idx < validationSteps.length - 1 && (
                  <div className="relative flex-1 mx-4" style={{ marginBottom: '3rem' }}>
                    <div className="h-1 bg-gray-200 rounded-full">
                      <div className={`h-full rounded-full transition-all ${
                        step.status === 'completed' ? 'bg-gray-900 w-full' : 'w-0'
                      }`} />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content - Reason Code Sections */}
          <div className="lg:col-span-2 space-y-4">
            {reasonCodeSections.map((section) => (
              <div key={section.code} className={`bg-white rounded-xl shadow-sm border-2 ${
                section.color === 'red' ? 'border-red-200' :
                section.color === 'green' ? 'border-green-200' :
                section.color === 'purple' ? 'border-purple-200' :
                'border-gray-200'
              }`}>
                <div className={`p-5 border-b-2 ${
                  section.color === 'red' ? 'bg-gradient-to-r from-red-50 to-red-50/50 border-red-200' :
                  section.color === 'green' ? 'bg-gradient-to-r from-green-50 to-green-50/50 border-green-200' :
                  section.color === 'purple' ? 'bg-gradient-to-r from-purple-50 to-purple-50/50 border-purple-200' :
                  'bg-gradient-to-r from-gray-50 to-gray-50/50 border-gray-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                        section.color === 'red' ? 'bg-red-100' :
                        section.color === 'green' ? 'bg-green-100' :
                        section.color === 'purple' ? 'bg-purple-100' :
                        'bg-gray-100'
                      }`}>
                        <span className={`text-3xl font-bold ${
                          section.color === 'red' ? 'text-red-700' :
                          section.color === 'green' ? 'text-green-700' :
                          section.color === 'purple' ? 'text-purple-700' :
                          'text-gray-700'
                        }`} style={{ fontFamily: 'Georgia, serif' }}>
                          {section.code}
                        </span>
                      </div>
                      <div>
                        <p className="text-xl font-medium text-gray-900">{section.label}</p>
                        <p className="text-sm text-gray-600">{section.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium ${
                        section.color === 'red' ? 'bg-red-100 text-red-800' :
                        section.color === 'green' ? 'bg-green-100 text-green-800' :
                        section.color === 'purple' ? 'bg-purple-100 text-purple-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {section.count} {section.count === 1 ? 'issue' : 'issues'}
                      </span>
                    </div>
                  </div>
                </div>

                {section.items.length > 0 ? (
                  <div className="p-5 space-y-3">
                    {section.items.map((item, idx) => {
                      const isFixing = fixingRules.has(item.rule);
                      const isFixed = fixedRules.has(item.rule);

                      return (
                        <div key={idx} className={`rounded-lg p-5 border-2 transition-all ${
                          isFixed ? 'bg-green-50 border-green-300' :
                          item.status === 'error' ? 'bg-red-50/50 border-red-200' :
                          item.status === 'warning' ? 'bg-yellow-50/50 border-yellow-200' :
                          'bg-green-50/50 border-green-200'
                        }`}>
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-3 mb-2">
                                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider ${
                                  isFixed ? 'bg-green-200 text-green-900' :
                                  item.status === 'error' ? 'bg-red-100 text-red-800' :
                                  item.status === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                                  'bg-green-100 text-green-800'
                                }`}>
                                  {item.rule}
                                </span>
                                {!isFixed && (
                                  <>
                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                                      item.severity === 'critical' ? 'bg-red-200 text-red-900' :
                                      item.severity === 'high' ? 'bg-orange-100 text-orange-800' :
                                      item.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                                      'bg-blue-100 text-blue-800'
                                    }`}>
                                      {item.severity}
                                    </span>
                                    {item.autoFixable && (
                                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                        ⚡ Auto-fixable
                                      </span>
                                    )}
                                  </>
                                )}
                                {isFixed && (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-200 text-green-900">
                                    <Check className="w-3 h-3" />
                                    Fixed
                                  </span>
                                )}
                              </div>
                              <h4 className="text-lg font-medium text-gray-900 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
                                {item.description}
                              </h4>
                              <p className="text-sm text-gray-700 mb-2">
                                {isFixed ? '✓ All validation rules now pass. Changes staged for submission.' : item.detail}
                              </p>
                              <p className="text-xs text-gray-500">{item.affectedRecords} records {isFixed ? 'corrected' : 'affected'}</p>
                            </div>
                            {!isFixed && item.status === 'error' && (
                              <AlertCircle className="w-6 h-6 text-red-600 ml-4" />
                            )}
                            {item.status === 'valid' && (
                              <CheckCircle className="w-6 h-6 text-green-600 ml-4" />
                            )}
                            {isFixed && (
                              <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center ml-4">
                                <Check className="w-6 h-6 text-white" />
                              </div>
                            )}
                          </div>
                          {item.autoFixable && !isFixed && (
                            <button
                              onClick={() => handleAutoFix(item.rule, item.description)}
                              disabled={isFixing}
                              className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                                isFixing
                                  ? 'bg-gray-400 text-white cursor-not-allowed'
                                  : 'bg-gray-900 text-white hover:bg-gray-800'
                              }`}
                            >
                              {isFixing ? (
                                <span className="flex items-center gap-2">
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                  Applying Fix...
                                </span>
                              ) : (
                                <span>Apply Auto-Fix →</span>
                              )}
                            </button>
                          )}
                          {!item.autoFixable && item.status === 'error' && !isFixed && (
                            <button
                              onClick={() => setSelectedDetailRule(item)}
                              className="px-4 py-2 border-2 border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium transition-all hover:border-gray-400 active:scale-95"
                            >
                              View Details →
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-8 text-center">
                    <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                    <p className="text-gray-600 font-medium">No issues detected</p>
                    <p className="text-sm text-gray-500 mt-1">All validations passed</p>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Activity Sidebar */}
          <div className="bg-white border-2 border-gray-300 rounded-lg h-fit">
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-lg" style={{ fontFamily: 'Georgia, serif' }}>Activity log</h3>
            </div>
            <div className="p-4 space-y-4">
              {activityLog.map((log, idx) => (
                <div key={idx} className="flex gap-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                    log.color === 'purple' ? 'bg-purple-100' : 'bg-blue-100'
                  }`}>
                    <log.icon className={`w-4 h-4 ${
                      log.color === 'purple' ? 'text-purple-600' : 'text-blue-600'
                    }`} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-gray-900 mb-1">{log.action}</p>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <span>{log.user}</span>
                      <span>·</span>
                      <span>{log.timestamp}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Wireframe Label */}
        <div className="mt-8 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-900">
            <strong>Wireframe:</strong> Reason-code Validation - Workflow interface showing validation progress, reason code sections (Assume, Provision, Link back, Audit cancel), rule violations, and real-time activity log
          </p>
        </div>
        </div>
      </div>
    </div>
  );
}
