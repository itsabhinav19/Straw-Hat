# 🐛 BugPredictor — Backend

AI-powered code bug prediction. Combines **AST static analysis** with **Claude AI** to generate a risk score and actionable suggestions.

---

## 🗂️ Project Structure

```
bugpredictor/
├── app.py            # Flask API server
├── analyzer.py       # Static analysis (AST + regex)
├── ai_engine.py      # Anthropic Claude AI integration
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚡ Setup (2 minutes)

### 1. Clone & install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your API key
```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

Or export directly:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run the server
```bash
python app.py
```
Server starts at `http://localhost:5000`

---

## 🔌 API Reference

### `GET /`
Health check.

**Response:**
```json
{ "status": "ok", "service": "BugPredictor API" }
```

---

### `POST /analyze`
Analyze code for bugs.

**Request body:**
```json
{
  "code": "def foo(x=[]):\n    x.append(1)\n    return x",
  "language": "python"
}
```

| Field      | Type   | Required | Default    |
|------------|--------|----------|------------|
| `code`     | string | ✅ yes   | —          |
| `language` | string | ❌ no    | `"python"` |

Supported languages: `python`, `javascript`, `typescript`, `java`, `go`, `rust`, `cpp`, `c`

**Response:**
```json
{
  "risk_score": 42,
  "risk_level": "MEDIUM",
  "summary": "Risk level: MEDIUM (42/100). Found 2 static issue(s). Logic bug in loop...",
  "static_issues": [
    {
      "line": 1,
      "column": 0,
      "severity": "warning",
      "code": "BP002",
      "message": "Mutable default argument in 'foo'",
      "suggestion": "Use None as default and initialise inside the function."
    }
  ],
  "ai_analysis": {
    "ai_risk_score": 18,
    "summary": "One mutable default bug; logic is otherwise sound.",
    "bugs": [...],
    "security_issues": [...],
    "code_smells": [...],
    "positive_notes": [...]
  }
}
```

**Risk levels:**

| Score   | Level    |
|---------|----------|
| 0–14    | `CLEAN`  |
| 15–39   | `LOW`    |
| 40–69   | `MEDIUM` |
| 70–100  | `HIGH`   |

---

## 🧠 How It Works

```
Code Input
    │
    ▼
┌─────────────────────┐
│  Static Analyzer    │  AST parsing + regex rules
│  (analyzer.py)      │  → Detects ~10 rule types instantly
└────────┬────────────┘
         │ issues list
         ▼
┌─────────────────────┐
│  AI Engine          │  Claude AI deep analysis
│  (ai_engine.py)     │  → Logic bugs, security, smells
└────────┬────────────┘
         │ ai_risk_score (0-50)
         ▼
┌─────────────────────┐
│  Risk Score         │  static_score (0-50) + ai_score (0-50)
│  Computation        │  = final score (0-100)
└─────────────────────┘
```

### Static Rules (Python)

| Code  | Description                        |
|-------|------------------------------------|
| BP000 | Syntax error                       |
| BP001 | Bare `except:` clause              |
| BP002 | Mutable default argument           |
| BP003 | `== None` instead of `is None`     |
| BP004 | Unused variable                    |
| BP005 | Division by zero (literal)         |
| BP006 | Assert statement                   |
| BP007 | Global variable usage              |
| BP008 | Silent `except: pass`              |
| BP020 | `eval()` usage                     |
| BP021 | `exec()` usage                     |
| BP022 | Hardcoded password                 |
| BP023 | Hardcoded secret                   |
| BP024 | Debug `print()` statement          |
| BP025 | TODO/FIXME comment                 |

---

## 🧪 Quick Test

```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def divide(a, b):\n    return a / b\n\nresult = divide(10, 0)",
    "language": "python"
  }'
```

---

## ⚠️ Limits
- Max code size: **10,000 characters**
- ANTHROPIC_API_KEY must be set
