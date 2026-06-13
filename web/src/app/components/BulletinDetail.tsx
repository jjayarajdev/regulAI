import { FileText, CheckCircle, XCircle, AlertTriangle, Calendar, Bell, User } from 'lucide-react';
import { ReguAISidebar } from './ReguAISidebar';

interface BulletinDetailProps {
  bulletinId: string;
  onBack: () => void;
  onNavigate?: (view: string) => void;
  onSwitchToUnderwriting?: () => void;
}

export function BulletinDetail({ bulletinId, onBack, onNavigate, onSwitchToUnderwriting }: BulletinDetailProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      <ReguAISidebar
        activeView="bulletins"
        onNavigate={onNavigate || (() => {})}
        onSwitchToUnderwriting={onSwitchToUnderwriting}
      />
      <div className="ml-64 flex-1">
        <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Bulletins</p>
              <p className="text-sm text-gray-900">Bulletin {bulletinId}</p>
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
            ← Back to overview
          </button>

          <div className="mb-4">
            <div className="inline-flex px-3 py-1 bg-green-50 border border-green-300 rounded text-sm text-green-700 mb-3">
              <strong>approv'd</strong> bulletin in canon
            </div>
            <h1 className="text-4xl mb-2" style={{ fontFamily: 'Georgia, serif' }}>
              Credit Score Declination During Catastrophe Periods
            </h1>
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <span>Bulletin: <strong>762</strong></span>
              <span>·</span>
              <span>PC 2025.02.176</span>
              <span>·</span>
              <span>Insurance Code</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Summary Card */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-6">
              <h2 className="text-2xl mb-4" style={{ fontFamily: 'Georgia, serif' }}>Summary</h2>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <p className="text-sm text-blue-900">
                  <strong>Credit Score Declination During Catastrophe Periods</strong>
                </p>
                <p className="text-sm text-blue-800 mt-2">
                  Prohibited from using credit scores to decline coverage or increase rates during
                  catastrophic events (STATUTORY_CODE_ADDRESS_CATASTROPHIC_CONDITIONS.yaml
                  coordinate.yaml)
                </p>
              </div>
            </div>

            {/* Texas Legislature Reference */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-6">
              <h2 className="text-2xl mb-4" style={{ fontFamily: 'Georgia, serif' }}>
                Texas legislature PC 981.2948
              </h2>
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-gray-500 mb-2">Legal citation date</p>
                  <p className="text-gray-900">September 1, 2025</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-2">Linked to baseline</p>
                  <p className="text-gray-900">
                    <span className="text-blue-600 hover:underline cursor-pointer">
                      Section 981.2948 - Use of Credit Information
                    </span>
                  </p>
                </div>
              </div>
            </div>

            {/* Bulletins Statistics */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white border-2 border-gray-300 rounded-lg p-6">
                <p className="text-sm text-gray-500 mb-2">Total bulletins</p>
                <p className="text-5xl mb-2" style={{ fontFamily: 'Georgia, serif' }}>148</p>
                <p className="text-sm text-gray-600">12 Adopted · 112 does</p>
              </div>

              <div className="bg-green-50 border-2 border-green-300 rounded-lg p-6">
                <p className="text-sm text-green-700 mb-2">Status</p>
                <p className="text-4xl text-green-700 mb-2" style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic' }}>
                  4 cleared
                </p>
                <p className="text-sm text-green-700">3 created by System · 12 compliant reviews remain</p>
              </div>
            </div>

            {/* Veritas Analysis */}
            <div className="bg-white border-2 border-gray-300 rounded-lg">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-2xl" style={{ fontFamily: 'Georgia, serif' }}>Compliance analysis</h2>
              </div>

              <div className="grid grid-cols-2 divide-x divide-gray-200">
                {/* Invalid Cases */}
                <div className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <XCircle className="w-5 h-5 text-red-600" />
                    <h3 className="text-xl" style={{ fontFamily: 'Georgia, serif' }}>
                      Veritas <span className="text-red-600" style={{ fontStyle: 'italic' }}>invalid</span>
                    </h3>
                  </div>
                  <div className="space-y-3">
                    <div className="border-l-2 border-red-300 pl-3">
                      <p className="text-sm text-gray-900 mb-1">
                        PPC 981A2 reason code: 1-1, flagged with
                      </p>
                      <p className="text-sm text-gray-600">
                        Credit used as the basis of the other 'decline — credit
                        score,' even during catastrophe period
                      </p>
                    </div>
                    <div className="text-xs text-gray-500">
                      Bulletin PC-2025-02 line 43
                    </div>
                  </div>
                </div>

                {/* Valid Cases */}
                <div className="p-6 bg-green-50">
                  <div className="flex items-center gap-2 mb-4">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <h3 className="text-xl" style={{ fontFamily: 'Georgia, serif' }}>
                      Veritas <span className="text-green-600" style={{ fontStyle: 'italic' }}>valid</span>
                    </h3>
                  </div>
                  <div className="space-y-3">
                    <div className="border-l-2 border-green-300 pl-3">
                      <p className="text-sm text-gray-900 mb-1">
                        Bulletin in Texas, Connecticut, + four similar
                      </p>
                      <p className="text-sm text-gray-600">
                        Insurance law prohibits denying coverage during catastrophic
                        declarations when credit is the only deficiency
                      </p>
                    </div>
                    <div className="text-xs text-gray-500">
                      Compliant with PC-2025-02 § 981.2948
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Execution Notes */}
            <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
                <div>
                  <h3 className="text-lg mb-2" style={{ fontFamily: 'Georgia, serif' }}>
                    Execution notes + enforcement scope
                  </h3>
                  <p className="text-sm text-yellow-900 mb-3">
                    Determination of 'catastrophe period' definition varies
                  </p>
                  <ul className="list-disc list-inside text-sm text-yellow-800 space-y-1">
                    <li>Governor-declared emergency: automatic trigger</li>
                    <li>TDI Commissioner determination: case-by-case</li>
                    <li>ZIP-code level granularity required for enforcement</li>
                    <li>30-day window post-declaration minimum</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Related Filings */}
            <div className="bg-white border-2 border-gray-300 rounded-lg">
              <div className="p-4 border-b border-gray-200">
                <h3 className="text-lg" style={{ fontFamily: 'Georgia, serif' }}>Related filings</h3>
              </div>
              <div className="divide-y divide-gray-200">
                <div className="p-4 hover:bg-gray-50">
                  <p className="text-sm font-medium text-gray-900">TPA-Q4-2025</p>
                  <p className="text-xs text-gray-500 mt-1">Homeowners Statistical</p>
                </div>
                <div className="p-4 hover:bg-gray-50">
                  <p className="text-sm font-medium text-gray-900">CR-Annual-2025</p>
                  <p className="text-xs text-gray-500 mt-1">Credit Scoring Compliance</p>
                </div>
                <div className="p-4 hover:bg-gray-50">
                  <p className="text-sm font-medium text-gray-900">WC-Q4-2025</p>
                  <p className="text-xs text-gray-500 mt-1">Workers Compensation</p>
                </div>
              </div>
            </div>

            {/* Timeline */}
            <div className="bg-white border-2 border-gray-300 rounded-lg">
              <div className="p-4 border-b border-gray-200">
                <h3 className="text-lg" style={{ fontFamily: 'Georgia, serif' }}>Timeline</h3>
              </div>
              <div className="p-4 space-y-4">
                <div className="flex gap-3">
                  <Calendar className="w-4 h-4 text-gray-400 mt-0.5" />
                  <div>
                    <p className="text-sm text-gray-900">Effective date</p>
                    <p className="text-xs text-gray-500">Sept 1, 2025</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <Calendar className="w-4 h-4 text-gray-400 mt-0.5" />
                  <div>
                    <p className="text-sm text-gray-900">Last reviewed</p>
                    <p className="text-xs text-gray-500">Jan 15, 2026</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <Calendar className="w-4 h-4 text-gray-400 mt-0.5" />
                  <div>
                    <p className="text-sm text-gray-900">Next review</p>
                    <p className="text-xs text-gray-500">Jun 30, 2026</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
              <h3 className="text-lg mb-3" style={{ fontFamily: 'Georgia, serif' }}>Actions</h3>
              <div className="space-y-2">
                <button className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
                  Export bulletin
                </button>
                <button className="w-full px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
                  View compliance history
                </button>
                <button className="w-full px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
                  Create reminder
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Wireframe Label */}
        <div className="mt-8 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-900">
            <strong>Wireframe:</strong> Bulletin Detail - Comprehensive view of regulatory bulletin on Credit Score Declination During Catastrophe Periods, showing legal citations, compliance analysis (Veritas valid/invalid), execution notes, and related filings
          </p>
        </div>
        </div>
      </div>
    </div>
  );
}
