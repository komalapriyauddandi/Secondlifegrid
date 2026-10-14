# SecondLife Grid

React (Vite) front end + Express back end that proxies Google Gemini. The API key stays on the server (`.env`), never in the browser bundle.

## Run
1. Install Node 18+.
2. `npm install`
3. `cp .env.example .env` and set `GEMINI_API_KEY` (free key: https://aistudio.google.com/apikey)
4. `npm run dev` then open http://localhost:5173

Production: `npm run build && npm start` then open http://localhost:8787

## Notes
- Listings and recorded reuse are saved in the browser (localStorage). Swap for a database to share across users.
- Buyers in Smart Match are demo profiles.
- The server validates image type/size, rate-limits requests, and constrains Gemini output with a JSON schema.
