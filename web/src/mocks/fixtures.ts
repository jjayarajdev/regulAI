// Mock data for every RHS endpoint, shaped 1:1 with api/rhs_demo.py responses
// (see src/api/types.ts). Four filings with deliberately different states:
//   TPA-Q4-2025  — clean, officer-approved, sealable (mid submission journey)
//   RES-M03-2026 — already sent + acknowledged + archived (full journey visible)
//   CL-Q4-2025   — early draft with errors
//   FHCF-A-2026  — Florida data call, validated with 3 open blockers
// Edit values here to exercise UI states (zero violations, huge counts, etc.).

import type {
  AnomaliesResponse,
  ApprovalStateResponse,
  AuditResponse,
  BronzeCancellationsResponse,
  BulletinImpact,
  BulletinsResponse,
  ClaimsResponse,
  FilingsResponse,
  FlatValidationResponse,
  KgAuditResponse,
  KgRulesResponse,
  PipelineStateResponse,
  SealedSubmission,
  StateResponse,
  SubmissionAck,
  SubmissionArchive,
  SubmissionEmail,
  ValidateResponse,
} from '../api/types';

export const filings: FilingsResponse = {
  filings: [
    {
      id: 'TPA-Q4-2025',
      plan_name: 'Texas Private Passenger Auto / Homeowners',
      plan_code: 'TPA',
      policy_id_ranges: [[2001, 2019], [2100, 2299]],
      cadence: 'Quarterly',
      period_start: '2025-10-01',
      period_end: '2025-12-31',
      due_date: '2026-07-15',
      channel: 'TICO ShareFile',
      is_active: true,
      jurisdiction_code: 'US-TX',
    },
    {
      id: 'RES-M03-2026',
      plan_name: 'Residential Property — March 2026',
      plan_code: 'RES',
      policy_id_ranges: [[2030, 2034], [2300, 2399]],
      cadence: 'Monthly',
      period_start: '2026-03-01',
      period_end: '2026-03-31',
      due_date: '2026-06-30',
      channel: 'TICO ShareFile',
      is_active: true,
      jurisdiction_code: 'US-TX',
    },
    {
      id: 'CL-Q4-2025',
      plan_name: 'Commercial Lines Q4 2025',
      plan_code: 'CL',
      policy_id_ranges: [[2050, 2053], [2400, 2449]],
      cadence: 'Quarterly',
      period_start: '2025-10-01',
      period_end: '2025-12-31',
      due_date: '2026-08-30',
      channel: 'TICO ShareFile',
      is_active: true,
      jurisdiction_code: 'US-TX',
    },
    {
      id: 'FHCF-A-2026',
      plan_name: 'Florida Hurricane Catastrophe Fund — Annual Data Call',
      plan_code: 'FHCF',
      policy_id_ranges: [[2500, 2599]],
      cadence: 'Annual',
      period_start: '2025-01-01',
      period_end: '2025-12-31',
      due_date: '2026-09-01',
      channel: 'FHCF Email Submission',
      is_active: true,
      jurisdiction_code: 'US-FL',
    },
  ],
  default: 'TPA-Q4-2025',
};

export const state: StateResponse = {
  reference_loaded: true,
  bulletin_applied: false,
  bulletin_id: 'B-2026-Q4-118',
  bulletin_title:
    "Commissioner's Bulletin B-2026-Q4-118 — Credit Score Declination During Catastrophe Periods",
};

