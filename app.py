"""Flask version of the SecondLife Grid backend (replaces server.js).
The Gemini API key is read from .env on the server and never reaches the browser."""
import os, time, json, collections
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory

load_dotenv()
app = Flask(__name__, static_folder="dist", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CATEGORIES = ["Textiles", "Wood", "Metal", "Plastic", "Glass", "Paper & Cardboard", "Electronics", "Construction", "Packaging", "Other"]
CONDITIONS = ["Like new", "Good", "Fair", "Needs repair"]
MIME = ["image/jpeg", "image/png", "image/webp"]

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "materialName": {"type": "STRING"},
        "category": {"type": "STRING", "enum": CATEGORIES},
        "description": {"type": "STRING"},
        "conditionEstimate": {"type": "STRING", "enum": CONDITIONS},
        "reuseIdeas": {"type": "ARRAY", "items": {"type": "STRING"}},
        "suggestedTitle": {"type": "STRING"},
    },
    "required": ["materialName", "category", "description", "conditionEstimate", "reuseIdeas", "suggestedTitle"],
}

PROMPT = """You help list reusable waste and surplus materials on a circular-economy marketplace.
Analyze the photo and return JSON only. Rules:
- Describe only what is visibly present. Never state or estimate weight, volume, count or dimensions; the seller enters quantity separately.
- conditionEstimate is a visual estimate only.
- reuseIdeas: 3 to 5 short, practical ideas.
- suggestedTitle: under 70 characters, no quantity claims.
- If the image does not show a reusable material, use category "Other" and say so in the description."""

hits = collections.defaultdict(list)


@app.before_request
def rate_limit():
    if request.path.startswith("/api"):
        now = time.time()
        recent = [t for t in hits[request.remote_addr] if now - t < 60]
        if len(recent) >= 10:
            return jsonify(error="Too many requests. Please wait a minute and try again."), 429
        hits[request.remote_addr] = recent + [now]


@app.get("/api/health")
def health():
    return jsonify(ok=True, aiConfigured=bool(os.getenv("GEMINI_API_KEY")))


@app.post("/api/analyze")
def analyze():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return jsonify(error="AI is not configured on the server. Add GEMINI_API_KEY to .env and restart."), 503
    body = request.get_json(silent=True) or {}
    image, mime, hint = body.get("image"), body.get("mimeType"), body.get("categoryHint")
    if not isinstance(image, str) or mime not in MIME:
        return jsonify(error="Upload a JPG, PNG or WebP image."), 400
    data = image.split(",", 1)[1] if image.startswith("data:") else image
    if len(data) > 5_500_000:
        return jsonify(error="Image is too large. Try a smaller photo."), 413

    text = PROMPT + (f'\nThe seller selected the category "{hint}"; use it only if it fits the photo.' if hint in CATEGORIES else "")
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            json={
                "contents": [{"parts": [{"text": text}, {"inline_data": {"mime_type": mime, "data": data}}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0.3},
            },
            timeout=60,
        )
        if not r.ok:
            app.logger.error("Gemini error %s %s", r.status_code, r.text)
            msg = "The AI service is busy. Try again shortly." if r.status_code == 429 else "The AI service could not analyze this image."
            return jsonify(error=msg), 502
        out = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        p = json.loads(out)
    except (requests.RequestException, KeyError, IndexError, ValueError):
        app.logger.exception("Analyze failed")
        return jsonify(error="The AI returned no usable result. Try a clearer photo."), 502

    ideas = p.get("reuseIdeas") if isinstance(p.get("reuseIdeas"), list) else []
    return jsonify(
        materialName=str(p.get("materialName", ""))[:80],
        category=p.get("category") if p.get("category") in CATEGORIES else "Other",
        description=str(p.get("description", ""))[:600],
        conditionEstimate=p.get("conditionEstimate") if p.get("conditionEstimate") in CONDITIONS else "Fair",
        reuseIdeas=[str(s)[:160] for s in ideas[:5]],
        suggestedTitle=str(p.get("suggestedTitle", ""))[:90],
    )


# Serve the built React app (run `npm run build` first)
@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def spa(path):
    full = os.path.join(app.static_folder, path)
    if path and os.path.isfile(full):
        return send_from_directory(app.static_folder, path)
    if os.path.isfile(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    return "Frontend not built. Run `npm run build`, or use `npm run dev` for development.", 404


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", 8787)), debug=False)
