"""
app.py — BugPredictor API

Analysis priority:
    1. Static analyzer    (always runs, fast)
    2. ML model           (runs if model is trained)
    3. AI fallback        (runs only if ML confidence < threshold OR model not ready)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

from analyzer import StaticAnalyzer
from ml_engine import MLEngine
from ai_engine import AIEngine

import traceback
import os

app = Flask(__name__)
CORS(app)

# Init engines (loaded once at startup)
static_analyzer = StaticAnalyzer()
ml_engine = MLEngine(model_dir=os.environ.get("MODEL_DIR", "models/"))

# AI engine is optional — only initialised if API key is present
_ai_engine = None

def get_ai_engine():
    global _ai_engine
    if _ai_engine is not None:
        return _ai_engine
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            _ai_engine = AIEngine()
        except Exception as e:
            print(f"[AIEngine] Could not initialise: {e}")
    return _ai_engine


# ------------------------------------------------------------------ #
#  Routes
# ------------------------------------------------------------------ #

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "BugPredictor API",
        "ml_model_ready": ml_engine.is_ready(),
        "ai_fallback_ready": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({"error": "Missing 'code' field in request body"}), 400

    code = data["code"].strip()
    language = data.get("language", "python").strip().lower()

    if not code:
        return jsonify({"error": "Code cannot be empty"}), 400
    if len(code) > 10_000:
        return jsonify({"error": "Code exceeds 10,000 character limit"}), 400

    try:
        result = run_pipeline(code, language)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Analysis failed", "detail": str(e)}), 500


@app.route("/model/info", methods=["GET"])
def model_info():
    if not ml_engine.is_ready():
        return jsonify({"status": "not_trained", "message": "Run train.py to build the model."}), 404
    return jsonify({
        "status": "ready",
        "meta": ml_engine.meta,
        "top_features": ml_engine.top_features(10),
    })


# ------------------------------------------------------------------ #
#  Core pipeline
# ------------------------------------------------------------------ #

def run_pipeline(code, language):
    # Stage 1: Static analysis (always runs)
    static_results = static_analyzer.analyze(code, language)

    # Stage 2: ML prediction
    ml_result = ml_engine.predict(code, language, static_results)

    # Stage 3: AI fallback (only if ML is uncertain or not trained)
    ai_result = None
    ai_used = False

    if ml_result["needs_ai"]:
        ai = get_ai_engine()
        if ai:
            ai_result = ai.analyze(code, language, static_results)
            ai_used = True

    # Stage 4: Final risk score
    risk_score = compute_final_score(static_results, ml_result, ai_result)

    return {
        "risk_score": risk_score,
        "risk_level": get_risk_level(risk_score),
        "static_issues": static_results["issues"],
        "static_breakdown": static_results["breakdown"],
        "ml_prediction": ml_result,
        "ai_analysis": ai_result,
        "ai_used": ai_used,
        "analysis_note": build_note(ml_result, ai_used),
        "summary": build_summary(risk_score, static_results, ml_result, ai_result),
    }


def compute_final_score(static_results, ml_result, ai_result):
    bd = static_results["breakdown"]
    static_score = min(
        bd.get("error", 0) * 10 +
        bd.get("warning", 0) * 5 +
        bd.get("info", 0) * 2,
        30
    )

    ml_score = ml_result.get("ml_risk_score") or 0

    if ai_result:
        ai_score = ai_result.get("ai_risk_score", 0)  # 0-50 from AI
        if ml_result.get("ml_risk_score") is not None:
            blended = int(ml_score * 0.6 + (ai_score * 2) * 0.4)
        else:
            blended = ai_score * 2
        final = min(static_score + blended, 100)
    else:
        final = min(static_score + ml_score, 100)

    return max(0, min(100, int(final)))


def get_risk_level(score):
    if score >= 70: return "HIGH"
    if score >= 40: return "MEDIUM"
    if score >= 15: return "LOW"
    return "CLEAN"


def build_note(ml_result, ai_used):
    if ml_result.get("ml_risk_score") is None:
        return "ML model not trained yet. Static analysis only."
    conf = ml_result.get("confidence", 0)
    if ai_used:
        return f"ML confidence {conf:.0%} — AI fallback triggered for deeper analysis."
    return f"ML confidence {conf:.0%} — prediction made solely by ML model."


def build_summary(score, static_results, ml_result, ai_result):
    level = get_risk_level(score)
    issues = static_results["total"]
    label = ml_result.get("label") or "unknown"
    ai_note = ai_result.get("summary", "") if ai_result else ""
    return (
        f"Risk: {level} ({score}/100). "
        f"Static: {issues} issue(s). "
        f"ML prediction: {label}. "
        + (f"AI: {ai_note}" if ai_note else "")
    ).strip()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
