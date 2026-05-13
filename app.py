from flask import Flask, render_template, request, jsonify, session
import os
import re
import requests
from dotenv import load_dotenv

# The Google generative AI client is imported lazily in setup below (so the app can run without it)

# ---------- SETUP ----------
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
model_name_default = os.getenv("GOOGLE_GEN_MODEL", "gemini-flash-latest")

# Try to import the Google Generative AI client. Keep the app running if it's unavailable.
try:
    import google.generativeai as genai
    genai_available = True
except Exception:
    genai = None
    genai_available = False

# Lazy model creation and safe generate wrapper
_model = None

def get_model():
    global _model, genai_available
    if not genai_available or not api_key:
        return None
    # Configure client (safe to call multiple times)
    try:
        genai.configure(api_key=api_key)
    except Exception:
        genai_available = False
        return None
    if _model is None:
        try:
            _model = genai.GenerativeModel(
                "gemini-flash-latest",
                system_instruction=(
                    "You are an educational assistant chatbot. "
                    "You must only provide answers related to education, learning, exams, syllabus, revision, quizzes, and doubt solving. "
                    "If the user asks anything outside of education (like jokes, movies, politics, or personal advice), "
                    "politely refuse and redirect them back to study-related help."
                )
            )
        except Exception:
            _model = None
            genai_available = False
    return _model


def rest_generate(prompt, model_name="gemini-flash-latest"):
    """Call Google's Generative Language REST API directly using API key.
    Returns text on success or None on failure.
    """
    if not api_key:
        return None
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    params = {"key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {
            "parts": [{"text": "You are an educational assistant chatbot. You must only provide answers related to education, learning, exams, syllabus, revision, quizzes, and doubt solving. If the user asks anything outside of education (like jokes, movies, politics, or personal advice), politely refuse and redirect them back to study-related help."}]
        },
        "generationConfig": {
            "temperature": 0.2
        }
    }
    try:
        r = requests.post(endpoint, params=params, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return str(data)
    except requests.exceptions.HTTPError as he:
        status = he.response.status_code if he.response is not None else ""
        if status == 404:
            msg = (
                "⚠️ REST API returned 404 Not Found. Check that the Generative Language API is enabled for your project and that the model name '" + model_name + "' is valid."
            )
        elif status in (401, 403):
            msg = "⚠️ REST API returned an authorization error (401/403). Check your `GOOGLE_API_KEY` and IAM/API access."
        else:
            msg = f"⚠️ Error calling AI (REST): {he}"
        app.logger.error("REST AI HTTP error: %s", he)
        return msg
    except Exception as e:
        app.logger.exception("REST AI call failed: %s", e)
        return f"⚠️ Error calling AI (REST): {e}"
    return None


def ai_generate(prompt, model_name="gemini-flash-latest"):
    """Return generated text or None if AI service unavailable."""
    # Prefer SDK when available
    m = get_model()
    if m:
        try:
            if hasattr(m, "generate_content"):
                return m.generate_content(prompt).text
            if hasattr(genai, "generate_text"):
                res = genai.generate_text(model=m, prompt=prompt)
                return getattr(res, "text", str(res))
        except Exception as e:
            app.logger.exception("AI SDK call failed: %s", e)
            return f"⚠️ Error calling AI (SDK): {e}"

    # Fallback to REST if API key is present
    if api_key:
        return rest_generate(prompt, model_name=model_name)

    return None

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "exam-prep-secret")

# Startup warnings about AI availability
if not genai_available:
    app.logger.warning("Generative AI SDK not available. AI features will be disabled.")
if not api_key:
    app.logger.warning("GOOGLE_API_KEY not set. Set it in .env to enable AI features.")


# ---------- Helpers ----------
def normalize_mode(m):
    if not m:
        return "quiz"
    s = str(m).lower().strip()
    # Friendly aliases from both frontend and query params
    if s in ("practice", "practice_mode", "practice-mode"):
        return "practice"
    if s in ("quiz", "practice_quiz", "practice-quiz", "practicequiz", "mcq", "study", "study_mode", "study-mode", "revision", "quick_revision", "quick-revision", "quick", "quickrev", "revision_mode"):
        return "quiz"
    if s in ("review", "review_mode", "review-mode", "doubt", "doubt_resolution", "doubt-resolution", "doubtsolve", "doubt_solve"):
        return "doubt"
    return s


# ---------- Routes ----------

@app.route('/status')
def status():
    return jsonify({
        'ai_sdk_installed': genai_available,
        'ai_api_key_set': bool(api_key),
        'model_default': model_name_default
    })

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chatbot")
def chatbot():
    mode = request.args.get("mode", "quiz")
    mode = normalize_mode(mode)
    session["mode"] = mode
    session.pop("quiz_active", None)
    session.pop("quiz_answer", None)
    session.pop("quiz_explanation", None)
    app.logger.debug("chatbot opened — mode set to: %s", mode)
    return render_template("chatbot.html", mode=mode, ai_enabled=bool(api_key), genai_available=genai_available, model_name=model_name_default)


