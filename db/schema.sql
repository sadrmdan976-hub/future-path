-- FUTURE PATH | مستقبلك — مخطط قاعدة البيانات (PostgreSQL)
-- يُنفَّذ مرة واحدة بحساب مالك (postgres). كل التطبيق يعمل بدور future_path_app
-- مع تفعيل Row Level Security، فلا يمكن لطالب رؤية بيانات طالب آخر حتى لو أخطأ كود التطبيق.

create schema if not exists future_path;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'future_path_app') then
    create role future_path_app nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;

grant usage on schema future_path to future_path_app;

-- The connecting owner must be able to SET ROLE (needed on managed Postgres
-- such as Supabase, where the owner is not a superuser).
do $$
begin
  execute format('grant future_path_app to %I', current_user);
exception
  when duplicate_object then null;
end $$;

-- ============================== الجداول ==============================

create table future_path.users (
  id uuid primary key default gen_random_uuid(),
  email text not null check (char_length(email) <= 254 and position('@' in email) > 1),
  password_hash text not null,
  full_name text not null check (char_length(btrim(full_name)) between 2 and 120),
  account_type text not null default 'student' check (account_type in ('student', 'admin')),
  is_active boolean not null default true,
  is_demo boolean not null default false,
  email_verified_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index users_email_lower_key on future_path.users (lower(email));

create table future_path.profiles (
  user_id uuid primary key references future_path.users(id) on delete cascade,
  university text check (char_length(university) <= 160),
  college text check (char_length(college) <= 160),
  major text check (char_length(major) <= 160),
  study_year text check (char_length(study_year) <= 40),
  city text check (char_length(city) <= 80),
  bio text check (char_length(bio) <= 1500),
  updated_at timestamptz not null default now()
);

create table future_path.skills (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  skill_name text not null check (char_length(btrim(skill_name)) between 2 and 80),
  level smallint not null check (level between 1 and 5),
  sort_order integer not null default 0
);
create index skills_user_idx on future_path.skills (user_id, sort_order);

create table future_path.languages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  language text not null check (char_length(btrim(language)) between 2 and 60),
  proficiency text not null check (proficiency in ('beginner', 'intermediate', 'advanced', 'native')),
  sort_order integer not null default 0
);
create index languages_user_idx on future_path.languages (user_id, sort_order);

create table future_path.courses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  title text not null check (char_length(btrim(title)) between 2 and 160),
  provider text check (char_length(provider) <= 120),
  year text check (char_length(year) <= 12),
  sort_order integer not null default 0
);
create index courses_user_idx on future_path.courses (user_id, sort_order);

create table future_path.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  title text not null check (char_length(btrim(title)) between 2 and 160),
  description text check (char_length(description) <= 700),
  link text check (char_length(link) <= 400),
  sort_order integer not null default 0
);
create index projects_user_idx on future_path.projects (user_id, sort_order);

create table future_path.experiences (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  title text not null check (char_length(btrim(title)) between 2 and 160),
  organization text check (char_length(organization) <= 160),
  period text check (char_length(period) <= 60),
  description text check (char_length(description) <= 700),
  sort_order integer not null default 0
);
create index experiences_user_idx on future_path.experiences (user_id, sort_order);

create table future_path.interests_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  answers jsonb not null,
  suggested_fields text[] not null default '{}',
  created_at timestamptz not null default now()
);
create index interests_user_idx on future_path.interests_results (user_id, created_at desc);

create table future_path.learning_paths (
  id uuid primary key default gen_random_uuid(),
  title text not null check (char_length(btrim(title)) between 3 and 160),
  category text not null check (category in ('digital', 'languages', 'communication', 'professional', 'entrepreneurship')),
  description text not null check (char_length(description) <= 1200),
  resource_url text not null check (resource_url ~ '^https?://'),
  level text not null default 'beginner' check (level in ('beginner', 'intermediate', 'advanced')),
  duration text check (char_length(duration) <= 60),
  is_active boolean not null default true,
  is_demo boolean not null default false,
  created_at timestamptz not null default now()
);
create index learning_paths_category_idx on future_path.learning_paths (category, is_active);

