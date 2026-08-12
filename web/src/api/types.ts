// Response shapes for the RegulAI RHS API (/api/rhs/*), mirrored from
// api/rhs_demo.py. These types are the contract shared by the live client
// and the MSW mock handlers — if the backend changes, update here first.

export interface Filing {
  id: string;                       // e.g. "TPA-Q4-2025"
  plan_name: string;
  plan_code: string;                // e.g. "TPA"
  policy_id_ranges: [number, number][];
  cadence: string;                  // "Quarterly" | "Monthly"
  period_start: string;             // ISO date
  period_end: string;
  due_date: string;
  channel: string;                  // e.g. "TICO ShareFile"
  is_active: boolean;
  jurisdiction_code: string;        // e.g. "US-TX"
}

export interface FilingsResponse {
  filings: Filing[];
  default: string;
}

export interface StateResponse {
  reference_loaded: boolean;
  bulletin_applied: boolean;
  bulletin_id: string;
  bulletin_title: string;
}

export type RuleStatus = 'pass' | 'fail' | 'error';
export type Severity = 'ERROR' | 'WARNING' | 'INFO';

export interface ValidationRule {
  rule_id: string;
  rule_number: string;              // e.g. "A.34"
  rule_name: string;
  target_table: string;             // e.g. "BRONZE.GW_PC_JOB"
  target_id_expr: string;
  violation_sql: string;
  violation_reason: string;
  severity: Severity;
  citation: string;
  jurisdiction_code: string;
  is_federal_default: boolean;
  status: RuleStatus;
  violation_count: number;
}

export interface Violation {
  rule_id: string;
  rule_number: string;
  rule_name: string;
  record_id: string;
  policy_number: string;
  violation_reason: string;
  severity: Severity;
  citation: string;
  suppressed?: boolean; // analyst-suppressed: visible but not blocking
}

export interface EditSuppression { memo: string; actor: string; created_at: string }
export interface EditAssignment { assignee: string; actor: string; assigned_at: string }

export interface ValidateResponse {
  summary: {
    rules_run: number;
    rules_passing: number;
    rules_failing: number;
    rules_errored: number;
    total_violations: number;
  };
  rules: ValidationRule[];
  violations: Violation[];
  run_id: string;
}

export interface FlatValidationRow {
  policy: string;
  action: string;                   // "CANCELLATION" | "DECLINATION" | "NONRENEWAL"
  reason_code: string;
  regulation_describes: string;
  rationale: string | null;
  validation_status: 'VALID' | 'INVALID';
  violation_reason: string | null;
}

export interface FlatValidationResponse {
  rows: FlatValidationRow[];
  count: number;
  invalid_count: number;
}

export interface BronzeCancellationRow {
  policy: string;
  action: string;
  reason_code: string;
  noticedate: string;
  effectivedate: string;
}

export interface BronzeCancellationsResponse {
  rows: BronzeCancellationRow[];
  count: number;
  filing: string;
}

export interface ClaimRow {
  claim_number: string;
  policy: string;
  loss_cause: string;
  loss_subtype: string;
  loss_date: string;
  reported_date: string;
  reporting_lag_days: number;
  total_incurred: number;
  in_twia_zone: boolean;
  state: string;
}

export interface ClaimsResponse {
  rows: ClaimRow[];
  count: number;
  filing: string;
}

export interface PipelineLayer {
  layer: 'BRONZE' | 'SILVER' | 'GOLD';
  table_count: number;
  row_total: number;
}

export interface PipelineStateResponse {
  layers: PipelineLayer[];
}

export interface KgRule {
  id: string;
  name: string;
  confidence: number | null; // Sentinel extraction confidence 0–1
  short_title: string | null;
  jurisdiction_code: string | null;
  rule_kind: string | null;
  clause_ref: string | null;       // the node's own section ref, e.g. "627.351(6)"
  created_by: string | null;
  created_at: string | null;
  severity: Severity;
  version: number;
  status: 'active' | 'superseded' | 'draft' | 'approved' | 'rejected';
  effective_from: string | null;
  effective_until: string | null;
  citation: string | null;
  section: string;
  executable: boolean;
  currently_active: boolean;
  source_doc: string | null;
  source_kind: string | null;
  source_url: string | null;
}

export interface KgRulesResponse {
  rules: KgRule[];
  counts: { total: number; executable: number; descriptive: number };
}