const tpaRules: ValidateResponse['rules'] = [
  {
    rule_id: 'RULE-A.34-001',
    rule_number: 'A.34',
    rule_name: 'Reason code L (credit score declination) requires companion',
    target_table: 'BRONZE.GW_PC_JOB',
    target_id_expr: 'j.publicid',
    violation_sql: "LENGTH(j.declinereason) = 1 AND j.declinereason = 'L'",
    violation_reason: 'L requires companion code',
    severity: 'ERROR',
    citation: '§34 Notice Record Layout col36',
    jurisdiction_code: 'US-TX',
    is_federal_default: false,
    status: 'fail',
    violation_count: 2,
  },
  {
    rule_id: 'RULE-A.22-001',
    rule_number: 'A.22',
    rule_name: 'Notice date must precede effective date by 30+ days',
    target_table: 'BRONZE.GW_PC_JOB',
    target_id_expr: 'j.publicid',
    violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30',
    violation_reason: 'Insufficient notice period',
    severity: 'ERROR',
    citation: '§22 Notice Record Layout col12',
    jurisdiction_code: 'US-TX',
    is_federal_default: false,
    status: 'fail',
    violation_count: 1,
  },
  {
    rule_id: 'RULE-A.10-001',
    rule_number: 'A.10',
    rule_name: 'Written premium must be positive',
    target_table: 'BRONZE.GW_PC_POLICYPERIOD',
    target_id_expr: 'p.publicid',
    violation_sql: 'p.writtenpremium <= 0',
    violation_reason: 'Non-positive written premium',
    severity: 'ERROR',
    citation: '§10 Premium Record Layout col8',
    jurisdiction_code: 'US-TX',
    is_federal_default: false,
    status: 'pass',
    violation_count: 0,
  },
  {
    rule_id: 'RULE-B.10-001',
    rule_number: 'B.10',
    rule_name: 'Loss detail reported within 60 days',
    target_table: 'BRONZE.GW_CC_CLAIM',
    target_id_expr: 'c.claimnumber',
    violation_sql: 'DATEDIFF(day, c.lossdate, c.reporteddate) > 60',
    violation_reason: 'Loss reported late',
    severity: 'WARNING',
    citation: '§10 Loss Record Layout col15',
    jurisdiction_code: 'US-TX',
    is_federal_default: false,
    status: 'pass',
    violation_count: 0,
  },
];

export const validateByFiling: Record<string, ValidateResponse> = {
  // TPA is clean — the sign-off chain is complete and the filing is sealable.
  'TPA-Q4-2025': {
    summary: { rules_run: 10, rules_passing: 10, rules_failing: 0, rules_errored: 0, total_violations: 0 },
    rules: tpaRules.map((r) => ({ ...r, status: 'pass' as const, violation_count: 0 })),
    violations: [],
    run_id: 'run-mock-tpa-0001',
  },
  // The Florida data call carries the open blockers story.
  'FHCF-A-2026': {
    summary: { rules_run: 10, rules_passing: 8, rules_failing: 2, rules_errored: 0, total_violations: 3 },
    rules: tpaRules,
    violations: [
      {
        rule_id: 'RULE-A.34-001',
        rule_number: 'A.34',
        rule_name: 'Reason code L (credit score declination) requires companion',
        record_id: 'POL-0011',
        policy_number: 'POL-0011',
        violation_reason: 'L requires companion code',
        severity: 'ERROR',
        citation: '§34 Notice Record Layout col36',
      },
      {
        rule_id: 'RULE-A.34-001',
        rule_number: 'A.34',
        rule_name: 'Reason code L (credit score declination) requires companion',
        record_id: 'POL-0050',
        policy_number: 'POL-0050',
        violation_reason: 'L requires companion code',
        severity: 'ERROR',
        citation: '§34 Notice Record Layout col36',
      },
      {
        rule_id: 'RULE-A.22-001',
        rule_number: 'A.22',
        rule_name: 'Notice date must precede effective date by 30+ days',
        record_id: 'POL-0007',
        policy_number: 'POL-0007',
        violation_reason: 'Insufficient notice period',
        severity: 'ERROR',
        citation: '§22 Notice Record Layout col12',
      },
    ],
    run_id: 'run-mock-fhcf-0001',
  },
  'RES-M03-2026': {
    summary: { rules_run: 10, rules_passing: 10, rules_failing: 0, rules_errored: 0, total_violations: 0 },
    rules: tpaRules.map((r) => ({ ...r, status: 'pass' as const, violation_count: 0 })),
    violations: [],
    run_id: 'run-mock-res-0001',
  },
  'CL-Q4-2025': {
    summary: { rules_run: 10, rules_passing: 6, rules_failing: 3, rules_errored: 1, total_violations: 7 },
    rules: tpaRules.map((r, i) => ({
      ...r,
      status: i < 2 ? ('fail' as const) : ('pass' as const),
      violation_count: i === 0 ? 5 : i === 1 ? 2 : 0,
    })),
    violations: Array.from({ length: 7 }, (_, i) => ({
      rule_id: i < 5 ? 'RULE-A.34-001' : 'RULE-A.22-001',
      rule_number: i < 5 ? 'A.34' : 'A.22',
      rule_name:
        i < 5
          ? 'Reason code L (credit score declination) requires companion'
          : 'Notice date must precede effective date by 30+ days',
      record_id: `POL-04${10 + i}`,
      policy_number: `POL-04${10 + i}`,
      violation_reason: i < 5 ? 'L requires companion code' : 'Insufficient notice period',
      severity: 'ERROR' as const,
      citation: i < 5 ? '§34 Notice Record Layout col36' : '§22 Notice Record Layout col12',
    })),
    run_id: 'run-mock-cl-0001',
  },
};