create table future_path.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(btrim(name)) between 2 and 160),
  description text check (char_length(description) <= 1200),
  contact_details text check (char_length(contact_details) <= 400),
  city text check (char_length(city) <= 80),
  verification_status text not null default 'pending' check (verification_status in ('pending', 'verified', 'rejected')),
  is_demo boolean not null default false,
  created_by uuid references future_path.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table future_path.opportunities (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references future_path.organizations(id) on delete restrict,
  title text not null check (char_length(btrim(title)) between 3 and 180),
  type text not null check (type in ('training', 'job')),
  field text not null check (char_length(btrim(field)) between 2 and 80),
  city text not null check (char_length(btrim(city)) between 1 and 80),
  work_mode text not null check (work_mode in ('onsite', 'remote', 'hybrid')),
  description text not null check (char_length(description) <= 4000),
  requirements text check (char_length(requirements) <= 2000),
  tasks text check (char_length(tasks) <= 2000),
  location_details text check (char_length(location_details) <= 200),
  deadline date not null,
  status text not null default 'draft' check (status in ('draft', 'pending_review', 'published', 'suspended', 'closed')),
  is_verified boolean not null default false,
  is_demo boolean not null default false,
  published_at timestamptz,
  created_by uuid references future_path.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint opportunities_published_must_be_verified check (status <> 'published' or is_verified)
);
create index opportunities_status_idx on future_path.opportunities (status, published_at desc nulls last);
create index opportunities_deadline_idx on future_path.opportunities (deadline);
create index opportunities_org_idx on future_path.opportunities (organization_id);

create table future_path.applications (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references future_path.opportunities(id) on delete cascade,
  student_id uuid not null references future_path.users(id) on delete cascade,
  cv_snapshot jsonb not null,
  status text not null default 'submitted' check (status in ('submitted', 'under_review', 'invited', 'accepted', 'rejected', 'withdrawn')),
  applied_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (opportunity_id, student_id)
);
create index applications_student_idx on future_path.applications (student_id, applied_at desc);

