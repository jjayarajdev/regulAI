import { Dashboard } from './components/Dashboard';
import { RiskAssessment } from './components/RiskAssessment';
import { TexasStatisticalReporting } from './components/TexasStatisticalReporting';
import { ReguAIOverview } from './components/ReguAIOverview';
import { ReasonCodeValidation } from './components/ReasonCodeValidation';
import { RuleDetail } from './components/RuleDetail';
import { AuditLog } from './components/AuditLog';
import { BulletinDetail } from './components/BulletinDetail';
import { WorkstationApp } from './ws/WorkstationApp';
import { ExperienceApp } from './experience/ExperienceApp';
import { StatFileApp } from './statfile/StatFileApp';
import { useState } from 'react';

type ViewType =
  | 'dashboard'
  | 'assessment'
  | 'reporting'
  | 'reguai-overview'
  | 'validation'
  | 'rule-detail'
  | 'audit-log'
  | 'bulletin';

export default function App() {
  // STATFILE (ported from the Statistical Filing Platform design) is the
  // product direction. The CBRE experience stays at ?ui=experience, the older
  // workstation at ?ui=workstation, and the Figma wireframes at ?ui=wireframe.
  const ui = new URLSearchParams(window.location.search).get('ui');
  if (ui === 'wireframe') return <WireframeApp />;
  if (ui === 'workstation') return <WorkstationApp />;
  if (ui === 'experience') return <ExperienceApp />;
  return <StatFileApp />;
}

function WireframeApp() {
  const [currentView, setCurrentView] = useState<ViewType>('reguai-overview');
  const [selectedSubmission, setSelectedSubmission] = useState<string | null>(null);
  const [selectedFiling, setSelectedFiling] = useState<string | null>(null);
  const [selectedRule, setSelectedRule] = useState<string | null>(null);
  const [selectedBulletin, setSelectedBulletin] = useState<string | null>(null);

  // Underwriting Workbench handlers
  const handleViewSubmission = (id: string) => {
    setSelectedSubmission(id);
    setCurrentView('assessment');
  };

  const handleBackToDashboard = () => {
    setCurrentView('dashboard');
    setSelectedSubmission(null);
  };

  const handleViewReporting = () => {
    setCurrentView('reporting');
  };

  // ReguAI handlers
  const handleNavigateToFiling = (filingId: string) => {
    setSelectedFiling(filingId);
    setCurrentView('validation');
  };

  const handleNavigateToValidation = (filingId: string) => {
    setSelectedFiling(filingId);
    setCurrentView('validation');
  };

  const handleNavigateToRuleDetail = (ruleId: string) => {
    setSelectedRule(ruleId);
    setCurrentView('rule-detail');
  };

  const handleNavigateToAuditLog = (filingId: string) => {
    setSelectedFiling(filingId);
    setCurrentView('audit-log');
  };

  const handleNavigateToBulletin = (bulletinId: string) => {
    setSelectedBulletin(bulletinId);
    setCurrentView('bulletin');
  };

  const handleBackToReguAI = () => {
    setCurrentView('reguai-overview');
    setSelectedFiling(null);
    setSelectedRule(null);
    setSelectedBulletin(null);
  };

  const handleReguAINavigate = (view: string) => {
    switch (view) {
      case 'overview':
        setCurrentView('reguai-overview');
        break;
      case 'filing':
      case 'validation':
        handleNavigateToValidation('TPA-Q4-2025');
        break;
      case 'regulations':
        handleNavigateToRuleDetail('A.22');
        break;
      case 'bulletins':
        handleNavigateToBulletin('762');
        break;
      case 'audit-log':
        handleNavigateToAuditLog('TSPR-Q4-2025');
        break;
    }
  };

  const isReguAIView = ['reguai-overview', 'validation', 'rule-detail', 'audit-log', 'bulletin'].includes(currentView);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Menu - Only show for Underwriting Workbench views */}
      {!isReguAIView && (
        <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="px-6 py-3">
            <div className="flex items-center gap-6 mb-3">
              <h1 className="text-xl" style={{ fontFamily: 'Georgia, serif' }}>
                Insurance Platform Suite
              </h1>
            </div>
            <div className="flex gap-2">
              <div className="flex gap-2 pr-4 border-r border-gray-300">
                <button
                  onClick={handleBackToDashboard}
                  className={`px-4 py-2 text-sm rounded-lg ${
                    currentView === 'dashboard'
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  Underwriting Dashboard
                </button>
                <button
                  onClick={handleViewReporting}
                  className={`px-4 py-2 text-sm rounded-lg ${
                    currentView === 'reporting'
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  TX Statistical
                </button>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleBackToReguAI}
                  className="px-4 py-2 text-sm rounded-lg text-gray-700 hover:bg-gray-100"
                >
                  → Switch to ReguAI
                </button>
              </div>
            </div>
          </div>
        </nav>
      )}

      {/* View Content */}
      {currentView === 'dashboard' && (
        <Dashboard onViewSubmission={handleViewSubmission} />
      )}
      {currentView === 'assessment' && (
        <RiskAssessment
          submissionId={selectedSubmission!}
          onBack={handleBackToDashboard}
        />
      )}
      {currentView === 'reporting' && (
        <TexasStatisticalReporting onBack={handleBackToDashboard} />
      )}
      {currentView === 'reguai-overview' && (
        <ReguAIOverview
          onNavigateToFiling={handleNavigateToFiling}
          onNavigateToValidation={handleNavigateToValidation}
          onNavigate={handleReguAINavigate}
          onSwitchToUnderwriting={handleBackToDashboard}
        />
      )}
      {currentView === 'validation' && (
        <ReasonCodeValidation
          filingId={selectedFiling!}
          onBack={handleBackToReguAI}
          onNavigate={handleReguAINavigate}
          onSwitchToUnderwriting={handleBackToDashboard}
        />
      )}
      {currentView === 'rule-detail' && (
        <RuleDetail
          ruleId={selectedRule!}
          onBack={handleBackToReguAI}
          onNavigate={handleReguAINavigate}
          onSwitchToUnderwriting={handleBackToDashboard}
        />
      )}
      {currentView === 'audit-log' && (
        <AuditLog
          filingId={selectedFiling || 'TSPR-Q4-2025'}
          onBack={handleBackToReguAI}
          onNavigate={handleReguAINavigate}
          onSwitchToUnderwriting={handleBackToDashboard}
        />
      )}
      {currentView === 'bulletin' && (
        <BulletinDetail
          bulletinId={selectedBulletin!}
          onBack={handleBackToReguAI}
          onNavigate={handleReguAINavigate}
          onSwitchToUnderwriting={handleBackToDashboard}
        />
      )}
    </div>
  );
}
