# Study-Exam-Bot

Study-Exam-Bot is a small Flask app that provides study helpers: quick revision, doubt solving, and quiz practice.

## Local setup

1. Create a venv (either Python 3.12 or 3.11). If you want the official Gen AI SDK, create a Python 3.11 venv.

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example` and add your `GOOGLE_API_KEY` if you have one.

4. Run the app:

```bash
python app.py
```

Open http://127.0.0.1:5000

## Enabling Google Generative AI (optional)

If you want real AI responses (not the offline fallback), do this:

1. Enable the **Generative Language API** (or Gemini API) in your Google Cloud project.
2. Create an **API key** and put it in your `.env` as `GOOGLE_API_KEY`.
3. Optionally set `GOOGLE_GEN_MODEL` (default: `text-bison-001`).

If the REST call returns a 404, verify the model name and ensure the Generative API is enabled for the project associated with the API key.

## Troubleshooting

- Use `GET /status` to check whether an API key is set and whether the local GenAI SDK is installed.
- If you see a 404 from REST, check model name and enable the Generative Language API in Google Cloud Console.
- If you see a 401/403, check that the API key is valid and has required permissions.

