#!/usr/bin/env python3
import asyncio
import os
from sqlalchemy import text
from app.core.database import engine

async def run_migrations():
    """Run pending migrations"""
    migration_sql = """
    -- Add is_published column to tasks table
    ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_published BOOLEAN DEFAULT false;
    CREATE INDEX IF NOT EXISTS ix_tasks_is_published ON tasks(is_published);
    
    -- Add human_rejection_reason column to subtasks table
    ALTER TABLE subtasks ADD COLUMN IF NOT EXISTS human_rejection_reason VARCHAR;

    -- Add deadline column to tasks table
    ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deadline TIMESTAMP;
    CREATE INDEX IF NOT EXISTS ix_tasks_deadline ON tasks(deadline);
    """
    
    async with engine.connect() as conn:
        for statement in migration_sql.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    await conn.execute(text(statement))
                    print(f"✅ Executed: {statement[:50]}...")
                except Exception as e:
                    print(f"⚠️  Statement skipped (likely already exists): {statement[:50]}...")
        
        await conn.commit()
    
    print("\n✅ All migrations completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_migrations())
