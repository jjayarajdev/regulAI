import { FileText, Calendar, CheckCircle, AlertTriangle, Download, Upload, Clock, TrendingUp, Filter, Search } from 'lucide-react';

interface TexasStatisticalReportingProps {
  onBack: () => void;
}

const reportTypes = [
  { id: 'stat-01', name: 'Premium & Loss Data', frequency: 'Quarterly', nextDue: '2026-07-15', status: 'draft', completeness: 85 },
  { id: 'stat-02', name: 'Policy Count Report', frequency: 'Monthly', nextDue: '2026-06-15', status: 'submitted', completeness: 100 },
  { id: 'stat-03', name: 'Claims Summary', frequency: 'Quarterly', nextDue: '2026-07-15', status: 'in-progress', completeness: 62 },
  { id: 'stat-04', name: 'Exposure Data by ZIP', frequency: 'Annual', nextDue: '2026-12-31', status: 'pending', completeness: 0 },
  { id: 'stat-05', name: 'Rate Filing Support', frequency: 'Ad-hoc', nextDue: '—', status: 'draft', completeness: 45 },
];

const submissionHistory = [
  { period: 'Q1 2026', submittedDate: '2026-04-10', status: 'accepted', reports: 8, validator: 'TDI System' },
  { period: 'Q4 2025', submittedDate: '2026-01-12', status: 'accepted', reports: 8, validator: 'TDI System' },
  { period: 'Q3 2025', submittedDate: '2025-10-08', status: 'accepted-warnings', reports: 8, validator: 'TDI System' },
  { period: 'Q2 2025', submittedDate: '2025-07-11', status: 'accepted', reports: 8, validator: 'TDI System' },
];

const validationIssues = [
  { type: 'error', field: 'Premium Amount (Line 2.3)', message: 'Value exceeds threshold variance from prior period', report: 'stat-01' },
  { type: 'warning', field: 'ZIP Code 78945', message: 'Exposure count lower than historical average', report: 'stat-03' },
  { type: 'warning', field: 'Loss Ratio Calculation', message: 'Ratio outside expected range (0.45-0.85)', report: 'stat-01' },
];

const complianceMetrics = [
  { label: 'On-Time Submissions', value: '96%', change: '+2%', trend: 'up', icon: CheckCircle, color: 'green', description: 'vs last quarter' },
  { label: 'Validation Pass Rate', value: '92%', change: '-1%', trend: 'down', icon: TrendingUp, color: 'blue', description: 'first-time acceptance' },
  { label: 'Pending Reports', value: '3', change: '0', trend: 'neutral', icon: Clock, color: 'orange', description: 'due within 30 days' },
  { label: 'Data Quality Score', value: '88', change: '+3', trend: 'up', icon: FileText, color: 'purple', description: 'out of 100' },
];

