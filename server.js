// Secure server-side Gemini proxy. The API key lives only in .env on the server.
import "dotenv/config";
import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";

const app = express();
const PORT = process.env.PORT || 8787;
const MODEL = process.env.GEMINI_MODEL || "gemini-2.5-flash";
const CATEGORIES = ["Textiles","Wood","Metal","Plastic","Glass","Paper & Cardboard","Electronics","Construction","Packaging","Other"];
const CONDITIONS = ["Like new","Good","Fair","Needs repair"];
const MIME = ["image/jpeg","image/png","image/webp"];

app.use(express.json({ limit: "6mb" }));

// Tiny in-memory rate limiter (10 requests / minute / IP)
const hits = new Map();
app.use("/api", (req, res, next) => {
  const now = Date.now(), k = req.ip;
  const recent = (hits.get(k) || []).filter((t) => now - t < 60000);
  if (recent.length >= 10) return res.status(429).json({ error: "Too many requests. Please wait a minute and try again." });
  hits.set(k, [...recent, now]);
  next();
});

const schema = {
  type: "OBJECT",
  properties: {
    materialName: { type: "STRING" },
    category: { type: "STRING", enum: CATEGORIES },
    description: { type: "STRING" },
    conditionEstimate: { type: "STRING", enum: CONDITIONS },
    reuseIdeas: { type: "ARRAY", items: { type: "STRING" } },
    suggestedTitle: { type: "STRING" },
  },
  required: ["materialName","category","description","conditionEstimate","reuseIdeas","suggestedTitle"],
};

const PROMPT = `You help list reusable waste and surplus materials on a circular-economy marketplace.
Analyze the photo and return JSON only. Rules:
- Describe only what is visibly present. Never state or estimate weight, volume, count or dimensions; the seller enters quantity separately.
- conditionEstimate is a visual estimate only.
- reuseIdeas: 3 to 5 short, practical ideas.
- suggestedTitle: under 70 characters, no quantity claims.
- If the image does not show a reusable material, use category "Other" and say so in the description.`;

app.get("/api/health", (_req, res) => res.json({ ok: true, aiConfigured: Boolean(process.env.GEMINI_API_KEY) }));

app.post("/api/analyze", async (req, res) => {
  try {
    if (!process.env.GEMINI_API_KEY) return res.status(503).json({ error: "AI is not configured on the server. Add GEMINI_API_KEY to .env and restart." });
    const { image, mimeType, categoryHint } = req.body || {};
    if (!image || typeof image !== "string" || !MIME.includes(mimeType)) return res.status(400).json({ error: "Upload a JPG, PNG or WebP image." });
    const data = image.replace(/^data:[^;]+;base64,/, "");
    if (data.length > 5_500_000) return res.status(413).json({ error: "Image is too large. Try a smaller photo." });

    const hint = CATEGORIES.includes(categoryHint) ? `\nThe seller selected the category "${categoryHint}"; use it only if it fits the photo.` : "";
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": process.env.GEMINI_API_KEY },
      body: JSON.stringify({
        contents: [{ parts: [{ text: PROMPT + hint }, { inline_data: { mime_type: mimeType, data } }] }],
        generationConfig: { responseMimeType: "application/json", responseSchema: schema, temperature: 0.3 },
      }),
    });
    if (!r.ok) {
      console.error("Gemini error", r.status, await r.text());
      return res.status(502).json({ error: r.status === 429 ? "The AI service is busy. Try again shortly." : "The AI service could not analyze this image." });
    }
    const json = await r.json();
    const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) return res.status(502).json({ error: "The AI returned no result. Try a clearer photo." });
    const p = JSON.parse(text);
    res.json({
      materialName: String(p.materialName || "").slice(0, 80),
      category: CATEGORIES.includes(p.category) ? p.category : "Other",
      description: String(p.description || "").slice(0, 600),
      conditionEstimate: CONDITIONS.includes(p.conditionEstimate) ? p.conditionEstimate : "Fair",
      reuseIdeas: (Array.isArray(p.reuseIdeas) ? p.reuseIdeas : []).slice(0, 5).map((s) => String(s).slice(0, 160)),
      suggestedTitle: String(p.suggestedTitle || "").slice(0, 90),
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "Something went wrong on the server." });
  }
});

// Serve the built app in production (npm run build && npm start)
const dist = path.join(path.dirname(fileURLToPath(import.meta.url)), "dist");
app.use(express.static(dist));
app.get("*", (_req, res) => res.sendFile(path.join(dist, "index.html"), (err) => err && res.status(404).end()));

app.listen(PORT, () => console.log(`API on http://localhost:${PORT}  (AI ${process.env.GEMINI_API_KEY ? "ready" : "NOT configured"})`));
