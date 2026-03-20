# AI Agentic Office

แพลตฟอร์มทำงานร่วมกันหลายเอเจนต์แบบ “ออฟฟิศเสมือน” — รันเวิร์กโฟลว์ด้วย **LangGraph** บน **FastAPI** แดชบอร์ด **Next.js** และหน่วยความจำ/RAG บน **PostgreSQL + pgvector** พร้อมแซนด์บ็อกซ์ **E2B** สำหรับ Developer

**เอกสารเชิงลึก**

- [backend/README.md](backend/README.md) — สถาปัตยกรรม API, กราฟ, ตาราง route, โมดูล, Mermaid
- [frontend/README.md](frontend/README.md) — App Router, hooks/context, WebSocket, Mermaid

---

## 1. วิธีการเริ่มต้นโปรเจกต์

### Prerequisites

- **Node.js** 18+
- **Python** 3.10+
- **Docker** (สำหรับ PostgreSQL และ Redis ตาม `docker-compose.yml`)

### ขั้นตอน

1. ที่รากโปรเจกต์: `docker compose up -d` — ขึ้น **PostgreSQL (pgvector)** และ **Redis**
2. **Backend** (`backend/`):

   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Frontend** (`frontend/`):

   ```bash
   cd frontend
   npm install
   cp .env.example .env.local
   npm run dev
   ```

### URL ที่ใช้บ่อย