create table future_path.reports (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references future_path.opportunities(id) on delete cascade,
  reporter_id uuid not null references future_path.users(id) on delete cascade,
  reason text not null check (char_length(reason) <= 300),
  details text check (char_length(details) <= 1000),
  status text not null default 'open' check (status in ('open', 'resolved', 'dismissed')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index reports_status_idx on future_path.reports (status, created_at desc);

create table future_path.admin_roles (
  user_id uuid primary key references future_path.users(id) on delete cascade,
  role text not null default 'admin' check (role in ('admin', 'superadmin')),
  granted_by uuid references future_path.users(id) on delete set null,
  granted_at timestamptz not null default now()
);

create table future_path.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  token_hash text not null unique,
  csrf_token text not null,
  user_agent text,
  ip text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index sessions_user_idx on future_path.sessions (user_id);

create table future_path.password_resets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references future_path.users(id) on delete cascade,
  token_hash text not null unique,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used_at timestamptz
);

-- ============================== الدوال المساعدة ==============================

create or replace function future_path.fp_uid()
returns uuid
language sql stable
as $$ select nullif(current_setting('app.user_id', true), '')::uuid $$;

create or replace function future_path.fp_is_admin()
returns boolean
language sql stable security definer
set search_path = future_path, pg_temp
as $$
  select exists (
    select 1 from future_path.admin_roles ar
    where ar.user_id = nullif(current_setting('app.user_id', true), '')::uuid
  )
$$;

-- مصادقة: البحث عن مستخدم لتسجيل الدخول (يعمل كمالك الجدول فيتجاوز RLS بحذر)
create or replace function future_path.fp_login_lookup(p_email text)
returns table (id uuid, password_hash text, full_name text, account_type text, is_active boolean, is_demo boolean)
language sql stable security definer
set search_path = future_path, pg_temp
as $$
  select u.id, u.password_hash, u.full_name, u.account_type, u.is_active, u.is_demo
  from future_path.users u
  where lower(u.email) = lower(btrim(p_email))
  limit 1
$$;

create or replace function future_path.fp_create_user(p_email text, p_password_hash text, p_full_name text)
returns uuid
language plpgsql security definer
set search_path = future_path, pg_temp
as $$
declare
  v_id uuid;
begin
  insert into future_path.users (email, password_hash, full_name, account_type)
  values (lower(btrim(p_email)), p_password_hash, btrim(p_full_name), 'student')
  returning id into v_id;
  insert into future_path.profiles (user_id) values (v_id);
  return v_id;
end $$;

create or replace function future_path.fp_set_password(p_user_id uuid, p_password_hash text)
returns void
language plpgsql security definer
set search_path = future_path, pg_temp
as $$
begin
  update future_path.users set password_hash = p_password_hash, updated_at = now() where id = p_user_id;
  delete from future_path.sessions where user_id = p_user_id;
end $$;

-- جلسات
create or replace function future_path.fp_create_session(
  p_user_id uuid, p_token_hash text, p_csrf text, p_expires timestamptz, p_user_agent text, p_ip text
) returns void
language plpgsql security definer
set search_path = future_path, pg_temp
as $$
begin
  delete from future_path.sessions where expires_at < now();
  insert into future_path.sessions (user_id, token_hash, csrf_token, expires_at, user_agent, ip)
  values (p_user_id, p_token_hash, p_csrf, p_expires, left(coalesce(p_user_agent, ''), 300), left(coalesce(p_ip, ''), 64));
end $$;

create or replace function future_path.fp_get_session(p_token_hash text)
returns table (user_id uuid, csrf_token text, expires_at timestamptz, last_seen_at timestamptz)
language sql stable security definer
set search_path = future_path, pg_temp
as $$
  select s.user_id, s.csrf_token, s.expires_at, s.last_seen_at
  from future_path.sessions s
  where s.token_hash = p_token_hash and s.expires_at > now()
  limit 1
$$;

create or replace function future_path.fp_touch_session(p_token_hash text)
returns void
language sql security definer
set search_path = future_path, pg_temp
as $$
  update future_path.sessions
  set last_seen_at = now(), expires_at = now() + interval '30 days'
  where token_hash = p_token_hash and expires_at > now()
$$;

create or replace function future_path.fp_delete_session(p_token_hash text)
returns void
language sql security definer
set search_path = future_path, pg_temp
as $$
  delete from future_path.sessions where token_hash = p_token_hash
$$;

-- استعادة كلمة المرور
create or replace function future_path.fp_request_reset(p_email text, p_token_hash text, p_expires timestamptz)
returns boolean
language plpgsql security definer
set search_path = future_path, pg_temp
as $$
declare
  v_id uuid;
begin
  select u.id into v_id from future_path.users u where lower(u.email) = lower(btrim(p_email)) limit 1;
  if v_id is null then
    return false;
  end if;
  delete from future_path.password_resets where user_id = v_id and used_at is null;
  insert into future_path.password_resets (user_id, token_hash, expires_at) values (v_id, p_token_hash, p_expires);
  return true;
end $$;

create or replace function future_path.fp_consume_reset(p_token_hash text)
returns uuid
language sql security definer
set search_path = future_path, pg_temp
as $$
  update future_path.password_resets
  set used_at = now()
  where token_hash = p_token_hash and used_at is null and expires_at > now()
  returning user_id
$$;

create or replace function future_path.fp_admin_create_reset(p_user_id uuid, p_token_hash text, p_expires timestamptz)
returns void
language plpgsql security definer
set search_path = future_path, pg_temp
as $$
begin
  if not future_path.fp_is_admin() then
    raise exception 'not authorized';
  end if;
  delete from future_path.password_resets where user_id = p_user_id and used_at is null;
  insert into future_path.password_resets (user_id, token_hash, expires_at) values (p_user_id, p_token_hash, p_expires);
end $$;

create or replace function future_path.fp_admin_set_active(p_user_id uuid, p_active boolean)
returns void
language plpgsql security definer
set search_path = future_path, pg_temp
as $$
begin
  if not future_path.fp_is_admin() then
    raise exception 'not authorized';
  end if;
  update future_path.users set is_active = p_active, updated_at = now() where id = p_user_id;
  if not p_active then
    delete from future_path.sessions where user_id = p_user_id;
  end if;
end $$;

-- ============================== الصلاحيات ==============================

revoke all on all tables in schema future_path from public;

grant select, insert, update, delete on
  future_path.profiles,
  future_path.skills,
  future_path.languages,
  future_path.courses,
  future_path.projects,
  future_path.experiences,
  future_path.interests_results,
  future_path.learning_paths,
  future_path.organizations,
  future_path.opportunities,
  future_path.applications,
  future_path.reports
to future_path_app;

revoke all on future_path.users from future_path_app;
grant select (id, email, full_name, account_type, is_active, is_demo, created_at, updated_at)
  on future_path.users to future_path_app;
grant update (full_name, updated_at) on future_path.users to future_path_app;

-- admin_roles: قراءة فقط للمسؤول (لفرض صلاحية fp_is_admin) وبلا أي كتابة عبر دور التطبيق
grant select on future_path.admin_roles to future_path_app;

-- sessions / password_resets / admin_roles: لا وصول مباشر إطلاقاً (دوال definer فقط)

revoke all on function
  future_path.fp_uid(),
  future_path.fp_is_admin(),
  future_path.fp_login_lookup(text),
  future_path.fp_create_user(text, text, text),
  future_path.fp_set_password(uuid, text),
  future_path.fp_create_session(uuid, text, text, timestamptz, text, text),
  future_path.fp_get_session(text),
  future_path.fp_touch_session(text),
  future_path.fp_delete_session(text),
  future_path.fp_request_reset(text, text, timestamptz),
  future_path.fp_consume_reset(text),
  future_path.fp_admin_create_reset(uuid, text, timestamptz),
  future_path.fp_admin_set_active(uuid, boolean)
from public;

grant execute on function
  future_path.fp_uid(),
  future_path.fp_is_admin(),
  future_path.fp_login_lookup(text),
  future_path.fp_create_user(text, text, text),
  future_path.fp_set_password(uuid, text),
  future_path.fp_create_session(uuid, text, text, timestamptz, text, text),
  future_path.fp_get_session(text),
  future_path.fp_touch_session(text),
  future_path.fp_delete_session(text),
  future_path.fp_request_reset(text, text, timestamptz),
  future_path.fp_consume_reset(text),
  future_path.fp_admin_create_reset(uuid, text, timestamptz),
  future_path.fp_admin_set_active(uuid, boolean)
to future_path_app;

-- ============================== Row Level Security ==============================

alter table future_path.users enable row level security;
alter table future_path.profiles enable row level security;
alter table future_path.skills enable row level security;
alter table future_path.languages enable row level security;
alter table future_path.courses enable row level security;
alter table future_path.projects enable row level security;
alter table future_path.experiences enable row level security;
alter table future_path.interests_results enable row level security;
alter table future_path.learning_paths enable row level security;
alter table future_path.organizations enable row level security;
alter table future_path.opportunities enable row level security;
alter table future_path.applications enable row level security;
alter table future_path.reports enable row level security;
alter table future_path.admin_roles enable row level security;
alter table future_path.sessions enable row level security;
alter table future_path.password_resets enable row level security;

create policy users_select_self on future_path.users
  for select to future_path_app
  using (id = future_path.fp_uid() or future_path.fp_is_admin());

create policy users_update_self on future_path.users
  for update to future_path_app
  using (id = future_path.fp_uid())
  with check (id = future_path.fp_uid());

create policy profiles_select_self on future_path.profiles
  for select to future_path_app
  using (user_id = future_path.fp_uid() or future_path.fp_is_admin());

create policy profiles_insert_self on future_path.profiles
  for insert to future_path_app
  with check (user_id = future_path.fp_uid());

create policy profiles_update_self on future_path.profiles
  for update to future_path_app
  using (user_id = future_path.fp_uid())
  with check (user_id = future_path.fp_uid());

create policy profiles_admin_all on future_path.profiles
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy skills_self on future_path.skills
  for all to future_path_app
  using (user_id = future_path.fp_uid())
  with check (user_id = future_path.fp_uid());

create policy skills_admin on future_path.skills
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy languages_self on future_path.languages
  for all to future_path_app
  using (user_id = future_path.fp_uid())
  with check (user_id = future_path.fp_uid());

create policy languages_admin on future_path.languages
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy courses_self on future_path.courses
  for all to future_path_app
  using (user_id = future_path.fp_uid())
  with check (user_id = future_path.fp_uid());

create policy courses_admin on future_path.courses
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy projects_self on future_path.projects
  for all to future_path_app
  using (user_id = future_path.fp_uid())
  with check (user_id = future_path.fp_uid());

create policy projects_admin on future_path.projects
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy experiences_self on future_path.experiences
  for all to future_path_app
  using (user_id = future_path.fp_uid())
  with check (user_id = future_path.fp_uid());

create policy experiences_admin on future_path.experiences
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy interests_self on future_path.interests_results
  for all to future_path_app
  using (user_id = future_path.fp_uid())
  with check (user_id = future_path.fp_uid());

create policy interests_admin on future_path.interests_results
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy learning_paths_read on future_path.learning_paths
  for select to future_path_app
  using (is_active or future_path.fp_is_admin());

create policy learning_paths_admin on future_path.learning_paths
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy organizations_read on future_path.organizations
  for select to future_path_app
  using (verification_status = 'verified' or future_path.fp_is_admin());

create policy organizations_admin on future_path.organizations
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy opportunities_read on future_path.opportunities
  for select to future_path_app
  using (status = 'published' or future_path.fp_is_admin());

create policy opportunities_admin on future_path.opportunities
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy applications_read_self on future_path.applications
  for select to future_path_app
  using (student_id = future_path.fp_uid() or future_path.fp_is_admin());

create policy applications_apply_self on future_path.applications
  for insert to future_path_app
  with check (
    student_id = future_path.fp_uid()
    and exists (
      select 1 from future_path.opportunities o
      where o.id = opportunity_id and o.status = 'published' and o.deadline >= current_date
    )
  );

create policy applications_withdraw_self on future_path.applications
  for update to future_path_app
  using (student_id = future_path.fp_uid() and status in ('submitted', 'under_review', 'invited'))
  with check (student_id = future_path.fp_uid() and status = 'withdrawn');

create policy applications_admin on future_path.applications
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy reports_insert_self on future_path.reports
  for insert to future_path_app
  with check (
    reporter_id = future_path.fp_uid()
    and exists (
      select 1 from future_path.opportunities o
      where o.id = opportunity_id and o.status = 'published'
    )
  );

create policy reports_read_self on future_path.reports
  for select to future_path_app
  using (reporter_id = future_path.fp_uid() or future_path.fp_is_admin());

create policy reports_admin on future_path.reports
  for all to future_path_app
  using (future_path.fp_is_admin())
  with check (future_path.fp_is_admin());

create policy admin_roles_read_admin on future_path.admin_roles
  for select to future_path_app
  using (future_path.fp_is_admin());

-- sessions / password_resets: RLS مفعّل بلا سياسة وبلا صلاحيات جدولية (دوال definer فقط).
-- منح دور مسؤول يتم حصراً بتشغيل SQL بحساب المالك (postgres) وليس عبر التطبيق.
