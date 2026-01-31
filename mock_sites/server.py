"""FastAPI server for mock form websites.

This server provides test forms at different difficulty levels:
- /simple - Basic contact form (MVP0 target)
- /complex - Multi-step employee onboarding form (MVP1 target)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(
    title="Mock Form Server",
    description="Test forms for GUI Agent development",
    version="0.1.0",
)

# Store submitted data in memory for verification
submitted_data: dict[str, list[dict[str, Any]]] = {
    "simple": [],
    "complex": [],
}

TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_template(name: str) -> str:
    """Load an HTML template file."""
    template_path = TEMPLATES_DIR / f"{name}.html"
    if template_path.exists():
        return template_path.read_text()
    raise FileNotFoundError(f"Template {name} not found")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Landing page with links to all forms."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mock Form Server</title>
        <style>
            body { font-family: system-ui, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            .card { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
            .card h2 { margin-top: 0; }
            .card a { display: inline-block; background: #0066cc; color: white; padding: 10px 20px;
                      text-decoration: none; border-radius: 4px; margin-top: 10px; }
            .card a:hover { background: #0055aa; }
            .difficulty { font-size: 14px; color: #666; }
            .difficulty.easy { color: green; }
            .difficulty.hard { color: orange; }
        </style>
    </head>
    <body>
        <h1>🤖 Mock Form Server</h1>
        <p>Test forms for GUI Agent development and evaluation.</p>

        <div class="card">
            <h2>Simple Contact Form</h2>
            <p class="difficulty easy">Difficulty: Easy</p>
            <p>A basic contact form with standard fields: name, email, phone, and message.</p>
            <ul>
                <li>5 input fields</li>
                <li>Basic validation</li>
                <li>Single page</li>
            </ul>
            <a href="/simple">Open Simple Form →</a>
        </div>

        <div class="card">
            <h2>Complex Employee Onboarding</h2>
            <p class="difficulty hard">Difficulty: Hard</p>
            <p>A multi-step employee onboarding form with various input types.</p>
            <ul>
                <li>15+ input fields across 3 steps</li>
                <li>Dropdowns, date pickers, radio buttons</li>
                <li>Conditional fields</li>
                <li>File upload placeholder</li>
            </ul>
            <a href="/complex">Open Complex Form →</a>
        </div>

        <div class="card">
            <h2>API Endpoints</h2>
            <ul>
                <li><code>GET /health</code> - Health check</li>
                <li><code>GET /submissions/{form_type}</code> - View submitted data</li>
                <li><code>DELETE /submissions/{form_type}</code> - Clear submissions</li>
            </ul>
        </div>
    </body>
    </html>
    """


@app.get("/simple", response_class=HTMLResponse)
async def simple_form() -> str:
    """Simple contact form - MVP0 target."""
    return load_template("simple_form")


@app.post("/simple/submit")
async def submit_simple_form(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(default=""),
    subject: str = Form(...),
    message: str = Form(...),
) -> JSONResponse:
    """Handle simple form submission."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "subject": subject,
        "message": message,
    }
    submitted_data["simple"].append(data)
    return JSONResponse(
        content={"status": "success", "message": "Form submitted successfully!", "data": data}
    )


@app.get("/complex", response_class=HTMLResponse)
async def complex_form() -> str:
    """Complex multi-step form - MVP1 target."""
    return load_template("complex_form")


@app.post("/complex/submit")
async def submit_complex_form(request: Request) -> JSONResponse:
    """Handle complex form submission."""
    form_data = await request.form()
    data = {
        "timestamp": datetime.now().isoformat(),
        **{key: value for key, value in form_data.items()},
    }
    submitted_data["complex"].append(data)
    return JSONResponse(
        content={"status": "success", "message": "Employee onboarding submitted!", "data": data}
    )


@app.get("/submissions/{form_type}")
async def get_submissions(form_type: str) -> JSONResponse:
    """Get all submissions for a form type."""
    if form_type not in submitted_data:
        return JSONResponse(
            content={"error": f"Unknown form type: {form_type}"},
            status_code=404,
        )
    return JSONResponse(content={"submissions": submitted_data[form_type]})


@app.delete("/submissions/{form_type}")
async def clear_submissions(form_type: str) -> JSONResponse:
    """Clear all submissions for a form type."""
    if form_type in submitted_data:
        submitted_data[form_type] = []
    return JSONResponse(content={"status": "cleared"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
