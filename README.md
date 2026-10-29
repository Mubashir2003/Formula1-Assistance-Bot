# Apex F1 Chatbot

A streaming Formula 1 chatbot built with FastAPI, Groq, HTML, CSS, and JavaScript. This first version uses a system prompt and the model's learned knowledge. It does not use RAG, a historical database, or live race data.

## Requirements

- Python 3.10+
- A Groq API key from https://console.groq.com/keys
- Internet connection for Groq API requests

## Setup

### 1. Open the project folder

```bash
cd f1-chatbot
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:

```bat
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure the API key

Copy `.env.example` to `.env`.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Windows Command Prompt:

```bat
copy .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Open `.env` and replace `replace_with_your_groq_api_key` with your own key. Never paste the key into HTML/JavaScript or commit `.env` to GitHub.

The default model is configured in `.env` as `llama-3.3-70b-versatile`. If this model is not available to your account, change `GROQ_MODEL` to a currently supported chat model listed in Groq's model documentation: https://console.groq.com/docs/models

### 5. Run the server

From the project root:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 in your browser.

API health check: http://127.0.0.1:8000/health  
Interactive API docs: http://127.0.0.1:8000/docs

Stop the server with `Ctrl+C`.

## How streaming works

The browser sends recent conversation messages to `POST /chat`. FastAPI calls Groq with `stream=True` and forwards text chunks using Server-Sent Events (SSE). JavaScript reads the stream and updates the assistant's message as tokens arrive.

## Security and limitations

- The Groq API key stays server-side in `.env`.
- `.gitignore` excludes `.env`; keep it that way.
- This is a local development starter. Before public deployment, add rate limiting, request timeouts, authentication if needed, and suitable abuse/cost controls.
- Conversation history is held in the browser and sent with each request; it is not saved to a database.
- The model can make mistakes. This version does not verify statistics or access live F1 data.
- The frontend escapes model output before applying basic Markdown formatting.
- Check current Groq model availability and API limits before deployment.

## Project structure

```text
f1-chatbot/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── groq_service.py
│   └── prompts.py
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```
