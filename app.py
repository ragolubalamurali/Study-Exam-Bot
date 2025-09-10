from flask import Flask, render_template, request, jsonify, session
import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# ---------- SETUP ----------
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("⚠️ GOOGLE_API_KEY is missing. Please set it in your .env file.")
genai.configure(api_key=api_key)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "exam-prep-secret")

# Gemini model with system instruction
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    system_instruction=(
        "You are an educational assistant chatbot. "
        "You must only provide answers related to education, learning, exams, syllabus, revision, quizzes, and doubt solving. "
        "If the user asks anything outside of education (like jokes, movies, politics, or personal advice), "
        "politely refuse and redirect them back to study-related help."
    )
)

# ---------- Helpers ----------
def normalize_mode(m):
    if not m:
        return "revision"
    s = str(m).lower().strip()
    if s in ("revision", "quick_revision", "quick-revision", "quick", "quickrev", "revision_mode"):
        return "revision"
    if s in ("quiz", "practice_quiz", "practice-quiz", "practice", "practicequiz", "mcq"):
        return "quiz"
    if s in ("doubt", "doubt_resolution", "doubt-resolution", "doubtsolve", "doubt_solve"):
        return "doubt"
    return s


# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chatbot")
def chatbot():
    mode = request.args.get("mode", "revision")
    mode = normalize_mode(mode)
    session["mode"] = mode
    session.pop("quiz_active", None)
    session.pop("quiz_answer", None)
    session.pop("quiz_explanation", None)
    app.logger.debug("chatbot opened — mode set to: %s", mode)
    return render_template("chatbot.html", mode=mode)


@app.route("/chat", methods=["POST"])
def chat():
    user_msg = (request.json.get("message") or "").strip()
    mode = normalize_mode(session.get("mode", "revision"))
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
        try:
            response_text = model.generate_content(prompt).text
        except Exception as e:
            response_text = f"⚠️ Error: {e}"
        return jsonify({"reply": response_text})

    # ------ DOUBT MODE ------
    if mode == "doubt":
        prompt = (
            f"❓ Doubt Solving Mode:\n"
            f"Explain the topic / question '{user_msg}'. First give a short paragraph (3-5 sentences), "
            f"then list 4–6 important bullet points and an example if applicable."
        )
        try:
            response_text = model.generate_content(prompt).text
        except Exception as e:
            response_text = f"⚠️ Error: {e}"
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

            try:
                raw = model.generate_content(prompt).text
            except Exception as e:
                return jsonify({"reply": f"⚠️ Error generating quiz: {e}"})

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
