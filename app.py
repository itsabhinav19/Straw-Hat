from flask import Flask, request, jsonify
from flask_cors import CORS
from analyzer import StaticAnalyzer
from ai_engine import AIEngine
from ml_engine import MLEngine
import traceback

app = Flask(__name__)
CORS(app)

# -------------------------------
# Initialize engines
# -------------------------------
analyzer = StaticAnalyzer()
ml_engine = MLEngine()

# Safe AI init
try:
    ai_engine = AIEngine()
    AI_AVAILABLE = True
    print("[INFO] AI Engine initialized")
except Exception as e:
    print("[WARNING] AI disabled:", e)
    AI_AVAILABLE = False


# -------------------------------
# Health check
# -------------------------------
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "ai_enabled": AI_AVAILABLE,
        "ml_ready": ml_engine.is_ready()
    })


# -------------------------------
# Analyze endpoint
# -------------------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({"error": "Missing 'code' field"}), 400

    code = data["code"].strip()
    language = data.get("language", "python")

    if not code:
        return jsonify({"error": "Code cannot be empty"}), 400

    if len(code) > 10000:
        return jsonify({"error": "Code too long"}), 400

    try:
        # -------------------------------
        # Step 1: Static analysis
        # -------------------------------
        static_results = analyzer.analyze(code, language)

        # -------------------------------
        # Step 2: ML prediction
        # -------------------------------
        ml_results = ml_engine.predict(code, language, static_results)

        # -------------------------------
        # Step 3: AI fallback
        # -------------------------------
        if ml_results.get("needs_ai", True) and AI_AVAILABLE:
            ai_results = ai_engine.analyze(code, language, static_results)
        else:
            ai_results = {
                "ai_risk_score": 0,
                "summary": "AI skipped (ML confident or unavailable)",
                "bugs": [],
                "security_issues": [],
                "code_smells": [],
                "positive_notes": []
            }

        # -------------------------------
        # Step 4: Risk score
        # -------------------------------
        ml_score = ml_results.get("ml_risk_score") or 0
        ai_score = ai_results.get("ai_risk_score", 0)

        # fallback if ML not trained
        if ml_score == 0:
            static_score = min(len(static_results["issues"]) * 10, 50)
            risk_score = min(static_score + ai_score, 100)
        else:
            risk_score = min(ml_score + ai_score, 100)

        # -------------------------------
        # Response
        # -------------------------------
        return jsonify({
            "risk_score": risk_score,
            "risk_level": get_risk_level(risk_score),
            "static_issues": static_results["issues"],
            "ml_analysis": ml_results,
            "ai_analysis": ai_results,
            "meta": {
                "ml_used": ml_engine.is_ready(),
                "ai_used": AI_AVAILABLE
            }
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": "Analysis failed",
            "detail": str(e)
        }), 500


# -------------------------------
# Risk level helper
# -------------------------------
def get_risk_level(score):
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    elif score >= 15:
        return "LOW"
    return "CLEAN"


# -------------------------------
# Run server
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)