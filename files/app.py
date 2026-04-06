from flask import Flask, request, jsonify
from flask_cors import CORS
from analyzer import StaticAnalyzer
from ai_engine import AIEngine
import traceback

app = Flask(__name__)
CORS(app)

analyzer = StaticAnalyzer()
ai_engine = AIEngine()


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "BugPredictor API"})


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({"error": "Missing 'code' field in request body"}), 400

    code = data["code"].strip()
    language = data.get("language", "python")

    if not code:
        return jsonify({"error": "Code cannot be empty"}), 400

    if len(code) > 10_000:
        return jsonify({"error": "Code exceeds 10,000 character limit"}), 400

    try:
        # Step 1: Static analysis (fast, rule-based)
        static_results = analyzer.analyze(code, language)

        # Step 2: AI-powered deep analysis
        ai_results = ai_engine.analyze(code, language, static_results)

        # Step 3: Compute final risk score
        risk_score = compute_risk_score(static_results, ai_results)

        return jsonify({
            "risk_score": risk_score,
            "risk_level": get_risk_level(risk_score),
            "static_issues": static_results["issues"],
            "ai_analysis": ai_results,
            "summary": build_summary(risk_score, static_results, ai_results),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Analysis failed", "detail": str(e)}), 500


def compute_risk_score(static_results, ai_results):
    """Combine static + AI signals into a 0-100 risk score."""
    static_score = min(len(static_results["issues"]) * 8, 50)
    ai_score = ai_results.get("ai_risk_score", 0)  # 0-50 from AI
    return min(int(static_score + ai_score), 100)


def get_risk_level(score):
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    elif score >= 15:
        return "LOW"
    return "CLEAN"


def build_summary(score, static_results, ai_results):
    level = get_risk_level(score)
    issue_count = len(static_results["issues"])
    return (
        f"Risk level: {level} ({score}/100). "
        f"Found {issue_count} static issue(s). "
        f"{ai_results.get('summary', '')}"
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
