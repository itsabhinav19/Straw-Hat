# BugPredictor 🚀

## Overview
BugPredictor is an AI-powered backend system for detecting bugs, security issues, and code quality problems using a hybrid pipeline:

1. Static Analysis (rule-based, AST + regex)
2. Machine Learning Model (trained on code features)
3. AI Deep Analysis (fallback using Claude)

---

## ✅ What Has Been Implemented

### 1. Static Analyzer
- Python AST-based analysis
- Regex-based detection for other languages
- Detects:
  - Syntax errors
  - Mutable defaults
  - Bare exceptions
  - Hardcoded secrets
  - Debug statements
  - Code smells

---

### 2. Feature Engineering
- 40+ features extracted from code:
  - Structural (functions, loops, conditions)
  - Complexity (cyclomatic, nesting)
  - Code smells
  - Static issue counts

---

### 3. Machine Learning Engine
- Supports:
  - Classification (buggy vs clean)
  - Regression (risk score 0–100)
- Uses:
  - Gradient Boosting
  - Feature scaling
- Outputs:
  - Risk score
  - Confidence
  - Prediction label

---

### 4. AI Engine (Fallback)
- Uses Claude API
- Performs deep semantic analysis
- Detects:
  - Logic bugs
  - Security vulnerabilities
  - Hidden issues missed by static analysis

---

### 5. API Layer (Flask)
- Endpoints:
  - GET / → health check
  - POST /analyze → analyze code
  - GET /model/info → model details
- Pipeline:
  Static → ML → AI (if needed)

---

### 6. Training Pipeline
- CSV-based dataset input
- Feature extraction pipeline
- Model training + evaluation
- Saves:
  - Trained model (.joblib)
  - Metadata (.json)

---

## 📁 Project Structure

```
bugpredictor/
│
├── app.py
├── analyzer.py
├── ai_engine.py
├── ml_engine.py
├── feature_extractor.py
├── train.py
├── requirements.txt
│
├── models/
├── data/
└── tests/
```

---

## ⚙️ How to Run

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Train model
```
python train.py --dataset dataset.csv
```

### 3. Set environment variables
```
export MODEL_DIR=models/
export ANTHROPIC_API_KEY=your_key_here  # optional
```

### 4. Run server
```
python app.py
```

---

## 🧪 Example Request

```
POST /analyze
{
  "code": "print('hello world')",
  "language": "python"
}
```

---

## 🔥 Current Capabilities

- Hybrid bug detection system
- ML + AI combined inference
- Multi-layer risk scoring
- Extensible architecture

---

## 🚧 Current Limitations

- Requires dataset for ML training
- Limited multi-language support (non-Python uses regex)
- No frontend yet

---

## 🎯 Future Improvements (Optional)

- Add React frontend
- Integrate Tree-sitter for multi-language parsing
- Add authentication & rate limiting
- Improve dataset quality

---

## 🧠 Tech Stack

- Python
- Flask
- Scikit-learn
- NumPy / Pandas
- Anthropic API

---

## 📌 Status

✅ Backend fully functional  
⚙️ ML + AI pipeline working  
🚀 Ready for GitHub / Resume / Deployment  

---

## Author
Harjit Singh
