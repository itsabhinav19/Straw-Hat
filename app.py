<<<<<<< HEAD
import streamlit as st
import requests

st.set_page_config(page_title="BugPredictor", layout="wide")

# 🔥 Custom Header
st.markdown("""
<h1 style='text-align: center; color: #4CAF50;'>🐞 BugPredictor</h1>
<p style='text-align: center; font-size:18px;'>
AI-powered bug detection for developers 🚀
</p>
<hr>
""", unsafe_allow_html=True)

# Create layout
col1, col2 = st.columns(2)

# 🔹 LEFT SIDE (Input)
with col1:
    st.markdown("### 💻 Code Input")
    code = st.text_area("Paste your code here:", height=400)
    language = st.selectbox("Select Language", ["python", "java"])
    analyze_btn = st.button("🚀 Analyze")


# 🔹 Backend function
def analyze_code(code, language):
    try:
        response = requests.post(
            "http://localhost:8000/analyze",
            json={"code": code, "language": language}
        )
        return response.json()
    except:
        return {
            "risk_score": 80,
            "issues": [
                {"line": 5, "issue": "Unused variable"},
                {"line": 10, "issue": "Deep nesting"}
            ],
            "suggestions": [
                "Remove unused variable",
                "Simplify logic"
            ]
        }


# 🔹 RIGHT SIDE (Results)
with col2:
    st.markdown("### 📊 Analysis Result")
    st.markdown("---")

    if analyze_btn:
        if code.strip() == "":
            st.warning("⚠️ Please enter code!")
        else:
            with st.spinner("Analyzing..."):
                result = analyze_code(code, language)

            # 🔴 Risk Score
            st.subheader("⚠️ Risk Score")
            score = result["risk_score"]

            if score < 40:
                st.success(f"🟢 Low Risk: {score}")
            elif score < 70:
                st.warning(f"🟡 Medium Risk: {score}")
            else:
                st.error(f"🔴 High Risk: {score}")

            st.progress(score / 100)

            # 🔍 Issues
            st.subheader("🔍 Issues Found")
            for issue in result["issues"]:
                st.error(f"⚠️ Line {issue['line']}: {issue['issue']}")

            # 💡 Suggestions
            st.subheader("💡 Suggestions")
            for s in result["suggestions"]:
                st.info(f"💡 {s}")

# 🔥 Footer
st.markdown("""
<hr>
<p style='text-align: center;'>
Built with ❤️ 
</p>
""", unsafe_allow_html=True)
=======
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
>>>>>>> 8e530d7548922c705a1b199fa688cab9fe9f5f48