export function TexasStatisticalReporting({ onBack }: TexasStatisticalReportingProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <button
                onClick={onBack}
                className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm"
              >
                ← Back
              </button>
              <div>
                <h1 className="text-gray-900">Texas Statistical Reporting</h1>
                <p className="text-gray-500 text-sm mt-1">TDI Compliance & Data Submission</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="px-3 py-2 bg-blue-50 border border-blue-300 rounded-lg">
              <p className="text-xs text-blue-700">Current Period</p>
              <p className="text-sm text-blue-900">Q2 2026</p>
            </div>
            <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2">
              <Upload className="w-4 h-4" />
              Submit to TDI
            </button>
          </div>
        </div>
      </header>

      <div className="p-6">
        {/* Compliance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {complianceMetrics.map((metric) => (
            <div key={metric.label} className={`bg-gradient-to-br from-${metric.color}-50 to-white border-2 border-${metric.color}-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`w-12 h-12 bg-${metric.color}-100 rounded-xl flex items-center justify-center`}>
                  <metric.icon className={`w-6 h-6 text-${metric.color}-600`} />
                </div>
                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium ${
                  metric.trend === 'up' ? 'bg-green-100 text-green-700' :
                  metric.trend === 'down' ? 'bg-red-100 text-red-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {metric.trend === 'up' ? '↑' : metric.trend === 'down' ? '↓' : '→'} {metric.change}
                </span>
              </div>
              <p className={`text-4xl font-medium text-${metric.color}-900 mb-2`} style={{ fontFamily: 'Georgia, serif' }}>
                {metric.value}
              </p>
              <p className="text-sm font-medium text-gray-900 mb-1">{metric.label}</p>
              <p className={`text-xs text-${metric.color}-700`}>{metric.description}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Report Types & Status */}
          <div className="lg:col-span-2">
            <div className="bg-white border-2 border-gray-300 rounded-lg">
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-gray-900">Required Statistical Reports</h2>
                  <div className="flex gap-2">
                    <button className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2">
                      <Filter className="w-4 h-4" />
                      <span className="text-sm">Filter</span>
                    </button>
                    <button className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      <span className="text-sm">Period</span>
                    </button>
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Report</th>
                      <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Frequency</th>
                      <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Next Due</th>
                      <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Completeness</th>
                      <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {reportTypes.map((report) => (
                      <tr key={report.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-gray-500" />
                            <div>
                              <p className="text-sm text-gray-900">{report.name}</p>
                              <p className="text-xs text-gray-500">{report.id}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700">{report.frequency}</td>
                        <td className="px-4 py-3">
                          <span className={`text-sm ${
                            report.nextDue === '—' ? 'text-gray-400' :
                            new Date(report.nextDue) < new Date('2026-06-30') ? 'text-red-600' :
                            'text-gray-700'
                          }`}>
                            {report.nextDue}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${
                                  report.completeness === 100 ? 'bg-green-500' :
                                  report.completeness > 60 ? 'bg-blue-500' :
                                  report.completeness > 0 ? 'bg-yellow-500' :
                                  'bg-gray-300'
                                }`}
                                style={{ width: `${report.completeness}%` }}
                              />
                            </div>
                            <span className="text-sm text-gray-700">{report.completeness}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex px-2 py-1 rounded text-xs border ${
                            report.status === 'submitted' ? 'bg-green-50 text-green-700 border-green-300' :
                            report.status === 'in-progress' ? 'bg-blue-50 text-blue-700 border-blue-300' :
                            report.status === 'draft' ? 'bg-yellow-50 text-yellow-700 border-yellow-300' :
                            'bg-gray-50 text-gray-700 border-gray-300'
                          }`}>
                            {report.status.replace('-', ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <button className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
                              Edit
                            </button>
                            <button className="p-1 hover:bg-gray-100 rounded">
                              <Download className="w-4 h-4 text-gray-600" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Validation Issues Panel */}
          <div className="bg-white border-2 border-gray-300 rounded-lg h-fit">
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-gray-900">Validation Issues</h3>
              <p className="text-xs text-gray-500 mt-1">Pre-submission checks</p>
            </div>
            <div className="p-4">
              <div className="space-y-3">
                {validationIssues.map((issue, idx) => (
                  <div key={idx} className={`p-3 rounded-lg border ${
                    issue.type === 'error' ? 'bg-red-50 border-red-300' : 'bg-yellow-50 border-yellow-300'
                  }`}>
                    <div className="flex items-start gap-2">
                      <AlertTriangle className={`w-4 h-4 mt-0.5 ${
                        issue.type === 'error' ? 'text-red-600' : 'text-yellow-600'
                      }`} />
                      <div className="flex-1">
                        <p className={`text-sm ${
                          issue.type === 'error' ? 'text-red-900' : 'text-yellow-900'
                        }`}>
                          {issue.field}
                        </p>
                        <p className={`text-xs mt-1 ${
                          issue.type === 'error' ? 'text-red-700' : 'text-yellow-700'
                        }`}>
                          {issue.message}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">{issue.report}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <button className="w-full mt-3 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
                Run Full Validation
              </button>
            </div>
          </div>
        </div>

        {/* Submission History */}
        <div className="bg-white border-2 border-gray-300 rounded-lg">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-gray-900">Submission History</h2>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by period..."
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm w-64"
                />
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Reporting Period</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Submission Date</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Reports Filed</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Validator</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {submissionHistory.map((submission, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900">{submission.period}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{submission.submittedDate}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{submission.reports} reports</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{submission.validator}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs border ${
                        submission.status === 'accepted' ? 'bg-green-50 text-green-700 border-green-300' :
                        submission.status === 'accepted-warnings' ? 'bg-yellow-50 text-yellow-700 border-yellow-300' :
                        'bg-gray-50 text-gray-700 border-gray-300'
                      }`}>
                        {submission.status === 'accepted' && <CheckCircle className="w-3 h-3" />}
                        {submission.status === 'accepted-warnings' && <AlertTriangle className="w-3 h-3" />}
                        {submission.status.replace('-', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
                          View
                        </button>
                        <button className="p-1 hover:bg-gray-100 rounded">
                          <Download className="w-4 h-4 text-gray-600" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Wireframe Label */}
        <div className="mt-6 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-900">
            <strong>Wireframe 3:</strong> Texas Statistical Reporting - Comprehensive interface for managing TDI compliance reports, tracking submission deadlines, validating data quality, and monitoring regulatory compliance across all required statistical filings
          </p>
        </div>
      </div>
    </div>
  );
}
