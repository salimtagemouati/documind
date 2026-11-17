create table if not exists refresh_sessions (
  id varchar(36) primary key,
  token_digest varchar(64) not null,
  expires_at timestamptz not null
);
create index if not exists ix_refresh_sessions_expires_at on refresh_sessions(expires_at);
alter table refresh_sessions enable row level security;