@app.route("/chat", methods=["POST"])
def chat():
    user_msg = (request.json.get("message") or "").strip()
    # Prefer explicit mode from request body (client sets this), fall back to session
    mode = normalize_mode((request.json.get("mode") or session.get("mode", "quiz")))
    session["mode"] = mode
    app.logger.debug("incoming /chat — mode=%s | msg=%s", mode, user_msg)

    if not user_msg:
        return jsonify({"reply": "⚠️ Please enter a message."})

    # 👇 Greetings & Gratitude handling
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "good afternoon"]
    gratitude = ["thank you", "thanks", "thx", "ty", "thank u", "thankyou"]

    msg_lower = user_msg.lower()
    if any(word in msg_lower for word in greetings):
        return jsonify({"reply": "👋 Hello! How can I help you with your exam prep today?"})
    if any(word in msg_lower for word in gratitude):
        return jsonify({"reply": "🙏 You're welcome! Happy to help. Keep studying strong!"})

    # ------ REVISION MODE ------
    if mode == "revision":
        prompt = (
            f"📘 Quick Revision Mode:\n"
            f"Summarize the topic '{user_msg}' in 3–5 short sentences and then give 3-4 concise bullet points.\n"
            f"Keep it short, exam-focused and use bullets."
        )
        response_text = ai_generate(prompt)
        if not response_text:
            response_text = "⚠️ AI service not available. Please set `GOOGLE_API_KEY` and install a compatible Gen AI SDK."
        return jsonify({"reply": response_text})

    # ------ PRACTICE MODE ------
    if mode == "practice":
        prompt = (
            f"🎯 Practice Mode:\n"
            f"Generate 3-5 practice questions (a mix of short answer and conceptual questions) on the topic '{user_msg}'.\n"
            f"Provide the questions as a numbered list. Do not provide the answers immediately, so the user can practice."
        )
        response_text = ai_generate(prompt)
        if not response_text:
            response_text = "⚠️ AI service not available. Please set `GOOGLE_API_KEY` and install a compatible Gen AI SDK."
        return jsonify({"reply": response_text})

    # ------ DOUBT MODE ------
    if mode == "doubt":
        prompt = (
            f"❓ Doubt Solving Mode:\n"
            f"Explain the topic / question '{user_msg}'. First give a short paragraph (3-5 sentences), "
            f"then list 4–6 important bullet points and an example if applicable."
        )
        response_text = ai_generate(prompt)
        if not response_text:
            response_text = "⚠️ AI service not available. Please set `GOOGLE_API_KEY` and install a compatible Gen AI SDK."
        return jsonify({"reply": response_text})

    # ------ QUIZ MODE ------
    if mode == "quiz":
        if not session.get("quiz_active"):
            prompt = (
                f"📝 Quiz Practice Mode:\n"
                f"Create ONE multiple-choice exam question on '{user_msg}'.\n"
                f"Provide exactly four options labeled A), B), C), D).\n"
                f"At the end of your response, always include:\n"
                f"Correct Answer: <A/B/C/D>\n"
                f"Explanation: <one or two sentences>\n\n"
                f"⚠️ Do not put option text after the letter in 'Correct Answer'. "
                f"Only output A, B, C, or D."
            )

            raw = ai_generate(prompt)
            if not raw:
                return jsonify({"reply": "⚠️ AI service not available. Please set `GOOGLE_API_KEY` and install a compatible Gen AI SDK to use Quiz mode."})

            # --- Extract correct answer & explanation ---
            correct_match = re.search(r"Correct Answer\s*[:\-]?\s*([A-D])", raw, flags=re.I)
            if not correct_match:
                correct_match = re.search(r"Correct Answer\s*[:\-]?\s*(?:Option\s*)?([A-D])", raw, flags=re.I)

            expl_match = re.search(r"Explanation\s*[:\-]?\s*(.+)", raw, flags=re.I | re.S)

            correct = correct_match.group(1).upper() if correct_match else None
            explanation = expl_match.group(1).strip() if expl_match else ""

            # Save in session
            session["quiz_active"] = True
            session["quiz_answer"] = correct
            session["quiz_explanation"] = explanation

            # Remove answer & explanation from the student-facing question
            question_only = re.sub(r"Correct Answer[:\-].*", "", raw, flags=re.I | re.S).strip()
            question_only = re.sub(r"Explanation[:\-].*", "", question_only, flags=re.I | re.S).strip()

            return jsonify({"reply": question_only})

        else:
            # Evaluate student’s answer
            correct = session.get("quiz_answer")
            explanation = session.get("quiz_explanation", "")

            m = re.search(r"\b([A-D])\b", user_msg.upper())
            user_choice = m.group(1) if m else (user_msg.strip().upper()[:1] if user_msg else "")

            # Reset quiz session
            session.pop("quiz_active", None)
            session.pop("quiz_answer", None)
            session.pop("quiz_explanation", None)

            if not correct:
                return jsonify({"reply": "⚠️ I couldn't determine the correct answer for that question. Please try again (ask for a new quiz question)."})

            if user_choice == correct:
                return jsonify({"reply": f"✅ Correct! Explanation: {explanation}"})
            else:
                return jsonify({"reply": f"❌ Incorrect. Correct answer: {correct}. Explanation: {explanation}"})

    # ------ FALLBACK ------
    app.logger.warning("Unknown mode encountered in /chat: %s", mode)
    return jsonify({"reply": "⚠️ Invalid mode. Please pick a mode from the homepage (Revision / Quiz / Doubt)."})

# ✅ Alias for frontend fetch("/api/chat")
@app.route("/api/chat", methods=["POST"])
def api_chat():
    return chat()


if __name__ == "__main__":
    app.run()
