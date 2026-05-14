# Task Management & Audit System

REST API untuk manajemen proyek, parsing instruksi berbasis AI, audit evidence, appeal, dan laporan PDF.

## Daftar Isi

1. [Ringkasan](#ringkasan)
2. [Fitur Utama](#fitur-utama)
3. [Arsitektur](#arsitektur)
4. [ERD](#erd)
5. [Flowchart](#flowchart)
6. [Quick Start](#quick-start)
7. [Konfigurasi](#konfigurasi)
8. [API Utama](#api-utama)
9. [Testing](#testing)
10. [Catatan Implementasi](#catatan-implementasi)

## Ringkasan

Project ini dibangun dengan FastAPI dan SQLModel untuk mengelola proyek berbasis tim. Alur utamanya sekarang berpusat pada `Task` dan `SubTask`, dengan workflow audit AI, appeal manual oleh Leader/QC, serta audit trail lewat `ActivityLog`.

## Fitur Utama

- Autentikasi JWT dengan access token dan refresh token.
- RBAC untuk role `LEADER`, `ASSISTANT`, `QC`, dan `MEMBER`.
- Upload instruksi proyek dalam bentuk teks, PDF, DOCX, atau file lain yang didukung extractor.
- Parsing instruksi menjadi `Task` dan `SubTask` secara otomatis.
- Publish task, claim subtask, upload evidence, dan audit AI.
- Appeal workflow untuk hasil penolakan AI.
- Keputusan manual final oleh Leader atau QC.
- Generate laporan PDF proyek lengkap dengan ringkasan aktivitas.

## Arsitektur

- FastAPI sebagai web framework async.
- SQLModel dan SQLAlchemy sebagai ORM.
- PostgreSQL sebagai database.
- Google Generative AI untuk parsing instruksi dan audit.
- WeasyPrint untuk generate PDF report.

## ERD

```mermaid
erDiagram
    USER ||--o{ PROJECT_MEMBER : has_roles
    PROJECT ||--o{ PROJECT_MEMBER : has_members
    PROJECT ||--o{ TASK : contains
    TASK ||--o{ SUBTASK : contains
    USER ||--o{ SUBTASK : assigned_to
    USER ||--o{ SUBTASK : approves
    USER ||--o{ ACTIVITY_LOG : performs
    PROJECT ||--o{ ACTIVITY_LOG : scoped_by
    USER ||--o{ REFRESH_TOKEN : has

    USER {
        uuid id PK
        string username
        string password_hash
    }

    PROJECT {
        uuid id PK
        string name
        datetime created_at
    }

    PROJECT_MEMBER {
        uuid user_id PK, FK
        uuid project_id PK, FK
        string role "LEADER/ASSISTANT/QC/MEMBER"
    }

    TASK {
        uuid id PK
        uuid project_id FK
        string title
        text raw_content
        datetime deadline
        boolean is_published
    }

    SUBTASK {
        uuid id PK
        uuid task_id FK
        string title
        text description
        string status "TODO/IN_PROGRESS/PENDING_AI_REVIEW/REJECTED_BY_AI/APPEAL_PENDING/PENDING_HUMAN_QC/REJECTED_BY_HUMAN/DONE"
        uuid assigned_to_id FK
        text evidence_url
        text ai_rejection_reason
        text appeal_reason
        text human_rejection_reason
        uuid approved_by_id FK
    }

    ACTIVITY_LOG {
        uuid id PK
        string action
        text details
        datetime created_at
        uuid user_id FK
        uuid project_id FK
    }

    REFRESH_TOKEN {
        uuid id PK
        string token
        uuid user_id FK
        datetime created_at
        datetime expires_at
        boolean revoked
    }
```

## Flowchart

```mermaid
flowchart TD
    A[Register / Login] --> B[Create Project]
    B --> C[Invite Member / Set Role]
    C --> D[Upload Instruction]
    D --> E[AI Parse Instruction]
    E --> F[Create Task + SubTasks]
    F --> G[Publish Task]
    G --> H[Member Claim SubTask]
    H --> I[Submit Evidence]
    I --> J[AI Audit]
    J -->|Pass| K[Status: DONE]
    J -->|Fail| L[Status: REJECTED_BY_AI]
    L --> M[Member Appeal]
    M --> N[Leader / QC Review]
    N -->|Approve| K
    N -->|Reject| O[Back to TODO]
    O --> H
    K --> P[Activity Log + PDF Report]
```

## Quick Start

### Prasyarat

- Python 3.12+
- PostgreSQL 12+
- UV
- API key Google Generative AI

### Instalasi

```bash
git clone <repo-url>
cd task_management
uv sync
```

### Konfigurasi Environment

Buat file `.env` di root project.

```env
DATABASE_URL=postgresql+asyncpg://auditor_user:auditor_pass@localhost:5432/auditor_db
SECRET_KEY=your-very-secret-key-at-least-32-characters-long
GEMINI_API_KEY=your-google-ai-key
PROJECT_NAME=Task Management & Audit System
VERSION=0.1.0
```

### Jalankan Database

```bash
python run_migrations.py
```

### Jalankan Aplikasi

```bash
uv run uvicorn app.main:app --reload
```

Server tersedia di `http://localhost:8000`.

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Konfigurasi

Project memakai `SQLModel.metadata.create_all` saat startup, jadi skema mengikuti model yang ada di `app/models/domain.py`. Migration SQL yang ada saat ini menambahkan kolom `is_published` di `tasks` dan `human_rejection_reason` di `subtasks`.

## API Utama

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

### Projects

- `POST /api/v1/projects/`
- `POST /api/v1/projects/{project_id}/members`
- `PATCH /api/v1/projects/{project_id}/members/{user_id}/role`
- `GET /api/v1/projects/{project_id}/dashboard`
- `GET /api/v1/projects/{project_id}/kanban`

### Tasks

- `POST /api/v1/tasks/upload-instruction/{project_id}`
- `POST /api/v1/tasks/publish/{task_id}`
- `GET /api/v1/tasks/{task_id}`
- `PATCH /api/v1/tasks/subtasks/{subtask_id}/assign/{user_id}`
- `POST /api/v1/tasks/subtasks/{subtask_id}/claim`
- `POST /api/v1/tasks/subtasks/{subtask_id}/submit-and-audit`

### Appeals

- `PATCH /api/v1/appeals/{subtask_id}/appeal`
- `GET /api/v1/appeals/projects/{project_id}/queue`
- `PATCH /api/v1/appeals/{subtask_id}/leader-decision`

### Reports

- `GET /api/v1/reports/projects/{project_id}`

## Testing

```bash
uv run pytest
```

Jika ingin fokus ke integration test:

```bash
uv run pytest tests/integration
```

## Catatan Implementasi

- `Task` sekarang menyimpan instruksi mentah dan status publikasi, sedangkan pekerjaan operasional ada di `SubTask`.
- `ActivityLog` dipakai untuk audit trail dan report PDF.
- `RefreshToken` dipakai untuk refresh flow login/logout.
- Status workflow subtask mengikuti state machine yang lebih detail daripada versi lama.

#### Get Task Details

```bash
curl -X GET http://localhost:8000/api/v1/tasks/$TASK_ID \
  -H "Authorization: Bearer $TOKEN"

# Response (200):
# {
#   "id": "ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj",
#   "title": "Build Login Flow",
#   "deadline": "2026-05-20T23:59:59",
#   "project_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
#   "subtasks": [
#     {
#       "id": "11111111-2222-3333-4444-555555555555",
#       "title": "Design login page",
#       "description": "Buat form login dengan HTML/CSS",
#       "status": "TODO",
#       "assigned_to_id": null,
#       "evidence_url": null,
#       "ai_rejection_reason": null,
#       "appeal_reason": null,
#       "human_rejection_reason": null,
#       "approved_by_id": null
#     },
#     ...
#   ]
# }
```

#### Claim Subtask

```bash
SUBTASK_ID="11111111-2222-3333-4444-555555555555"

curl -X POST http://localhost:8000/api/v1/tasks/subtasks/$SUBTASK_ID/claim \
  -H "Authorization: Bearer $TOKEN"

# Response (200):
# {
#   "status": "success",
#   "message": "Tugas 'Design login page' berhasil di-claim"
# }
```

**RBAC:** MEMBER (member project)  
**Effect:** Status berubah TODO → IN_PROGRESS, assigned_to_id = current_user.id

#### Assign Subtask

```bash
TARGET_USER_ID="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

curl -X PATCH http://localhost:8000/api/v1/tasks/subtasks/$SUBTASK_ID/assign/$TARGET_USER_ID \
  -H "Authorization: Bearer $TOKEN"

# Response (200):
# {
#   "status": "success",
#   "message": "Tugas 'Design login page' sekarang di-assign ke User {TARGET_USER_ID}"
# }
```

**RBAC:** LEADER atau ASSISTANT

#### Submit Evidence & Trigger AI Audit

```bash
curl -X POST http://localhost:8000/api/v1/tasks/subtasks/$SUBTASK_ID/submit-and-audit \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@evidence.png"

# Response (200):
# {
#   "status": "PENDING_AI_REVIEW",
#   "message": "Bukti berhasil diunggah. AI sedang melakukan audit di background."
# }
```

**RBAC:** Member yang mengerjakan subtask  
**Effect:** 
- Status: IN_PROGRESS → PENDING_AI_REVIEW
- Evidence disimpan ke `/static/uploads/`
- Background task trigger Google Gemini untuk audit

**AI Audit Process (Background):**
```
Gemini.audit_evidence(description, image_bytes)
→ { is_valid: bool, confidence_score: 0-100, feedback: str }

Jika valid (is_valid=true):
  Status: DONE

Jika invalid (is_valid=false):
  Status: REJECTED_BY_AI
  ai_rejection_reason: feedback dari AI
```

---

### Appeals

#### File Appeal

```bash
curl -X PATCH http://localhost:8000/api/v1/appeals/$SUBTASK_ID/appeal \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "AI salah membaca bukti, saya sudah ikuti instruksi dengan benar"
  }'

# Response (200):
# {
#   "message": "Banding berhasil diajukan. Menunggu tinjauan manual Leader/QC.",
#   "status": "APPEAL_PENDING"
# }
```

**Precondition:** Subtask status = REJECTED_BY_AI  
**RBAC:** Member yang mengerjakan subtask

#### Get Appeal Queue

```bash
curl -X GET http://localhost:8000/api/v1/appeals/projects/$PROJECT_ID/queue \
  -H "Authorization: Bearer $TOKEN"

# Response (200):
# {
#   "project_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
#   "items": [
#     {
#       "id": "11111111-2222-3333-4444-555555555555",
#       "title": "Design login page",
#       "description": "Buat form login dengan HTML/CSS",
#       "evidence_url": "/static/uploads/evidence_xxx.png",
#       "ai_rejection_reason": "Bukti tidak cukup jelas, harus screenshot penuh",
#       "appeal_reason": "Screenshot sudah penuh, AI salah baca"
#     }
#   ]
# }
```

**RBAC:** LEADER atau QC

#### Leader Decision on Appeal

```bash
curl -X PATCH http://localhost:8000/api/v1/appeals/$SUBTASK_ID/leader-decision \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_approved": true
  }'

# Response (200):
# {
#   "message": "Keputusan berhasil disimpan. Status sekarang: DONE"
# }
```

**If Approve (`is_approved=true`):**
- Status: APPEAL_PENDING → DONE
- approved_by_id = current_user.id

**If Reject (`is_approved=false`):**
- Status: APPEAL_PENDING → TODO (retry dari awal)
- Wajib menyertakan `reason`
- human_rejection_reason = reason

```bash
# Contoh reject
curl -X PATCH http://localhost:8000/api/v1/appeals/$SUBTASK_ID/leader-decision \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "is_approved": false,
    "reason": "Bukti masih belum sesuai instruksi, ulang lagi dengan lebih teliti"
  }'
```

**RBAC:** LEADER atau QC

---

### Reports

#### Generate Project Report

```bash
curl -X GET http://localhost:8000/api/v1/reports/projects/$PROJECT_ID \
  -H "Authorization: Bearer $TOKEN" \
  --output project-report.pdf

# File akan tersimpan sebagai project-report.pdf
```

**RBAC:** LEADER only  
**Content:**
- Judul proyek & tanggal laporan
- Statistik: total task, completed, failed, under review
- Daftar semua subtask dengan status, evidence, dan feedback
- Audit trail aktivitas
- Grafik progress

---

## 🔐 RBAC (Role-Based Access Control)

| Role | Permission | Contoh Aksi |
|------|-----------|-----------|
| **LEADER** | Full control proyek | Create project, add member, publish task, approve appeal, generate report |
| **ASSISTANT** | Manage task | Upload instruksi, publish task, assign subtask |
| **QC** | Review & approve | Access appeal queue, give decision on appeal |
| **MEMBER** | Execute task | Claim subtask, submit evidence, file appeal |

### Default Authorization

| Endpoint | GET | POST | PATCH | DELETE | Min Role |
|----------|-----|------|-------|--------|----------|
| `/projects` | ✓ | ✓ | - | - | MEMBER |
| `/projects/{id}/members` | - | ✓ | ✓ | - | LEADER |
| `/projects/{id}/dashboard` | ✓ | - | - | - | LEADER |
| `/tasks/upload-instruction` | - | ✓ | - | - | LEADER/ASSISTANT |
| `/tasks/publish` | - | ✓ | - | - | LEADER/ASSISTANT |
| `/tasks/subtasks/claim` | - | ✓ | - | - | MEMBER |
| `/tasks/subtasks/submit-and-audit` | - | ✓ | - | - | MEMBER (assigned) |
| `/appeals/appeal` | - | - | ✓ | - | MEMBER (assigned) |
| `/appeals/queue` | ✓ | - | - | - | LEADER/QC |
| `/appeals/leader-decision` | - | - | ✓ | - | LEADER/QC |
| `/reports/projects/{id}` | ✓ | - | - | - | LEADER |

---

## 🔄 Workflow & Use Cases

### Use Case 1: Complete Task Flow

```
1. LEADER membuat project
   → POST /projects

2. LEADER invite MEMBER ke project
   → POST /projects/{id}/members

3. LEADER/ASSISTANT upload instruksi (PDF/DOCX)
   → POST /tasks/upload-instruction/{project_id}
   → AI auto-parse menjadi subtask

4. LEADER publish task
   → POST /tasks/publish/{task_id}

5. MEMBER claim subtask
   → POST /tasks/subtasks/{id}/claim
   → Status: TODO → IN_PROGRESS

6. MEMBER submit evidence (screenshot/file)
   → POST /tasks/subtasks/{id}/submit-and-audit
   → Status: IN_PROGRESS → PENDING_AI_REVIEW

7. AI audit evidence (background)
   → AI valid? → Status: DONE
   → AI invalid? → Status: REJECTED_BY_AI + feedback

8. (If rejected) MEMBER file appeal
   → PATCH /appeals/{id}/appeal
   → Status: REJECTED_BY_AI → APPEAL_PENDING

9. LEADER review appeal & decide
   → PATCH /appeals/{id}/leader-decision
   → is_approved=true → Status: DONE
   → is_approved=false → Status: TODO (retry)

10. LEADER generate report
    → GET /reports/projects/{id}
    → Download PDF dengan statistik & audit trail
```

### Use Case 2: Group Task Assignment

```
1. LEADER/ASSISTANT upload instruksi dengan banyak subtask
   → AI extract 10+ subtask dari instruksi

2. LEADER/ASSISTANT assign masing-masing subtask ke MEMBER berbeda
   → PATCH /tasks/subtasks/{id}/assign/{user_id}

3. Semua MEMBER bekerja parallel, submit evidence satu-satu
   → MEMBER A, B, C submit bukti
   → AI audit setiap evidence independen

4. LEADER monitor progress di dashboard
   → GET /projects/{id}/dashboard
   → Lihat statistik real-time

5. LEADER approve yang sesuai, tolak yang perlu retry
   → PATCH /appeals/{id}/leader-decision
```

### Use Case 3: Manual QC Process

```
1. QC role di-assign ke MEMBER tertentu
   → POST /projects/{id}/members
   → role=QC

2. QC check appeal queue
   → GET /appeals/projects/{id}/queue

3. QC review bukti & alasan appeal, diskusi dengan member
   → (Review via evidence_url)

4. QC approve atau reject appeal
   → PATCH /appeals/{id}/leader-decision
   → is_approved=true/false
```

---

## 🧪 Testing

### Run Unit Tests

```bash
# Semua unit test
uv run pytest tests/test_unit.py -v

# Test spesifik
uv run pytest tests/test_unit.py::TestAuth -v
```

### Run Integration Tests

```bash
# Semua integration test
uv run pytest tests/integration/ -v

# Test spesifik flow
uv run pytest tests/integration/test_appeal_flow.py -v
```

### Test Coverage

```bash
# Generate coverage report
uv run pytest --cov=app tests/

# HTML report
uv run pytest --cov=app --cov-report=html tests/
# Open: htmlcov/index.html
```

### Sample Test: Appeal Flow

```python
# tests/integration/test_appeal_flow.py

async def test_full_appeal_flow(client: AsyncClient):
    """
    1. Register leader & member
    2. Create project
    3. Upload instruksi → AI parse subtask
    4. Publish task
    5. Member claim & submit evidence
    6. AI audit (reject)
    7. Member appeal
    8. Leader approve appeal
    9. Verify subtask status = DONE
    10. Generate report (PDF)
    """
    # ... (lihat file test untuk detail implementasi)
```

---

## 🔍 Troubleshooting

### Issue: Database Connection Error

**Error:**
```
FATAL ERROR: DATABASE_URL tidak ditemukan di file .env!
```

**Solution:**
```bash
# 1. Buat .env file
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/auditor_db
SECRET_KEY=your-secret-key
GEMINI_API_KEY=your-gemini-key
EOF

# 2. Test koneksi
python -c "import asyncio; from app.core.database import engine; asyncio.run(engine.connect())"
```

### Issue: PostgreSQL Not Running

**Error:**
```
sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL
```

**Solution:**
```bash
# Cek PostgreSQL status
sudo systemctl status postgresql

# Start PostgreSQL jika belum jalan
sudo systemctl start postgresql

# Atau dengan Docker
docker run --name postgres \
  -e POSTGRES_USER=auditor_user \
  -e POSTGRES_PASSWORD=auditor_pass \
  -e POSTGRES_DB=auditor_db \
  -p 5432:5432 \
  -d postgres:15
```

### Issue: API Key Google Gemini Invalid

**Error:**
```
google.generativeai.types.APIError: Invalid API key
```

**Solution:**
```bash
# 1. Dapatkan API key dari https://ai.google.dev/
# 2. Update di .env
GEMINI_API_KEY=AIzaSyD...your_key...

# 3. Restart server
uv run uvicorn app.main:app --reload
```

### Issue: JWT Token Expired

**Error:**
```json
{
  "detail": "Token tidak valid atau sudah kedaluwarsa"
}
```

**Solution:**
```bash
# Login ulang untuk mendapatkan token baru
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=user&password=pass"
```

**Note:** Token berlaku 7 hari. Untuk implementasi lebih lanjut, bisa tambahkan refresh token endpoint.

### Issue: Upload File Rejected

**Error:**
```
Bukti harus berupa gambar (PNG/JPG)
```

**Solution:**
```bash
# Pastikan upload file dengan format PNG atau JPG
curl -X POST http://localhost:8000/api/v1/tasks/subtasks/$SUBTASK_ID/submit-and-audit \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@screenshot.png"  # ✓ PNG
  # -F "file=@document.pdf"  # ✗ PDF tidak support
```

### Issue: Permission Denied on Endpoint

**Error:**
```json
{
  "detail": "Anda bukan anggota proyek ini."
}
```

**Solution:**
1. Pastikan user sudah invite ke project
2. Cek role user, apakah sesuai permission endpoint
3. Gunakan Bearer token dari user yang tepat

```bash
# Debug: Check current user
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Issue: AI Audit Background Task Not Running

**Error:**
```
Evidence uploaded tapi status tidak berubah ke DONE/REJECTED_BY_AI
```

**Solution:**
```bash
# Cek server logs untuk error
# (Background tasks di console saat development)

# Pastikan GEMINI_API_KEY valid
# Pastikan image file valid dan bisa dibaca

# Restart server
uv run uvicorn app.main:app --reload
```

---

## 📞 Support & Contributing

### Project Structure

```
task_management/
├── app/
│   ├── api/
│   │   ├── v1/           # API routes (auth, projects, tasks, appeals, reports)
│   │   └── deps.py       # Dependency injection & RBAC
│   ├── core/
│   │   ├── config.py     # Settings & environment
│   │   ├── database.py   # SQLModel setup
│   │   └── security.py   # JWT & password hashing
│   ├── models/
│   │   └── domain.py     # Database models & enums
│   ├── schemas/          # Pydantic schemas (request/response)
│   ├── services/         # Business logic (auth, task, AI, report)
│   ├── static/uploads/   # Evidence & file uploads
│   ├── utils/            # Helper functions (logger, etc)
│   └── main.py           # FastAPI app entry point
├── migrations/           # SQL migration files
├── tests/                # Unit & integration tests
├── pyproject.toml        # Project metadata & dependencies
├── pytest.ini            # Pytest configuration
├── run_migrations.py     # Migration runner script
└── README.md             # This file
```

### Adding New Feature

1. **Tambah model** di `app/models/domain.py`
2. **Tambah schema** di `app/schemas/`
3. **Tambah service logic** di `app/services/`
4. **Tambah route** di `app/api/v1/`
5. **Test** di `tests/integration/`
6. **Update** dokumentasi di README ini

### Running Tests Locally

```bash
# Semua test
uv run pytest -v

# Dengan coverage
uv run pytest --cov=app -v

# Debug mode
uv run pytest -vv -s
```

---

## 📄 License

© 2026 The Auditor's Command Center. All rights reserved.

---

**Last Updated:** May 11, 2026  
**Version:** 0.1.0