export const flatValidation: FlatValidationResponse = {
  rows: [
    {
      policy: 'POL-0011',
      action: 'DECLINATION',
      reason_code: 'L',
      regulation_describes: 'Credit score declination',
      rationale: 'Insurer may decline based on credit score; must attach companion code',
      validation_status: 'INVALID',
      violation_reason: 'credit_score needs companion',
    },
    {
      policy: 'POL-0050',
      action: 'CANCELLATION',
      reason_code: 'AB',
      regulation_describes: 'Failure to pay premium + increase in hazard',
      rationale: null,
      validation_status: 'VALID',
      violation_reason: null,
    },
    {
      policy: 'POL-0007',
      action: 'NONRENEWAL',
      reason_code: 'C',
      regulation_describes: 'Nonrenewal at policy term end',
      rationale: null,
      validation_status: 'INVALID',
      violation_reason: 'must_appear_alone violated',
    },
  ],
  count: 3,
  invalid_count: 2,
};

export const bronzeByFiling: Record<string, BronzeCancellationsResponse> = {
  'TPA-Q4-2025': { rows: [], count: 0, filing: 'TPA-Q4-2025' },
  // The FHCF blockers' underlying bronze rows — the inline fix flow edits these.
  'FHCF-A-2026': {
    rows: [
      { policy: 'POL-0011', action: 'DECLINATION', reason_code: 'L', noticedate: '2025-11-15', effectivedate: '2025-12-01' },
      { policy: 'POL-0050', action: 'CANCELLATION', reason_code: 'L', noticedate: '2025-10-20', effectivedate: '2025-11-20' },
      { policy: 'POL-0007', action: 'NONRENEWAL', reason_code: 'C', noticedate: '2025-12-10', effectivedate: '2025-12-31' },
    ],
    count: 3,
    filing: 'FHCF-A-2026',
  },
  'RES-M03-2026': { rows: [], count: 0, filing: 'RES-M03-2026' },
  'CL-Q4-2025': {
    rows: [
      { policy: 'POL-0410', action: 'DECLINATION', reason_code: 'L', noticedate: '2025-11-01', effectivedate: '2025-11-15' },
    ],
    count: 1,
    filing: 'CL-Q4-2025',
  },
};

export const claimsByFiling: Record<string, ClaimsResponse> = {
  'TPA-Q4-2025': {
    rows: [
      {
        claim_number: 'CLM-2025-00123',
        policy: 'POL-0015',
        loss_cause: 'Theft',
        loss_subtype: 'Vehicle Theft',
        loss_date: '2025-09-10',
        reported_date: '2025-09-12',
        reporting_lag_days: 2,
        total_incurred: 25000,
        in_twia_zone: false,
        state: 'TX',
      },
      {
        claim_number: 'CLM-2025-00187',
        policy: 'POL-0011',
        loss_cause: 'Hail',
        loss_subtype: 'Roof Damage',
        loss_date: '2025-10-02',
        reported_date: '2025-10-30',
        reporting_lag_days: 28,
        total_incurred: 41250.5,
        in_twia_zone: true,
        state: 'TX',
      },
    ],
    count: 2,
    filing: 'TPA-Q4-2025',
  },
  'RES-M03-2026': { rows: [], count: 0, filing: 'RES-M03-2026' },
  'CL-Q4-2025': { rows: [], count: 0, filing: 'CL-Q4-2025' },
};

