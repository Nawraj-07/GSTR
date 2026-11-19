-- GSTR-9C tables for FinAxis Supabase (run in SQL Editor).
-- Reuses profiles, gst_registrations, documents, employee_has_client_access.
-- Do NOT create a new Supabase project.

create table if not exists public.gst_9c_cases (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.profiles(id) on delete cascade,
  registration_id uuid not null references public.gst_registrations(id) on delete cascade,
  gstin text not null,
  financial_year text not null,
  assigned_to uuid references public.profiles(id) on delete set null,
  status text not null default 'draft'
    check (status in ('draft','collecting_data','reconciling','draft_ready','in_review','approved','exported','archived')),
  notes text,
  created_by uuid references public.profiles(id) on delete set null,
  approved_by uuid references public.profiles(id) on delete set null,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (registration_id, financial_year)
);
create index if not exists idx_gst_9c_cases_client on public.gst_9c_cases(client_id);

create table if not exists public.gst_9c_documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  document_id uuid references public.documents(id) on delete set null,
  doc_type text not null check (doc_type in ('sales_register','purchase_register','trial_balance','profit_and_loss','balance_sheet','gstr9','other')),
  file_name text, storage_path text,
  status text not null default 'pending' check (status in ('pending','uploaded','parsed','error')),
  parse_error text,
  uploaded_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gst_import_jobs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  registration_id uuid references public.gst_registrations(id) on delete set null,
  job_type text not null check (job_type in ('fetch_returns','ingest_document','normalize','reconcile','generate_9c','export')),
  status text not null default 'queued' check (status in ('queued','running','succeeded','failed','cancelled')),
  progress numeric(5,2) not null default 0,
  input jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  error_message text,
  created_by uuid references public.profiles(id) on delete set null,
  started_at timestamptz, finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gst_api_logs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid references public.gst_9c_cases(id) on delete set null,
  client_id uuid references public.profiles(id) on delete set null,
  job_id uuid references public.gst_import_jobs(id) on delete set null,
  provider text not null default 'gstzen',
  action text not null,
  http_method text, request_path text, http_status int,
  ok boolean not null default false,
  reference_id text,
  request_meta jsonb not null default '{}'::jsonb,
  response_meta jsonb not null default '{}'::jsonb,
  duration_ms int,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.gst_imported_records (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  source text not null check (source in ('gstr1','gstr1a','gstr2','gstr2a','gstr2b','gstr3b','gstr9','sales_register','purchase_register','trial_balance','profit_and_loss','balance_sheet','manual','other')),
  source_document_id uuid references public.gst_9c_documents(id) on delete set null,
  source_snapshot_id uuid,
  tax_period text,
  record_type text not null default 'invoice',
  invoice_number text, invoice_date date, counterparty_gstin text,
  taxable_value numeric(18,2), igst numeric(18,2), cgst numeric(18,2), sgst numeric(18,2), cess numeric(18,2), total_tax numeric(18,2),
  raw jsonb not null default '{}'::jsonb,
  fingerprint text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_gst_imported_case on public.gst_imported_records(case_id);

create table if not exists public.gst_9c_reconciliation_runs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  comparison_type text not null check (comparison_type in ('gstr1_vs_sales','gstr3b_vs_gstr1','gstr2b_vs_purchases','gstr9_vs_financials','books_vs_returns','other')),
  status text not null default 'running' check (status in ('running','completed','failed')),
  summary jsonb not null default '{}'::jsonb,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gst_9c_reconciliation_items (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.gst_9c_reconciliation_runs(id) on delete cascade,
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  match_status text not null check (match_status in ('matched','partially_matched','mismatched','missing_in_gst','missing_in_books')),
  difference_type text,
  difference_amount numeric(18,2),
  left_record_id uuid references public.gst_imported_records(id) on delete set null,
  right_record_id uuid references public.gst_imported_records(id) on delete set null,
  explanation text,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.gst_9c_adjustments (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  table_code text, field_key text,
  amount numeric(18,2) not null default 0,
  explanation text not null,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gst_9c_drafts (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  version int not null default 1,
  status text not null default 'draft' check (status in ('draft','in_review','approved','superseded')),
  fy_schema_key text not null,
  summary jsonb not null default '{}'::jsonb,
  created_by uuid references public.profiles(id) on delete set null,
  approved_by uuid references public.profiles(id) on delete set null,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (case_id, version)
);

create table if not exists public.gst_9c_table_values (
  id uuid primary key default gen_random_uuid(),
  draft_id uuid not null references public.gst_9c_drafts(id) on delete cascade,
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  table_code text not null, row_key text not null, col_key text not null,
  value numeric(18,2), value_text text,
  source_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (draft_id, table_code, row_key, col_key)
);

create table if not exists public.gst_9c_exports (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.gst_9c_cases(id) on delete cascade,
  client_id uuid not null references public.profiles(id) on delete cascade,
  draft_id uuid references public.gst_9c_drafts(id) on delete set null,
  export_type text not null check (export_type in ('reconciliation_excel','gstr9c_excel','gstr9c_pdf','other')),
  storage_path text, file_name text,
  status text not null default 'queued' check (status in ('queued','ready','failed')),
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gst_audit_logs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid references public.gst_9c_cases(id) on delete set null,
  client_id uuid references public.profiles(id) on delete set null,
  actor_id uuid references public.profiles(id) on delete set null,
  action text not null,
  entity_type text, entity_id uuid,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- RLS
alter table public.gst_9c_cases enable row level security;
alter table public.gst_9c_documents enable row level security;
alter table public.gst_import_jobs enable row level security;
alter table public.gst_api_logs enable row level security;
alter table public.gst_imported_records enable row level security;
alter table public.gst_9c_reconciliation_runs enable row level security;
alter table public.gst_9c_reconciliation_items enable row level security;
alter table public.gst_9c_adjustments enable row level security;
alter table public.gst_9c_drafts enable row level security;
alter table public.gst_9c_table_values enable row level security;
alter table public.gst_9c_exports enable row level security;
alter table public.gst_audit_logs enable row level security;

do $$
declare t text;
begin
  foreach t in array array[
    'gst_9c_cases','gst_9c_documents','gst_import_jobs','gst_imported_records',
    'gst_9c_reconciliation_runs','gst_9c_reconciliation_items','gst_9c_adjustments',
    'gst_9c_drafts','gst_9c_table_values','gst_9c_exports'
  ]
  loop
    execute format('drop policy if exists %I on public.%I', t||'_select', t);
    execute format('create policy %I on public.%I for select to authenticated using (public.employee_has_client_access(auth.uid(), client_id))', t||'_select', t);
    execute format('drop policy if exists %I on public.%I', t||'_insert', t);
    execute format('create policy %I on public.%I for insert to authenticated with check (public.employee_has_client_access(auth.uid(), client_id))', t||'_insert', t);
    execute format('drop policy if exists %I on public.%I', t||'_update', t);
    execute format('create policy %I on public.%I for update to authenticated using (public.employee_has_client_access(auth.uid(), client_id)) with check (public.employee_has_client_access(auth.uid(), client_id))', t||'_update', t);
    execute format('drop policy if exists %I on public.%I', t||'_delete', t);
    execute format('create policy %I on public.%I for delete to authenticated using (public.employee_has_client_access(auth.uid(), client_id))', t||'_delete', t);
  end loop;
end $$;

drop policy if exists gst_api_logs_select on public.gst_api_logs;
create policy gst_api_logs_select on public.gst_api_logs for select to authenticated
  using (client_id is not null and public.employee_has_client_access(auth.uid(), client_id));
drop policy if exists gst_api_logs_insert on public.gst_api_logs;
create policy gst_api_logs_insert on public.gst_api_logs for insert to authenticated
  with check (client_id is null or public.employee_has_client_access(auth.uid(), client_id));

drop policy if exists gst_audit_select on public.gst_audit_logs;
create policy gst_audit_select on public.gst_audit_logs for select to authenticated
  using (client_id is not null and public.employee_has_client_access(auth.uid(), client_id));
drop policy if exists gst_audit_insert on public.gst_audit_logs;
create policy gst_audit_insert on public.gst_audit_logs for insert to authenticated
  with check (client_id is null or public.employee_has_client_access(auth.uid(), client_id));