export type FilingStatus =
  | 'draft' | 'validating' | 'validated'
  | 'analyst_signed' | 'actuary_approved' | 'officer_approved'
  | 'submitted' | 'acked';

export interface AuditAction {
  action_id: string;
  action_type: string;
  actor: string;
  target_record: string | null;
  target_rule: string | null;
  summary: string;
  acted_at: string;
}

export interface FilingException {
  exception_id: string;
  source_record_id: string;
  policy_number: string;
  rule_number: string;
  rule_name: string;
  severity: Severity;
  violation_reason: string;
  resolution_status: 'open' | 'fixed';
  resolution_action: string | null;
  opened_at: string;
  resolved_at: string | null;
}

export interface AuditResponse {
  filing_id: string;
  batch: {
    filing_batch_id: string;
    status: FilingStatus;
    last_validated_at: string | null;
    last_validation_run_id: string | null;
    open_blockers: number;
    generated_at: string | null;
    submitted_at: string | null;
    acked_at: string | null;
  };
  actions: AuditAction[];
  exceptions: FilingException[];
}

export interface ApprovalStateResponse {
  filing_id: string;
  status: FilingStatus;
  open_blockers: number;
  next_role: 'analyst' | 'actuary' | 'officer' | null;
  can_seal: boolean;
  submitted_at: string | null;
  acked_at: string | null;
}

export interface Anomaly {
  anomaly_type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  territory_zip: string;
  cause_of_loss_code: string | null;
  current_month_value: number;
  rolling_12m_mean: number;
  rolling_12m_stddev: number;
  std_deviations_from_mean: number;
  anomaly_description: string;
  filing_batch_id: string;
  source_records: string[];
  flagged_at: string;
}

export interface AnomaliesResponse {
  filing: string;
  anomalies: Anomaly[];
  count: number;
}

export interface KgAuditEntry {
  id: string;
  action: string;
  actor: string;
  summary: string;
  occurred_at: string;
  affected_count: number;
}

export interface KgAuditResponse {
  entries: KgAuditEntry[];
  count: number;
  node_id: string | null;
}

// ── KG neighborhood (vis-network graph) ──────────────────────────
export interface KgGraphNode {
  id: string;
  label: string;
  group: string; // 'root' or the node's KG label (Rule, CodeList, FieldRequirement, …)
  sublabel?: string; // distinguishing context (parent layout, code meaning) or the label
  title: string;
  shape: 'box' | 'ellipse' | 'dot';
}

export interface KgGraphEdge {
  from: string;
  to: string;
  label: string;
}

export interface KgNeighborhoodResponse {
  nodes: KgGraphNode[];
  edges: KgGraphEdge[];
  center: string;
  truncated?: Record<string, number>; // label → count of nodes dropped by display caps
}

// ── mutations ─────────────────────────────────────────────────────
export type ApprovalRole = 'analyst' | 'actuary' | 'officer';

export interface ApproveResponse {
  filing_id: string;
  role: ApprovalRole;
  prev_state: string;
  new_state: string;
  actor: string;
}

export interface AckResponse {
  filing_id: string;
  receipt: string;
  new_state: 'acked';
}

export interface BulletinStepResult {
  step: string;
  ok: boolean;
  stdout?: string;
  stderr?: string;
}

export interface BulletinApplyResponse {
  ok: boolean;
  steps: BulletinStepResult[];
  deltas: Record<string, { closed_count: number; closed: { policy_number: string; rule_number: string }[] }>;
}

export interface BulletinResetResponse {
  ok: boolean;
  steps: BulletinStepResult[];
}

// ── filing submission journey (GET /filing/{id}/submission) ──────
export type SubmissionJourneyStatus =
  | 'validated' | 'analyst_signed' | 'actuary_approved' | 'officer_approved'
  | 'submitted' | 'sent' | 'acked';

export interface SubmissionApproval {
  filing_id: string;
  status: string;
  open_blockers: number;
  next_role: 'analyst' | 'actuary' | 'officer' | null;
  can_seal: boolean;
  submitted_at: string | null;
  acked_at: string | null;
}

export interface SealedSubmission {
  submission_id: string;
  sha256: string;
  file_name: string;
  record_count: number;
  file_size_bytes: number;
  sealed_at: string;
}

export interface SubmissionEmail {
  message_id: string;
  from: string;
  to: string[];
  subject: string;
  body: string | null;
  attachment: { name: string; bytes: number } | null;
  sent_at: string;
  eml_path: string;
  transport: 'outbox' | 'smtp';
}

