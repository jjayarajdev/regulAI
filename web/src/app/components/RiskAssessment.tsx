import { ArrowLeft, MessageSquare, Users, FileText, Brain, CheckCircle, XCircle, AlertTriangle, TrendingUp, DollarSign, MapPin, Calendar } from 'lucide-react';
import { useState } from 'react';

interface RiskAssessmentProps {
  submissionId: string;
  onBack: () => void;
}

const mockRiskFactors = [
  { category: 'Location Risk', score: 72, factors: ['High crime area', 'Flood zone proximity'], status: 'warning' },
  { category: 'Financial Stability', score: 45, factors: ['Strong credit rating', 'Stable revenue'], status: 'good' },
  { category: 'Industry Risk', score: 68, factors: ['Moderate claims history', 'Regulatory compliance'], status: 'warning' },
  { category: 'Coverage Amount', score: 55, factors: ['Within appetite', 'Standard limits'], status: 'good' },
];

const mockComments = [
  { user: 'Mike Rodriguez', role: 'Risk Analyst', time: '2h ago', message: 'Completed preliminary risk assessment. Location risk is elevated due to flood zone.' },
  { user: 'Sarah Chen', role: 'Senior Underwriter', time: '1h ago', message: 'Reviewed financials. Company shows strong performance. Requesting additional loss run data.' },
];

const aiRecommendations = [
  { type: 'pricing', text: 'Suggested premium: $45,200 - $52,800 based on similar risks', confidence: 'High' },
  { type: 'terms', text: 'Recommend flood exclusion or 10% deductible increase', confidence: 'Medium' },
  { type: 'referral', text: 'Similar submissions approved at 15% loading', confidence: 'High' },
];

