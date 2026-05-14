-- DB initialization script for task_management
-- Run on PostgreSQL to create tables/types used by the application.
-- Usage: psql -d yourdb -f db/init.sql

-- Optional: enable uuid generation functions if desired
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ENUM types
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role_enum') THEN
        CREATE TYPE role_enum AS ENUM ('LEADER', 'ASSISTANT', 'QC', 'MEMBER');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_status_enum') THEN
        CREATE TYPE task_status_enum AS ENUM (
            'TODO', 'IN_PROGRESS', 'PENDING_AI_REVIEW', 'REJECTED_BY_AI',
            'APPEAL_PENDING', 'PENDING_HUMAN_QC', 'REJECTED_BY_HUMAN', 'DONE'
        );
    END IF;
END$$;

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

-- Table: projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE
);

-- Table: project_members (composite PK)
CREATE TABLE IF NOT EXISTS project_members (
    user_id UUID NOT NULL,
    project_id UUID NOT NULL,
    role role_enum DEFAULT 'MEMBER',
    PRIMARY KEY (user_id, project_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Table: tasks
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    raw_content TEXT,
    deadline TIMESTAMP WITHOUT TIME ZONE,
    is_published BOOLEAN DEFAULT FALSE,
    project_id UUID NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Table: subtasks
CREATE TABLE IF NOT EXISTS subtasks (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status task_status_enum DEFAULT 'TODO',
    task_id UUID NOT NULL,
    assigned_to_id UUID,
    evidence_url TEXT,
    ai_rejection_reason TEXT,
    appeal_reason TEXT,
    human_rejection_reason TEXT,
    approved_by_id UUID,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to_id) REFERENCES users(id),
    FOREIGN KEY (approved_by_id) REFERENCES users(id)
);

-- Table: activity_logs
CREATE TABLE IF NOT EXISTS activity_logs (
    id UUID PRIMARY KEY,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    user_id UUID NOT NULL,
    project_id UUID,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Table: refresh_tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY,
    token TEXT NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    expires_at TIMESTAMP WITHOUT TIME ZONE,
    revoked BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks (deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_is_published ON tasks (is_published);
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks (project_id);
CREATE INDEX IF NOT EXISTS idx_subtasks_status ON subtasks (status);
CREATE INDEX IF NOT EXISTS idx_subtasks_task_id ON subtasks (task_id);
CREATE INDEX IF NOT EXISTS idx_subtasks_assigned_to ON subtasks (assigned_to_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked ON refresh_tokens (revoked);

-- Seed: system sentinel user to represent auto-approvals by AI
-- Default sentinel used by app: 00000000-0000-0000-0000-000000000000
INSERT INTO users (id, username, password_hash)
VALUES ('00000000-0000-0000-0000-000000000000', 'system_ai', '')
ON CONFLICT (id) DO NOTHING;

-- End of script
