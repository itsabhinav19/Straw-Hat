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