# app/services/project_service.py
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.domain import Project, ProjectMember, User, RoleEnum, ActivityLog
import uuid

class ProjectService:
    @staticmethod
    async def create_project(db: AsyncSession, name: str, leader_id: uuid.UUID):
        # 1. Buat Proyek Baru
        new_project = Project(name=name)
        db.add(new_project)
        await db.flush() # Ambil ID proyek tanpa commit dulu
        
        # 2. Jadikan pembuat sebagai LEADER
        membership = ProjectMember(
            user_id=leader_id,
            project_id=new_project.id,
            role=RoleEnum.LEADER
        )
        db.add(membership)
        
        # 3. Catat Log (Fase 1: Action: GROUP_CREATED)
        log = ActivityLog(
            action="GROUP_CREATED",
            details=f"Proyek {name} berhasil dibuat.",
            user_id=leader_id,
            project_id=new_project.id
        )
        db.add(log)
        
        await db.commit()
        await db.refresh(new_project)
        return new_project

    @staticmethod
    async def add_member(db: AsyncSession, project_id: uuid.UUID, username: str, role: RoleEnum, admin_id: uuid.UUID):
        # Cari user yang akan diundang
        stmt = select(User).where(User.username == username)
        result = await db.exec(stmt)
        user_to_add = result.first()
        
        if not user_to_add:
            raise HTTPException(status_code=404, detail="Mahasiswa tidak ditemukan")
            
        # Cek apakah sudah jadi member
        member_stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id, 
            ProjectMember.user_id == user_to_add.id
        )
        existing = await db.exec(member_stmt)
        if existing.first():
            raise HTTPException(status_code=400, detail="User sudah bergabung di proyek ini")

        new_member = ProjectMember(user_id=user_to_add.id, project_id=project_id, role=role)
        db.add(new_member)
        
        # Log Role Assignment
        log = ActivityLog(
            action="ROLE_ASSIGNED",
            details=f"User {username} ditugaskan sebagai {role}",
            user_id=admin_id,
            project_id=project_id
        )
        db.add(log)
        
        await db.commit()
        return {"message": f"Berhasil menambahkan {username} sebagai {role}"}