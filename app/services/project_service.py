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

    @staticmethod
    async def update_member_role(
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        role: RoleEnum,
        admin_id: uuid.UUID,
    ):
        if role == RoleEnum.LEADER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role LEADER hanya bisa diberikan saat membuat project")

        membership_stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        membership_result = await db.exec(membership_stmt)
        project_member = membership_result.first()

        if not project_member:
            raise HTTPException(status_code=404, detail="Member tidak ditemukan di project ini")

        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.exec(user_stmt)
        target_user = user_result.first()

        if not target_user:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")

        previous_role = project_member.role
        project_member.role = role

        log = ActivityLog(
            action="ROLE_UPDATED",
            details=f"User {target_user.username} diubah dari {previous_role} ke {role}",
            user_id=admin_id,
            project_id=project_id,
        )
        db.add(project_member)
        db.add(log)

        await db.commit()
        return {
            "message": f"Role {target_user.username} berhasil diubah menjadi {role}",
            "user_id": user_id,
            "role": role,
        }