export interface SubmissionAck { receipt: string; acked_at: string; eml_path: string }
export interface SubmissionArchive { path: string; sha256: string; archived_at: string }

export interface SubmissionState {
  filing_id: string;
  status: SubmissionJourneyStatus;
  approval: SubmissionApproval;
  submission: SealedSubmission | null;
  email: SubmissionEmail | null;
  sftp_path?: string | null;
  ack: SubmissionAck | null;
  archive: SubmissionArchive | null;
}

export interface SendFilingResponse {
  filing_id: string;
  status: 'sent';
  email: SubmissionEmail;
  sftp_path: string;
  archive: SubmissionArchive;
}

// GET /filing/{id}/file — the rendered fixed-width TSPR package.
export interface FilingFileResponse {
  filing_id: string;
  file_name: string;
  naic: string;
  record_count: number;
  byte_count: number;
  sha256: string;
  preview: string;
  header: string;
  footer: string;
  p_count: number;
  l_count: number;
  c_count: number;
  warning: string | null;
  persisted?: boolean;
  submission_id?: string;
}

// ── bulletins & amendment impact ──────────────────────────────────
export interface Bulletin {
  name: string;
  title: string;
  effective_date: string;
  status: 'pending' | 'applied';
  targets: number;
  summary: string;
  jurisdiction_code: string;
}

export interface BulletinsResponse {
  bulletins: Bulletin[];
  kg_offline?: boolean;
}

export interface RuleChangeSide {
  violation_sql: string;
  severity: Severity;
  violation_reason: string;
}

export interface RuleChangeRecords {
  newly_failing: number;
  newly_passing: number;
  sample_newly_failing: string[];
  sample_newly_passing: string[];
}

export interface RuleChange {
  rule_number: string;
  name: string;
  change_kind: 'modified' | 'added' | 'retired';
  before: RuleChangeSide | null;
  after: RuleChangeSide | null;
  records: RuleChangeRecords | null;
  sql_error?: string;
}

export interface BulletinImpact {
  bulletin: Bulletin;
  rule_changes: RuleChange[];
  totals: {
    rules_affected: number;
    newly_failing: number;
    newly_passing: number;
    filings_affected: string[];
  };
}

export type BronzeFixField = 'reason_code' | 'naic_number' | 'writtenpremium' | 'termtype' | 'noticedate';

export interface BronzeFixResponse {
  ok: boolean;
  policy_number: string;
  field: BronzeFixField;
  table: string;
  old_value: string | null;
  new_value: string | null;
}

// ── mapping review: schema-mapper proposals + human review ─────────
export type MappingTransformType = 'direct' | 'composite' | 'lookup';

export interface MappingSummary {
  name: string;                     // e.g. "guidewire_fl_fhcf"
  source_label: string;
  target: string;                   // e.g. "FHCF_EXPOSURE"
  target_table: string;             // e.g. "…SILVER.FHCF_EXPOSURE_STAGING"
  columns: number;
  overridden: number;               // human overrides recorded in review
  needs_review_flags: number;       // proposals the agent itself flagged
  avg_confidence: number | null;
  proposed_by: string | null;       // e.g. "openai:gpt-5.5"
  tokens: number | null;
  reviewed_by: string | null;
  review_summary: string | null;
  compiled: boolean;
  compiled_at: string | null;
}

export interface MappingsResponse {
  mappings: MappingSummary[];
}

export interface MappingColumn {
  target_column: string;
  source_column: string | null;     // null for per-cycle constants
  transform_type: MappingTransformType;
  confidence: number;
  needs_review: boolean;            // the agent's own flag on the proposal
  accepted: boolean;
  overridden: boolean;              // human review replaced the proposed SQL
  accepted_sql: string;
  proposed_sql: string | null;      // the agent's original expression
  override_reason: string | null;
  rationale: string | null;
  review_note: string | null;
}

export interface UnmappedSourceColumn {
  name: string;
  reason?: string;
}

// NB: in the detail response `columns` is the per-column array — the server
// spreads the summary then overwrites the numeric count with the array.
export interface MappingDetail extends Omit<MappingSummary, 'columns'> {
  source_relation: string;
  source_filter: string;
  notes: string | null;
  unmapped_source_columns: Array<string | UnmappedSourceColumn>;
  columns: MappingColumn[];
  compiled_sql: string | null;      // the compiled select_sql
}
