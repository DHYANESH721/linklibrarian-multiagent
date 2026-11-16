# LinkLibrarian — a multi-agent AI bookmark manager

Paste a URL. A team of **six AI agents** fetches the page, reads it, writes a summary,
chooses tags and a category, checks the quality of the result, and files it as a card
in your catalog.

**Stack:** Python · Flask · SQLite · SQLAlchemy · BeautifulSoup4 · Requests · Groq (Llama 3.3 70B) · vanilla JS/CSS

---

## The agent team

Every agent lives in its own file inside `agents/` and inherits from `BaseAgent`.

| # | Agent | File | Its job |
|---|---|---|---|
| 1 | **Librarian Agent** (manager) | `agents/librarian_agent.py` | Gives work to the other agents, collects results, sends poor work back, saves the card |
| 2 | **Scout Agent** | `agents/scout_agent.py` | Fetches the page and decides: **readable**, **blocked**, or **retry** |
| 3 | **Reader Agent** | `agents/reader_agent.py` | Pulls out the title, description, favicon and clean main text (also reads hidden paper metadata on sites like IEEE) |
| 4 | **Summariser Agent** | `agents/summariser_agent.py` | Asks the AI for a 2–3 sentence summary (rewrites it if rejected) |
| 5 | **Tagger Agent** | `agents/tagger_agent.py` | Asks the AI for 3–6 tags and a category (48 built-in, or a new one when nothing fits) |
| 6 | **Quality Checker Agent** | `agents/quality_agent.py` | Approves the card, or rejects it with feedback so it gets redone |

Supporting files (not agents):

- `agents/base_agent.py` — the parent class: name, role, `run(task)`, logging, trace
- `agents/llm_client.py` — the **AI tool** (Groq API) used by the Summariser and Tagger

### How the agents work together

```
User pastes link
      │
      ▼
Librarian Agent ── valid URL? already saved? ──► (duplicate → stop)
      │
      ▼
Scout Agent ──── blocked site? ──► ⛔ stop with explanation
      │          slow / HTTP 5xx? ──► ↻ retry once
      ▼
Reader Agent ─── no readable text? ──► stop with explanation
      │
      ▼
Summariser Agent  ──►  Tagger Agent
      ▲                     │
      │                     ▼
      └── "redo" ◄── Quality Checker Agent ── approved ──► Librarian saves the card
         (max 2 times)
```

The agents share one `task` dictionary (a "blackboard"). Each agent reads what it needs,
adds its result, and records a line in `task["trace"]`. You can watch them work:

- **Terminal:** every agent prints what it decided, e.g. `[Scout Agent] READABLE — HTTP 200`
- **Website:** the loading bar steps through each agent; after saving, the status line says
  how many agents worked and whether the Quality Checker asked for a redo
- **API:** `POST /api/links` returns an `agents` list; `GET /api/health` lists the whole team

---

## Categories (automatic)

The Tagger Agent files every link under ONE category, chosen in this order:

1. **Reuse** a category already in your library (keeps the sidebar tidy)
2. Pick the most specific of **48 built-in categories**
3. If nothing fits, the AI **creates a new short category** (e.g. "Astrology", "Martial Arts");
   the Tagger and Quality Checker make sure the name is clean (1–3 words, no junk like "misc")

Built-in categories:

| Group | Categories |
|---|---|
| Technology | AI & Machine Learning · Programming · Web Development · Data Science · Cybersecurity · Technology · Engineering |
| Science | Science · Space & Astronomy · Mathematics · Agriculture · Environment · Energy · History |
| Health & life | Health & Medicine · Fitness · Mental Health · Food & Cooking · Parenting & Family · Pets & Animals · Home & Garden · Fashion & Beauty · Lifestyle |
| Learning & work | Education · Careers & Jobs · Business · Marketing · Finance · Cryptocurrency · Real Estate · Productivity |
| Society | News · Politics & Government · Law & Legal · Religion & Spirituality · Social Media |
| Leisure | Sports · Automotive · Travel · Movies & TV · Music · Gaming · Books & Literature · Art & Photography · Design · Entertainment · Shopping & Deals |
| Fallback | Other |

