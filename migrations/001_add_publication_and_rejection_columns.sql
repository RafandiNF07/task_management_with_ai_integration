-- Migration: Add is_published to tasks and human_rejection_reason to subtasks
-- Created: 2026-05-10
-- This migration adds columns needed for the appeal workflow feature

-- Add is_published column to tasks table
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_published BOOLEAN DEFAULT false;
CREATE INDEX IF NOT EXISTS is_tasks_is_published ON tasks(is_published);

-- Add human_rejection_reason column to subtasks table
ALTER TABLE subtasks ADD COLUMN IF NOT EXISTS human_rejection_reason VARCHAR;

-- Log that migration ran successfully
SELECT 'Migration 001 completed: Added is_published and human_rejection_reason columns' AS migration_status;
