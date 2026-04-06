import os
import json
import anthropic
from typing import Dict, Any


SYSTEM_PROMPT = """You are BugPredictor — an expert code review AI specializing in bug detection, 
security vulnerabilities, and code quality analysis.

You will receive code along with a list of issues already found by a static analyzer.
Your job is to perform a DEEPER analysis: look for logic bugs, race conditions, off-by-one errors, 
security flaws, bad patterns, and anything the static analyzer might have missed.

You MUST respond ONLY with valid JSON in exactly this structure:
{
  "ai_risk_score": <integer 0-50>,
  "summary": "<one sentence summary>",
  "bugs": [
    {
      "type": "<bug type>",
      "severity": "<critical|high|medium|low>",
      "description": "<what the bug is>",
      "line_hint": "<approximate area in code>",
      "suggestion": "<how to fix it>"
    }
  ],
  "security_issues": [
    {
      "type": "<vulnerability type>",
      "severity": "<critical|high|medium|low>",
      "description": "<what the issue is>",
      "suggestion": "<how to fix it>"
    }
  ],
  "code_smells": [
    "<short description of smell>"
  ],
  "positive_notes": [
    "<something done well>"
  ]
}

Scoring guide for ai_risk_score (0-50):
- 0-10: Clean code, minor concerns
- 11-25: Notable issues that need attention
- 26-40: Significant bugs or security issues
- 41-50: Critical bugs, major security vulnerabilities

Be precise and actionable. Do not hallucinate issues. If code is clean, say so."""


class AIEngine:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-opus-4-5"

    def analyze(
        self,
        code: str,
        language: str,
        static_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send code + static analysis results to Claude for deep AI analysis.
        Returns structured JSON with bugs, security issues, smells, and risk score.
        """

        static_summary = self._format_static_results(static_results)

        user_prompt = f"""Language: {language}

--- STATIC ANALYSIS RESULTS (already found) ---
{static_summary}

--- CODE TO ANALYZE ---
```{language}
{code}
```

Perform a deep analysis. Focus on issues the static analyzer may have missed.
Return ONLY valid JSON, no markdown, no explanation outside the JSON."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )

            response_text = message.content[0].text.strip()

            # Strip markdown code fences if model wraps JSON in them
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)
            return self._validate_response(result)

        except json.JSONDecodeError as e:
            return self._fallback_response(f"AI returned invalid JSON: {e}")
        except anthropic.APIError as e:
            return self._fallback_response(f"Anthropic API error: {e}")
        except Exception as e:
            return self._fallback_response(str(e))

    def _format_static_results(self, static_results: Dict[str, Any]) -> str:
        issues = static_results.get("issues", [])
        if not issues:
            return "No static issues found."
        lines = []
        for issue in issues:
            lines.append(
                f"[{issue['severity'].upper()}] Line {issue['line']}: "
                f"{issue['message']} (Code: {issue['code']})"
            )
        return "\n".join(lines)

    def _validate_response(self, result: Dict) -> Dict:
        """Ensure required keys exist with sensible defaults."""
        return {
            "ai_risk_score": max(0, min(50, int(result.get("ai_risk_score", 0)))),
            "summary": str(result.get("summary", "AI analysis complete.")),
            "bugs": result.get("bugs", []),
            "security_issues": result.get("security_issues", []),
            "code_smells": result.get("code_smells", []),
            "positive_notes": result.get("positive_notes", []),
        }

    def _fallback_response(self, error_msg: str) -> Dict:
        print(f"[AIEngine] Warning: {error_msg}")
        return {
            "ai_risk_score": 0,
            "summary": "AI analysis unavailable. Showing static analysis only.",
            "bugs": [],
            "security_issues": [],
            "code_smells": [],
            "positive_notes": [],
            "error": error_msg,
        }