export const pipelineState: PipelineStateResponse = {
  layers: [
    { layer: 'BRONZE', table_count: 8, row_total: 2450 },
    { layer: 'SILVER', table_count: 4, row_total: 1200 },
    { layer: 'GOLD', table_count: 4, row_total: 950 },
  ],
};

// Fields the KG doesn't stamp on these seed rules default to null.
const kgRuleDefaults = {
  confidence: null,
  short_title: null,
  jurisdiction_code: 'US-TX',
  rule_kind: null,
  clause_ref: null,
  created_by: null,
  created_at: null,
  source_doc: null,
  source_kind: null,
  source_url: null,
};

export const kgRules: KgRulesResponse = {
  rules: [
    {
      ...kgRuleDefaults,
      id: 'RULE-A.34-001',
      name: 'Rule A.34 — Credit Score Declination Requirement',
      severity: 'ERROR',
      version: 2,
      status: 'active',
      effective_from: '2026-01-01',
      effective_until: null,
      citation: '§34 Notice Record Layout col36',
      section: 'A',
      executable: true,
      currently_active: true,
    },
    {
      ...kgRuleDefaults,
      id: 'RULE-A.22-001',
      name: 'Rule A.22 — Notice Period Requirement',
      severity: 'ERROR',
      version: 1,
      status: 'active',
      effective_from: '2025-01-01',
      effective_until: null,
      citation: '§22 Notice Record Layout col12',
      section: 'A',
      executable: true,
      currently_active: true,
    },
    {
      ...kgRuleDefaults,
      id: 'RULE-B.10-001',
      name: 'Rule B.10 — Loss Detail Timeliness',
      severity: 'WARNING',
      version: 1,
      status: 'superseded',
      effective_from: '2025-01-01',
      effective_until: '2025-12-31',
      citation: '§10 Loss Record Layout col15',
      section: 'B',
      executable: false,
      currently_active: false,
    },
  ],
  counts: { total: 3, executable: 2, descriptive: 1 },
};

export const bulletinText = `# Commissioner's Bulletin B-2026-Q4-118

## Credit Score Declination During Catastrophe Periods

### Effective Date
January 1, 2026

### Summary
During a declared catastrophe period, an insurer that declines an application
on the basis of credit score (reason code L) must report a companion reason
code identifying the catastrophe-related underwriting consideration.

### Applicability
All carriers reporting under the Texas Statistical Plan for Automobile and
Homeowners insurance (TSPR).

### Rule Changes
Rule A.34 is amended: reason code "L" submitted alone constitutes a reporting
violation for notice records dated within a declared catastrophe period.
`;

