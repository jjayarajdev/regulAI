import { AlertCircle, TrendingUp, Clock, CheckCircle, Search, Filter, Bell, User } from 'lucide-react';

interface DashboardProps {
  onViewSubmission: (id: string) => void;
}

const mockSubmissions = [
  { id: 'SUB-2024-001', broker: 'Acme Insurance Brokers', type: 'Commercial Property', value: '$2.5M', status: 'pending', priority: 'high', sla: '2h remaining', riskScore: null },
  { id: 'SUB-2024-002', broker: 'Global Risk Partners', type: 'Liability', value: '$850K', status: 'in-review', priority: 'medium', sla: '1d 4h remaining', riskScore: 72 },
  { id: 'SUB-2024-003', broker: 'Premier Underwriters', type: 'Marine Cargo', value: '$1.2M', status: 'in-review', priority: 'medium', sla: '18h remaining', riskScore: 58 },
  { id: 'SUB-2024-004', broker: 'Shield Insurance Group', type: 'Professional Indemnity', value: '$3.1M', status: 'pending', priority: 'high', sla: '4h remaining', riskScore: null },
  { id: 'SUB-2024-005', broker: 'Midwest Coverage LLC', type: 'Commercial Auto', value: '$680K', status: 'approved', priority: 'low', sla: 'Met SLA', riskScore: 45 },
];

const kpiData = [
  { label: 'Pending Review', value: '12', change: '+3', icon: Clock, color: 'text-orange-600' },
  { label: 'Avg Risk Score', value: '64', change: '-2', icon: TrendingUp, color: 'text-blue-600' },
  { label: 'SLA Compliance', value: '94%', change: '+1%', icon: CheckCircle, color: 'text-green-600' },
  { label: 'High Priority', value: '5', change: '+2', icon: AlertCircle, color: 'text-red-600' },
];

export function Dashboard({ onViewSubmission }: DashboardProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-gray-900">Underwriting Workbench</h1>
            <p className="text-gray-500 text-sm mt-1">Dashboard View</p>
          </div>
          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-gray-100 rounded-lg relative">
              <Bell className="w-5 h-5 text-gray-600" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
            </button>
            <div className="flex items-center gap-2 pl-4 border-l border-gray-200">
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-white" />
              </div>
              <div>
                <p className="text-sm text-gray-900">Sarah Chen</p>
                <p className="text-xs text-gray-500">Senior Underwriter</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="p-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {kpiData.map((kpi) => (
            <div key={kpi.label} className="bg-white border-2 border-gray-300 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <kpi.icon className={`w-5 h-5 ${kpi.color}`} />
                <span className={`text-sm ${kpi.change.startsWith('+') ? 'text-green-600' : 'text-gray-600'}`}>
                  {kpi.change}
                </span>
              </div>
              <p className="text-2xl text-gray-900 mb-1">{kpi.value}</p>
              <p className="text-sm text-gray-600">{kpi.label}</p>
            </div>
          ))}
        </div>

        {/* Submissions Table */}
        <div className="bg-white border-2 border-gray-300 rounded-lg">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-gray-900">New Business Submissions</h2>
              <div className="flex gap-2">
                <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2">
                  <Filter className="w-4 h-4" />
                  <span className="text-sm">Filter</span>
                </button>
                <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                  New Submission
                </button>
              </div>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search submissions, brokers, or policy types..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Submission ID</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Broker</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Value</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Risk Score</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">SLA</th>
                  <th className="px-4 py-3 text-left text-xs text-gray-600 uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {mockSubmissions.map((sub) => (
                  <tr key={sub.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {sub.priority === 'high' && (
                          <AlertCircle className="w-4 h-4 text-red-600" />
                        )}
                        <span className="text-sm text-gray-900">{sub.id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{sub.broker}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{sub.type}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{sub.value}</td>
                    <td className="px-4 py-3">
                      {sub.riskScore ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div 
                              className={`h-full ${
                                sub.riskScore < 50 ? 'bg-green-500' : 
                                sub.riskScore < 70 ? 'bg-yellow-500' : 
                                'bg-red-500'
                              }`}
                              style={{ width: `${sub.riskScore}%` }}
                            />
                          </div>
                          <span className="text-sm text-gray-700">{sub.riskScore}</span>
                        </div>
                      ) : (
                        <span className="text-sm text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-1 rounded text-xs border ${
                        sub.status === 'approved' ? 'bg-green-50 text-green-700 border-green-300' :
                        sub.status === 'in-review' ? 'bg-blue-50 text-blue-700 border-blue-300' :
                        'bg-gray-50 text-gray-700 border-gray-300'
                      }`}>
                        {sub.status.replace('-', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-sm ${
                        sub.sla.includes('remaining') && parseInt(sub.sla) < 5 ? 'text-red-600' :
                        'text-gray-700'
                      }`}>
                        {sub.sla}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button 
                        onClick={() => onViewSubmission(sub.id)}
                        className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm"
                      >
                        Review
                      </button>
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
            <strong>Wireframe 1:</strong> Dashboard View - Central hub for managing submissions, tracking KPIs, monitoring SLA compliance, and prioritizing work queue
          </p>
        </div>
      </div>
    </div>
  );
}