| บริการ | URL |
|--------|-----|
| แอป Next.js | [http://localhost:3000](http://localhost:3000) |
| Swagger / OpenAPI | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Health | `GET` [http://localhost:8000/health](http://localhost:8000/health) |

ถ้า `pip` ขึ้น `bad interpreter` เกี่ยวกับ Python เวอร์ชัน — ลบ `backend/.venv` แล้วสร้าง venv ใหม่

---

## 2. ระบบนี้คืออะไร (คร่าวๆ)

ระบบจำลอง “ออฟฟิศ” ที่เอเจนต์ทำงานเป็นขั้น **Research → Developer → Writer → QA** บนกราฟ LangGraph ที่ compile พร้อม **in-memory checkpointer** และจุด **interrupt** ก่อนการตัดสินใจของผู้ใช้เมื่อเข้าโหมด escalation

- **LLM:** Google Gemini (ผ่าน `langchain-google-genai`) เมื่อตั้ง `GOOGLE_API_KEY`
- **หน่วยความจำ / RAG:** ค้นคว้าและ ingest ตาม `memory_service.py` และ `RAG_ENABLED` / embedding ใน `.env`
- **Developer:** ใช้แซนด์บ็อกซ์ E2B เมื่อมี `E2B_API_KEY`
- **สตรีม:** เหตุการณ์จากกราฟถูกส่งออกทาง **WebSocket** `/ws/agent-thoughts` เพื่อแสดงความคิดและสถานะบนแดชบอร์ด

---

## 3. มี agent อะไรบ้าง (ตามโค้ดปัจจุบัน)

บทบาทที่แสดงใน UI / สตรีม (`pm`, `researcher`, `developer`, `writer`, `qa`) สอดคล้องกับโหนดและการแมปใน `agents/streaming_manager.py`:

| บทบาท | บทบาทในระบบ |
|--------|----------------|
| **PM** | ความคิด/สถานะระดับผู้จัดการ (เช่น ข้อความ scope ใน research; โหนด escalation แมปมาที่ `pm` ในสตรีม) — ไม่มีโหนดแยกชื่อ `pm` ในกราฟ |
| **Researcher** | โหนด `research` — ค้นหาหน่วยความจำภายใน, ข้อเท็จจริงเสริม, สังเคราะห์โน้ต |
| **Developer** | โหนด `developer` — ReAct + เครื่องมือ E2B (Python/sandbox) |
| **Writer** | โหนด `writer` — ร่าง deliverable Markdown และบันทึกไฟล์ |
| **QA** | โหนด `qa` — รีวิวร่าง; ตรวจจับลูปซ้ำ (semantic similarity) แล้วอาจส่งต่อ escalation |
| **Office Manager (Escalation)** | โหนด `escalation` + `await_user_decision` — สรุปสถานการณ์และตัวเลือก; หยุดรอ `POST /api/graph/resume` |

---

## 4. การทำงานของ agent

1. **คอมไพล์กราฟ** (`build_research_writer_graph`): เส้นทางหลัก `research` → `developer` → `writer` → `qa` → `END` หรือแยกไป `escalation` ตามเงื่อนไข
2. **Loop guard:** ถ้า `loop_counter` สูงเกินเกณฑ์ใน `should_continue` จะไป `escalation` แทนการไปขั้นถัดไป
3. **QA stagnant:** ถ้า feedback ใกล้เคียงรอบก่อนเกินเกณฑ์ → ไป `escalation`
4. **Escalation:** หลัง `escalation` กราฟ **interrupt ก่อน** `await_user_decision` — ไคลเอนต์ส่ง `POST /api/graph/resume` พร้อม `thread_id` และ `choice` (`force_approve` | `change_instructions` | `terminate`)
5. **สตรีม:** `StreamingManager` ใช้ `astream_events` จาก LangGraph แล้ว broadcast JSON ไปยัง WebSocket; `emit_thought` ในโหนดส่งข้อความความคิดของแต่ละบทบาท

รายละเอียดเส้นทาง, API และ **ทำไมถึงใช้ LangGraph / ได้ประโยชน์อะไรในระบบนี้**: [backend/README.md](backend/README.md) (หัวข้อ *LangGraph ทำงานอย่างไร และมีประโยชน์ยังไงในระบบนี้*)

---

## 5. การใช้งานระบบ + ตัวอย่างเคส

### แดชบอร์ด

1. เปิด [http://localhost:3000](http://localhost:3000)
2. ใส่หัวข้อ (topic) แล้วรัน — ส่งไปที่ `POST /api/graph/run`
3. ดู log/ความคิดผ่านการเชื่อม **WebSocket** `ws://localhost:8000/ws/agent-thoughts` (หรือ `NEXT_PUBLIC_WS_URL` + path เดียวกัน) — hook หลักคือ `useAgentLog` ใน [frontend/README.md](frontend/README.md)
4. ถ้าเข้า escalation — UI ใช้ **`ManagerInterventionPanel`** เลือกตัวเลือกและส่ง `POST /api/graph/resume`

### ตัวอย่าง `curl` / JSON

**เริ่มรันกราฟ**

```bash
curl -s -X POST http://localhost:8000/api/graph/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "รีวิวกลยุทธ์ตลาด Q2", "human_feedback": "เน้นตลาด SEA"}'
```

**ดำเนินการหลัง escalation** (ได้ `thread_id` จาก response ของ backend/UI)

```bash
curl -s -X POST http://localhost:8000/api/graph/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "<uuid-from-run>", "choice": "change_instructions", "new_instructions": "ลดความยาวเหลือ 1 หน้า"}'
```

**รายการผลลัพธ์ที่เก็บใน DB**

```bash
curl -s http://localhost:8000/api/outputs
```

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy async URL เชื่อม PostgreSQL |
| `REDIS_URL` | Redis จาก Docker; ค่าอยู่ใน settings (`core/config.py`) |
| `CORS_ORIGINS` | คั่นด้วย comma เช่น `http://localhost:3000` |
| `VECTOR_DIMENSION` | ขนาด embedding (ต้องสอดคล้องกับโมเดล) |
| `RAG_ENABLED` | เปิด/ปิด path RAG ในหน่วยความจำ |
| `EMBEDDING_MODEL` | โมเดล embedding Gemini |
| `E2B_API_KEY` | แซนด์บ็อกซ์สำหรับ Developer |
| `GOOGLE_API_KEY` | Gemini — Researcher, Writer, QA, Developer, escalation |
| `GEMINI_MODEL` | รหัสโมเดลแชท เช่น `gemini-2.5-pro` |
| `STORAGE_ROOT` | โฟลเดอร์เก็บไฟล์ output (สัมพัทธ์จาก `backend/` ถ้าไม่ใช่ absolute) |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend base URL (ค่าเริ่ม `http://localhost:8000`) |
| `NEXT_PUBLIC_WS_URL` | WebSocket base (ค่าเริ่ม `ws://localhost:8000`) |

---

## Project layout

```
├── backend/              # FastAPI, LangGraph — ดู backend/README.md
│   ├── api/              # REST + WebSocket
│   ├── agents/           # กราฟ, โหนด, สตรีม
│   ├── core/             # Settings
│   ├── db/               # SQLAlchemy, schema
│   ├── integrations/     # E2B, vector, supplemental research
│   └── storage/          # writer outputs บนดิสก์
├── frontend/             # Next.js — ดู frontend/README.md
├── docker-compose.yml    # PostgreSQL + Redis
└── README.md
```

---

## Development workflow

1. `docker compose up -d`
2. Terminal A: `cd backend && source .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000`
3. Terminal B: `cd frontend && npm run dev`

## Troubleshooting

- **Frontend ไม่ต่อ WebSocket:** ตรวจว่า backend รันที่พอร์ต 8000 และ `CORS_ORIGINS` รวม `http://localhost:3000`
- **ฐานข้อมูลเชื่อมไม่ได้:** ตรวจ `docker compose ps` และให้ `DATABASE_URL` ตรงกับ user/password/db ใน `docker-compose.yml`
- **Postgres volume เดิมไม่เข้ากันกับ image:** สำรองข้อมูลก่อน; ใน dev อาจใช้ `docker compose down -v` (ลบข้อมูลใน volume)
- **Build frontend:** `cd frontend && npm run build`

## License

MIT (ปรับตามต้องการ)