export function RiskAssessment({ submissionId, onBack }: RiskAssessmentProps) {
  const [activeTab, setActiveTab] = useState<'details' | 'risk' | 'collaboration'>('risk');

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={onBack}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-gray-900">Risk Assessment</h1>
              <p className="text-gray-500 text-sm mt-1">{submissionId} - Commercial Property</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-600" />
              <span>Decline</span>
            </button>
            <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-600" />
              <span>Refer</span>
            </button>
            <button className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2">
              <CheckCircle className="w-4 h-4" />
              <span>Approve</span>
            </button>
          </div>
        </div>
      </header>

      <div className="p-6">
        <div className="grid grid-cols-3 gap-6">
          {/* Main Content Area */}
          <div className="col-span-2 space-y-6">
            {/* Tabs */}
            <div className="bg-white border-2 border-gray-300 rounded-lg">
              <div className="border-b border-gray-200 px-4">
                <div className="flex gap-4">
                  <button
                    onClick={() => setActiveTab('details')}
                    className={`px-4 py-3 border-b-2 ${
                      activeTab === 'details' 
                        ? 'border-blue-600 text-blue-600' 
                        : 'border-transparent text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Submission Details
                  </button>
                  <button
                    onClick={() => setActiveTab('risk')}
                    className={`px-4 py-3 border-b-2 ${
                      activeTab === 'risk' 
                        ? 'border-blue-600 text-blue-600' 
                        : 'border-transparent text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Risk Analysis
                  </button>
                  <button
                    onClick={() => setActiveTab('collaboration')}
                    className={`px-4 py-3 border-b-2 ${
                      activeTab === 'collaboration' 
                        ? 'border-blue-600 text-blue-600' 
                        : 'border-transparent text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Team Collaboration
                  </button>
                </div>
              </div>

              <div className="p-6">
                {activeTab === 'details' && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600">Insured Name</p>
                        <p className="text-gray-900">Midwest Manufacturing Corp</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600">Broker</p>
                        <p className="text-gray-900">Acme Insurance Brokers</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600">Policy Type</p>
                        <p className="text-gray-900">Commercial Property</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600">Coverage Limit</p>
                        <p className="text-gray-900">$2,500,000</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600">Effective Date</p>
                        <p className="text-gray-900">Jan 1, 2025</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600">Industry</p>
                        <p className="text-gray-900">Manufacturing - Metal Parts</p>
                      </div>
                    </div>
                    <div className="pt-4 border-t border-gray-200">
                      <p className="text-sm text-gray-600 mb-2">Attached Documents</p>
                      <div className="space-y-2">
                        {['Application Form.pdf', 'Loss Runs 2021-2024.xlsx', 'Property Survey.pdf'].map((doc) => (
                          <div key={doc} className="flex items-center gap-2 p-2 border border-gray-300 rounded hover:bg-gray-50">
                            <FileText className="w-4 h-4 text-gray-600" />
                            <span className="text-sm text-gray-900">{doc}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'risk' && (
                  <div className="space-y-6">
                    {/* Overall Risk Score */}
                    <div className="flex items-center justify-between p-4 bg-gray-50 border border-gray-300 rounded-lg">
                      <div>
                        <p className="text-sm text-gray-600 mb-1">Overall Risk Score</p>
                        <p className="text-3xl text-gray-900">62 / 100</p>
                      </div>
                      <div className="w-24 h-24">
                        <div className="w-full h-full rounded-full border-8 border-yellow-500 flex items-center justify-center bg-white">
                          <TrendingUp className="w-8 h-8 text-yellow-600" />
                        </div>
                      </div>
                    </div>

                    {/* Risk Factors */}
                    <div className="space-y-3">
                      <p className="text-gray-900">Risk Factor Breakdown</p>
                      {mockRiskFactors.map((factor) => (
                        <div key={factor.category} className="border border-gray-300 rounded-lg p-4">
                          <div className="flex items-center justify-between mb-2">
                            <p className="text-gray-900">{factor.category}</p>
                            <span className={`px-2 py-1 rounded text-xs ${
                              factor.status === 'good' 
                                ? 'bg-green-100 text-green-700' 
                                : 'bg-yellow-100 text-yellow-700'
                            }`}>
                              Score: {factor.score}
                            </span>
                          </div>
                          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-2">
                            <div 
                              className={`h-full ${
                                factor.score < 50 ? 'bg-green-500' : 
                                factor.score < 70 ? 'bg-yellow-500' : 
                                'bg-red-500'
                              }`}
                              style={{ width: `${factor.score}%` }}
                            />
                          </div>
                          <ul className="space-y-1">
                            {factor.factors.map((item) => (
                              <li key={item} className="text-sm text-gray-600 flex items-center gap-2">
                                <span className="w-1 h-1 bg-gray-400 rounded-full"></span>
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === 'collaboration' && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 mb-4">
                      <Users className="w-5 h-5 text-gray-600" />
                      <p className="text-gray-900">Team Activity</p>
                    </div>
                    <div className="space-y-3">
                      {mockComments.map((comment, idx) => (
                        <div key={idx} className="border border-gray-300 rounded-lg p-4">
                          <div className="flex items-start gap-3">
                            <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
                              <span className="text-sm text-gray-700">{comment.user[0]}</span>
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <p className="text-sm text-gray-900">{comment.user}</p>
                                <span className="text-xs text-gray-500">{comment.role}</span>
                                <span className="text-xs text-gray-400">• {comment.time}</span>
                              </div>
                              <p className="text-sm text-gray-700">{comment.message}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="pt-4 border-t border-gray-200">
                      <textarea 
                        placeholder="Add a comment or tag a team member..."
                        className="w-full p-3 border border-gray-300 rounded-lg resize-none"
                        rows={3}
                      />
                      <div className="flex justify-end mt-2">
                        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                          Post Comment
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* AI Recommendations */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-5 h-5 text-purple-600" />
                <p className="text-gray-900">AI Recommendations</p>
              </div>
              <div className="space-y-3">
                {aiRecommendations.map((rec, idx) => (
                  <div key={idx} className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-purple-700 uppercase">{rec.type}</span>
                      <span className="text-xs px-2 py-0.5 bg-purple-200 text-purple-900 rounded">
                        {rec.confidence}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700">{rec.text}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
              <p className="text-gray-900 mb-3">Quick Actions</p>
              <div className="space-y-2">
                <button className="w-full px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-left flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-gray-600" />
                  <span className="text-sm">Run Rating Engine</span>
                </button>
                <button className="w-full px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-left flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-gray-600" />
                  <span className="text-sm">Check Location Data</span>
                </button>
                <button className="w-full px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-left flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-gray-600" />
                  <span className="text-sm">Schedule Meeting</span>
                </button>
                <button className="w-full px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-left flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-gray-600" />
                  <span className="text-sm">Contact Broker</span>
                </button>
              </div>
            </div>

            {/* SLA Tracker */}
            <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
              <p className="text-gray-900 mb-3">SLA Status</p>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Time Remaining</span>
                  <span className="text-sm text-orange-600">2h 15m</span>
                </div>
                <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div className="h-full bg-orange-500" style={{ width: '35%' }} />
                </div>
                <p className="text-xs text-gray-500">Target: 4h response time</p>
              </div>
            </div>
          </div>
        </div>

        {/* Wireframe Label */}
        <div className="mt-6 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-900">
            <strong>Wireframe 2:</strong> Risk Assessment View - Detailed workspace for evaluating submissions with AI recommendations, risk scoring, team collaboration, and automated decision support
          </p>
        </div>
      </div>
    </div>
  );
}
