# AI Agentic Office

แพลตฟอร์มทำงานร่วมกันหลายเอเจนต์แบบ “ออฟฟิศเสมือน” — มีบทบาท PM, Researcher, Dev, QA ผ่าน **LangGraph** แดชบอร์ดลากจัดวางได้ (Next.js) และ API ด้วย **FastAPI**

**Quick links (English below):** โครงสร้างโฟลเดอร์ → [Project layout](#project-layout) · ตัวแปรสภาพแวดล้อม → [Environment variables](#environment-variables)

---

## เริ่มต้นโปรเจกต์ (สรุป)

1. ติดตั้ง [Prerequisites](#prerequisites)
2. ที่รากโปรเจกต์: `docker compose up -d` (PostgreSQL + Redis)
3. เปิดเทอร์มินัล 1 — backend: สร้าง venv, `pip install -r requirements.txt`, คัดลอก `backend/.env.example` → `.env`, รัน `uvicorn main:app --reload`
4. เปิดเทอร์มินัล 2 — frontend: `npm install` ใน `frontend/`, (ทางเลือก) คัดลอก `frontend/.env.example` → `.env.local`, รัน `npm run dev`
5. เปิดเบราว์เซอร์: [http://localhost:3000](http://localhost:3000) · API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Prerequisites

- **Node.js** 18+
- **Python** 3.10+
- **Docker** (สำหรับ PostgreSQL และ Redis)

## Quick start

### 1. Infrastructure

```bash
docker compose up -d
```

รอจน Postgres และ Redis พร้อม (`docker compose ps`)

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # แก้ค่าตามต้องการ
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health:** `GET http://localhost:8000/health`
- **รันกราฟตัวอย่าง:** `POST http://localhost:8000/api/graph/run` (body JSON: `{"topic": "ข้อความหัวข้อ"}`)
- **WebSocket ความคิดเอเจนต์:** `ws://localhost:8000/ws/agent-thoughts`

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # ทางเลือก: กำหนด NEXT_PUBLIC_WS_URL / NEXT_PUBLIC_API_URL
npm run dev
```

- **แอป:** [http://localhost:3000](http://localhost:3000)

## Environment variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy URL, e.g. `postgresql+asyncpg://agentic:agentic@localhost:5432/agentic_office` |
| `REDIS_URL` | `redis://localhost:6379/0` (checkpointing / caching) |
| `CORS_ORIGINS` | Comma-separated origins, e.g. `http://localhost:3000` |
| `PINECONE_API_KEY` | Optional; RAG vector store |
| `PINECONE_INDEX` | Optional; Pinecone index name |
| `E2B_API_KEY` | Optional; code sandboxing |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend base URL, default `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL` | WebSocket base, default `ws://localhost:8000` |

## Project layout

```
├── backend/              # FastAPI, LangGraph agents, WebSocket
│   ├── api/              # REST + WebSocket routes
│   ├── agents/           # OfficeState, StateGraph, nodes
│   ├── core/             # Settings
│   ├── db/               # SQLAlchemy async session
│   └── integrations/   # Pinecone / E2B stubs
├── frontend/             # Next.js 14+ App Router dashboard
├── docker-compose.yml
└── README.md
```

## Development workflow

1. `docker compose up -d`
2. Terminal A: `cd backend && source .venv/bin/activate && uvicorn main:app --reload`
3. Terminal B: `cd frontend && npm run dev`

## Troubleshooting

- **Frontend ไม่ต่อ WebSocket:** ตรวจว่า backend รันที่พอร์ต 8000 และ `CORS_ORIGINS` รวม `http://localhost:3000`
- **ฐานข้อมูลเชื่อมไม่ได้:** ตรวจ `docker compose ps` และให้ `DATABASE_URL` ตรงกับ user/password/db ใน `docker-compose.yml`
- **Build frontend:** `cd frontend && npm run build`

## License

MIT (ปรับตามต้องการ)