export const auditByFiling: Record<string, AuditResponse> = {
  'TPA-Q4-2025': {
    filing_id: 'TPA-Q4-2025',
    batch: {
      filing_batch_id: 'TPA-Q4-2025',
      status: 'officer_approved',
      last_validated_at: '2026-06-10 14:32:21',
      last_validation_run_id: 'run-mock-tpa-0001',
      open_blockers: 0,
      generated_at: '2026-06-01 10:00:00',
      submitted_at: null,
      acked_at: null,
    },
    actions: [
      {
        action_id: 'act-0001',
        action_type: 'validation_run',
        actor: 'system',
        target_record: null,
        target_rule: null,
        summary: '10 rules · 3 violations',
        acted_at: '2026-06-10 14:32:21',
      },
      {
        action_id: 'act-0002',
        action_type: 'manual_fix',
        actor: 'D. Reyes · Analyst',
        target_record: 'POL-0050',
        target_rule: 'reason_code',
        summary: 'declinereason: L → LB',
        acted_at: '2026-06-10 13:15:00',
      },
      {
        action_id: 'act-0003',
        action_type: 'analyst_approved',
        actor: 'M. Okonkwo · Analyst',
        target_record: null,
        target_rule: null,
        summary: 'M. Okonkwo signed off — state draft → analyst_signed',
        acted_at: '2026-06-09 15:00:00',
      },
    ],
    exceptions: [],
  },
  'RES-M03-2026': {
    filing_id: 'RES-M03-2026',
    batch: {
      filing_batch_id: 'RES-M03-2026',
      status: 'acked',
      last_validated_at: '2026-06-11 09:05:00',
      last_validation_run_id: 'run-mock-res-0001',
      open_blockers: 0,
      generated_at: '2026-06-02 08:00:00',
      submitted_at: '2026-06-12 09:41:00',
      acked_at: '2026-06-12 14:05:00',
    },
    actions: [],
    exceptions: [],
  },
  'FHCF-A-2026': {
    filing_id: 'FHCF-A-2026',
    batch: {
      filing_batch_id: 'FHCF-A-2026',
      status: 'validated',
      last_validated_at: '2026-06-12 07:45:00',
      last_validation_run_id: 'run-mock-fhcf-0001',
      open_blockers: 3,
      generated_at: '2026-06-08 09:00:00',
      submitted_at: null,
      acked_at: null,
    },
    actions: [],
    exceptions: [
      {
        exception_id: 'exc-FHCF-A-2026-POL-0011',
        source_record_id: 'POL-0011',
        policy_number: 'POL-0011',
        rule_number: 'A.34',
        rule_name: 'Reason code L requires companion',
        severity: 'ERROR',
        violation_reason: 'L requires companion code',
        resolution_status: 'open',
        resolution_action: null,
        opened_at: '2026-06-12 07:45:00',
        resolved_at: null,
      },
    ],
  },
  'CL-Q4-2025': {
    filing_id: 'CL-Q4-2025',
    batch: {
      filing_batch_id: 'CL-Q4-2025',
      status: 'validating',
      last_validated_at: '2026-06-12 08:00:00',
      last_validation_run_id: 'run-mock-cl-0001',
      open_blockers: 7,
      generated_at: '2026-06-05 12:00:00',
      submitted_at: null,
      acked_at: null,
    },
    actions: [],
    exceptions: [],
  },
};

export const approvalByFiling: Record<string, ApprovalStateResponse> = {
  // Mid-journey: chain complete, zero blockers — one Seal click from sending.
  'TPA-Q4-2025': {
    filing_id: 'TPA-Q4-2025',
    status: 'officer_approved',
    open_blockers: 0,
    next_role: null,
    can_seal: true,
    submitted_at: null,
    acked_at: null,
  },
  // Fully done: sealed, sent, acknowledged, archived (see submissionExtras).
  'RES-M03-2026': {
    filing_id: 'RES-M03-2026',
    status: 'acked',
    open_blockers: 0,
    next_role: null,
    can_seal: false,
    submitted_at: '2026-06-12 09:41:00',
    acked_at: '2026-06-12 14:05:00',
  },
  'CL-Q4-2025': {
    filing_id: 'CL-Q4-2025',
    status: 'validating',
    open_blockers: 7,
    next_role: 'analyst',
    can_seal: false,
    submitted_at: null,
    acked_at: null,
  },
  // Start of the journey: validated, but 3 ERROR blockers hold the chain.
  'FHCF-A-2026': {
    filing_id: 'FHCF-A-2026',
    status: 'validated',
    open_blockers: 3,
    next_role: 'analyst',
    can_seal: false,
    submitted_at: null,
    acked_at: null,
  },
};

