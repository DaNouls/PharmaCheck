# PharmaCheck

A drug information and compatibility analysis web application that uses the OpenFDA Drug Label API and Google Gemini AI.

## Architecture

- **Backend**: FastAPI (Python) — serves REST API and mounts the frontend as static files
- **Frontend**: Vanilla HTML/CSS/JS (no build step required)
- **Port**: 5000 (both frontend and API on the same server)

## Project Structure

```
main.py              # Entry point — runs uvicorn on port 5000
backend/
  main.py            # FastAPI app with all API routes + static file mount
  data.py            # Drug data helpers
  requirements.txt   # Python dependencies
frontend/
  index.html         # Main HTML page
  style.css          # Styles
  app.js             # Frontend JS (uses relative API URLs)
```

## Key Details

- The backend mounts the `frontend/` directory as static files at `/`
- All API routes live under `/api/drugs/...`
- `API_BASE` in `frontend/app.js` is set to `''` (relative URLs) since backend serves frontend
- Supports Spanish/European drug name translations to FDA names

## Dependencies

- fastapi, uvicorn, httpx (from backend/requirements.txt)
- gunicorn + uvicorn workers for production deployment

## Running

Development: `python main.py` (port 5000)
Production: gunicorn with UvicornWorker bound to 0.0.0.0:5000