Add more by editing `CATEGORY_GUIDE` in `agents/tagger_agent.py` (name → description + keywords).
Without an API key the agent uses weighted keyword scoring over the built-in list instead, which
is less accurate — add `GROQ_API_KEY` to `.env` for the best results.

## Features

| Feature | Notes |
|---|---|
| Add URL | Validation, normalization, tracking-parameter stripping |
| Multi-agent processing | Scout → Reader → Summariser → Tagger → Quality Checker, run by the Librarian |
| Quality control | Poor summaries / tags are sent back for a redo (max 2) |
| Blocked-site detection | Amazon, Flipkart, RedBus, Swiggy, Instagram… refused with a clear message |
| Automatic retry | Temporary errors (timeout, HTTP 429/5xx) are retried once |
| Duplicate detection | Unique URL, HTTP 409 with the existing card |
| Search · category filter · tag filter | Same as before |
| Edit · delete · re-read | Re-read sends the link through the whole agent team again |
| Offline fallback | Without an API key the agents use keyword rules, so links still save |

---

## Run it in VS Code (Windows)

Open the `linklibrarian` folder in VS Code, open a terminal (**Ctrl + `**) and run:

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process RemoteSigned
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and paste your free Groq key (https://console.groq.com/keys):

```env
GROQ_API_KEY=gsk_your_real_key
```

Save (**Ctrl + S**), then start the app:

```powershell
python app.py
```

Open **http://127.0.0.1:5000** — the terminal shows the six agents on duty.
Check **http://127.0.0.1:5000/api/health** → `"ai_enabled": true` and the agent list.

Next time you only need:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
venv\Scripts\activate
python app.py
```

macOS / Linux: use `python3 -m venv venv`, `source venv/bin/activate`, `cp .env.example .env`.

---

## Folder structure

```
linklibrarian/
├── app.py                  # Flask app factory, prints the agent team at start-up
├── config.py               # Settings from .env
├── database.py             # SQLAlchemy instance
├── models.py               # Link table
├── routes.py               # Web pages + JSON API
├── agents/                 # ★ THE AGENT TEAM
│   ├── base_agent.py
│   ├── librarian_agent.py
│   ├── scout_agent.py
│   ├── reader_agent.py
│   ├── summariser_agent.py
│   ├── tagger_agent.py
│   ├── quality_agent.py
│   └── llm_client.py       # Groq AI tool used by Summariser + Tagger
├── services/link_service.py  # search, edit, delete; hands saving to the Librarian
├── utils/                  # URL validation, JSON helpers
├── templates/              # HTML pages
├── static/                 # CSS + JS
├── docs/architecture_diagram.png
├── requirements.txt
├── render.yaml · .python-version   # for deploying on Render
└── .env.example
```

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/links` | Save a URL (`{"url": "..."}`) — response includes the `agents` trace |
| `GET` | `/api/links` | List with `?q=&category=&tag=&sort=` |
| `GET` | `/api/links/<id>` | One link |
| `PUT` | `/api/links/<id>` | Edit fields |
| `DELETE` | `/api/links/<id>` | Delete |
| `POST` | `/api/links/<id>/refresh` | Re-read with the agent team |
| `GET` | `/api/categories` · `/api/tags` | Filters |
| `GET` | `/api/health` | Status, AI key check, and the list of agents |

Errors: `400` invalid input · `404` not found · `409` duplicate · `422` an agent could not read the page (the response says which agent).

---

## Deploy on Render

`render.yaml` is included. In the Render dashboard add the environment variable
`GROQ_API_KEY`. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`.

---

## Troubleshooting

- **`No module named flask_sqlalchemy`** — the virtual environment is not active or the
  requirements are not installed. Run `venv\Scripts\activate` then `pip install -r requirements.txt`.
- **"Offline mode" banner / wrong categories** — `.env` is missing, in the wrong folder, or has no key.
  It must sit next to `app.py` and contain `GROQ_API_KEY=gsk_...`. Restart after editing, then
  click **Re-read** on old cards to re-categorise them.
- **"This site blocks automated readers"** — the Scout Agent refused a known blocked site; save a different page.
- **"No readable text found"** — the page is built entirely with JavaScript.
- **Reset the library** — stop the server and delete `linklibrarian.db` (or the `instance/` folder).