// ── submission journey extras (seal / email / ack / archive) ────────
// Everything past the approval chain, per filing. RES carries the complete
// story so the Filing screen shows the whole journey instantly.
export const RES_SHA256 = 'e3b1c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
export interface SubmissionExtras {
  submission: SealedSubmission | null;
  email: SubmissionEmail | null;
  ack: SubmissionAck | null;
  archive: SubmissionArchive | null;
}
export const submissionExtrasByFiling: Record<string, SubmissionExtras> = {
  'TPA-Q4-2025': { submission: null, email: null, ack: null, archive: null },
  'CL-Q4-2025': { submission: null, email: null, ack: null, archive: null },
  'FHCF-A-2026': { submission: null, email: null, ack: null, archive: null },
  'RES-M03-2026': {
    submission: {
      submission_id: 'sub-res-7f2a91c04d61',
      sha256: RES_SHA256,
      file_name: 'TSPR_10639_RES_RESM032026.txt',
      record_count: 132,
      file_size_bytes: 26774,
      sealed_at: '2026-06-12 09:38:12',
    },
    email: {
      message_id: '<20260612094100.RES-M03-2026@regulai.demo>',
      from: 'filings@regulai.demo',
      to: ['stat-submissions@tico.example.org'],
      subject: 'RES statistical submission — RES-M03-2026 (Residential Property — March 2026)',
      body:
        'To the TX statistical reporting desk,\n\n'
        + 'Please find attached the sealed RES submission for filing RES-M03-2026, '
        + 'covering 2026-03-01 through 2026-03-31.\n\n'
        + 'File: TSPR_10639_RES_RESM032026.txt\nRecords: 132\nSHA-256: ' + RES_SHA256 + '\n\n'
        + 'The package was validated against the current edit reference and carries the\n'
        + 'full sign-off chain in its audit trail.\n\nRegards,\nRegulAI filing desk',
      attachment: { name: 'TSPR_10639_RES_RESM032026.txt', bytes: 26774 },
      sent_at: '2026-06-12 09:41:00',
      eml_path: 'outbox/RES-M03-2026/submission.eml',
      transport: 'outbox',
    },
    ack: {
      receipt: 'TICO-ACK-2026-004417',
      acked_at: '2026-06-12 14:05:00',
      eml_path: 'inbox/RES-M03-2026/ack.eml',
    },
    archive: {
      path: 'archive/2026/RES-M03-2026/TSPR_10639_RES_RESM032026.txt',
      sha256: RES_SHA256,
      archived_at: '2026-06-12 09:41:02',
    },
  },
};

export const anomaliesByFiling: Record<string, AnomaliesResponse> = {
  'TPA-Q4-2025': {
    filing: 'TPA-Q4-2025',
    anomalies: [
      {
        anomaly_type: 'EXCESSIVE_LOSS_RATIO',
        severity: 'HIGH',
        territory_zip: '75001',
        cause_of_loss_code: 'THEFT',
        current_month_value: 450000,
        rolling_12m_mean: 125000,
        rolling_12m_stddev: 45000,
        std_deviations_from_mean: 7.22,
        anomaly_description: 'Loss ratio 7.2σ above 12-month mean for ZIP 75001',
        filing_batch_id: 'TPA-Q4-2025',
        source_records: ['CLM-2025-00123', 'CLM-2025-00187'],
        flagged_at: '2026-06-10 14:30:00',
      },
    ],
    count: 1,
  },
  'RES-M03-2026': { filing: 'RES-M03-2026', anomalies: [], count: 0 },
  'CL-Q4-2025': { filing: 'CL-Q4-2025', anomalies: [], count: 0 },
};

export const kgAudit: KgAuditResponse = {
  entries: [
    {
      id: 'audit-20260610-001',
      action: 'bulletin_apply',
      actor: 'D. Reyes',
      summary: 'Applied B-2026-Q4-118 — credit score declination override',
      occurred_at: '2026-06-10 14:20:00',
      affected_count: 12,
    },
    {
      id: 'audit-20260609-005',
      action: 'rule_update',
      actor: 'system',
      summary: 'Rule A.34 version bumped to v2',
      occurred_at: '2026-06-09 16:45:30',
      affected_count: 1,
    },
  ],
  count: 2,
  node_id: null,
};

// ── bulletins & amendment impact ────────────────────────────────────
export const bulletins: BulletinsResponse = {
  bulletins: [
    {
      name: 'B-2026-Q4-118',
      title: 'Credit Score Declination During Catastrophe Periods',
      effective_date: '2026-01-01',
      status: 'pending',
      targets: 3,
      summary:
        'During a declared catastrophe period, reason code L submitted alone becomes a '
        + 'reporting violation — a companion catastrophe-related code is required on the notice record.',
      jurisdiction_code: 'US-TX',
    },
    {
      name: 'B-2026-Q3-104',
      title: 'Notice-Period Alignment for Renewal Declinations',
      effective_date: '2025-10-01',
      status: 'applied',
      targets: 2,
      summary:
        'Aligned the minimum notice window for nonrenewals with §22 (30 days), '
        + 'retiring the 21-day transitional rule.',
      jurisdiction_code: 'US-TX',
    },
  ],
};

export const bulletinImpacts: Record<string, BulletinImpact> = {
  'B-2026-Q4-118': {
    bulletin: bulletins.bulletins[0],
    rule_changes: [
      {
        rule_number: 'A.34',
        name: 'Reason code L (credit score declination) requires companion',
        change_kind: 'modified',
        before: {
          violation_sql: "LENGTH(j.declinereason) = 1 AND j.declinereason = 'L'",
          severity: 'WARNING',
          violation_reason: 'L should carry a companion code',
        },
        after: {
          violation_sql:
            "LENGTH(j.declinereason) = 1 AND j.declinereason = 'L'\n"
            + 'AND EXISTS (SELECT 1 FROM REF.CAT_PERIOD cp\n'
            + '  WHERE j.noticedate BETWEEN cp.start_date AND cp.end_date)',
          severity: 'ERROR',
          violation_reason: 'L alone during a declared catastrophe period',
        },
        records: {
          newly_failing: 12,
          newly_passing: 0,
          sample_newly_failing: ['POL-0011', 'POL-0050', 'POL-0410', 'POL-0412', 'POL-2107', 'POL-2151'],
          sample_newly_passing: [],
        },
      },
      {
        rule_number: 'A.22',
        name: 'Notice date must precede effective date by 30+ days',
        change_kind: 'modified',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period',
        },
        after: {
          violation_sql:
            'DATEDIFF(day, j.noticedate, j.effectivedate) < 30\n'
            + "AND j.action <> 'DECLINATION'",
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period (declinations carved out per bulletin)',
        },
        records: {
          newly_failing: 0,
          newly_passing: 2,
          sample_newly_failing: [],
          sample_newly_passing: ['POL-0007', 'POL-2103'],
        },
      },
      {
        rule_number: 'A.41',
        name: 'Catastrophe-period declination memo required',
        change_kind: 'added',
        before: null,
        after: {
          violation_sql:
            "j.declinereason LIKE 'L%' AND j.cat_memo IS NULL\n"
            + 'AND EXISTS (SELECT 1 FROM REF.CAT_PERIOD cp\n'
            + '  WHERE j.noticedate BETWEEN cp.start_date AND cp.end_date)',
          severity: 'WARNING',
          violation_reason: 'Catastrophe-period declination lacks the underwriting memo',
        },
        records: null,
        sql_error: 'REF.CAT_PERIOD not yet loaded in the warehouse — dry-run skipped',
      },
    ],
    totals: {
      rules_affected: 3,
      newly_failing: 12,
      newly_passing: 2,
      filings_affected: ['TPA-Q4-2025', 'CL-Q4-2025'],
    },
  },
  'B-2026-Q3-104': {
    bulletin: bulletins.bulletins[1],
    rule_changes: [
      {
        rule_number: 'A.22',
        name: 'Notice date must precede effective date by 30+ days',
        change_kind: 'modified',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 21',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period (21-day transitional window)',
        },
        after: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period',
        },
        records: {
          newly_failing: 4,
          newly_passing: 0,
          sample_newly_failing: ['POL-0007', 'POL-0413', 'POL-2110', 'POL-2144'],
          sample_newly_passing: [],
        },
      },
      {
        rule_number: 'A.22-T',
        name: 'Transitional 21-day notice window (2025)',
        change_kind: 'retired',
        before: {
          violation_sql:
            'DATEDIFF(day, j.noticedate, j.effectivedate) < 21\n'
            + "AND j.effectivedate < '2025-10-01'",
          severity: 'WARNING',
          violation_reason: 'Below the transitional 21-day window',
        },
        after: null,
        records: {
          newly_failing: 0,
          newly_passing: 3,
          sample_newly_failing: [],
          sample_newly_passing: ['POL-0021', 'POL-0038', 'POL-2131'],
        },
      },
    ],
    totals: {
      rules_affected: 2,
      newly_failing: 4,
      newly_passing: 3,
      filings_affected: ['TPA-Q4-2025'],
    },
  },
};
