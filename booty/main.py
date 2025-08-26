from uuid import uuid4
import os
import base64
import hashlib
from typing import Optional, Dict

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from admin import admin_router
from calculator import (
    industry_benchmarks,
    calculate_customer_churn_loss,
    calculate_efficiency_loss_and_roi,
    calculate_leadership_drag_loss,
    calculate_productivity_metrics,
    calculate_productivity_metrics_dive,
)
from operational_risk import run_operational_risk, RiskInput
from profit_projection import router as profit_router
from profit_projection import ProfitRequest, compute_projection


# === App ===
app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.candooculture.com",
        "https://candooculture.com",
        "https://clarity.candooculture.com",
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Health check
@app.get("/healthz")
def healthz():
    return {"ok": True}

app.include_router(admin_router)
app.include_router(profit_router)


# === Simple unlock capture (Sheets log, non-blocking) ===
@app.post("/unlock-user")
async def unlock_user_email(request: Request):
    """
    Logs unlocks to Google Sheets and always returns 200 so the UI can proceed.
    """
    try:
        payload = await request.json()
        email = str(payload.get("email", "")).strip()
        if "@" not in email:
            raise HTTPException(status_code=400, detail="Invalid email")

        gs_url = "https://script.google.com/macros/s/AKfycbwbtb1kDD5fOJrtCVtfcVq2H5vdgrpYhw89zpnJryUEiuset9AUBWSkNRPTU_5So-t-/exec"
        timestamp = pd.Timestamp.utcnow().isoformat() + "Z"

        try:
            r = requests.post(
                gs_url,
                data={"email": email, "timestamp": timestamp, "source": "module-unlock"},
                timeout=10,
            )
            if not r.ok:
                print(f"⚠️ Sheets logging failed: {r.status_code} {r.text[:160]}")
        except Exception as e:
            print(f"⚠️ Sheets logging error: {e}")

        print(f"🔓 Unlock email captured: {email} @ {timestamp}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ /unlock-user error (non-fatal): {e}")
        return {"success": True}


# === Input Models for calculators ===
class EfficiencyAutoInput(BaseModel):
    industry: str
    total_employees: int
    avg_salary: float
    improvement_rate: float

class ChurnCalculatorRequest(BaseModel):
    num_customers: int
    churn_rate: float
    avg_revenue: float
    cac: float
    desired_improvement: float
    industry: str

class LeadershipDragCalculatorRequest(BaseModel):
    industry: str
    total_employees: int
    avg_salary: float
    leadership_drag: float

class WorkforceProductivityFullRequest(BaseModel):
    industry: str
    total_revenue: float
    payroll_cost: float
    total_employees: int
    productive_hours: float
    target_hours_per_employee: float
    absenteeism_days: float
    overtime_hours: float

class ProductivityDeepDiveInput(BaseModel):
    industry: str
    total_employees: int
    avg_salary: float
    absenteeism_days: Optional[float] = 0
    avg_hours: Optional[float] = 0


# === Module Calculator Endpoints ===
@app.post("/run-payroll-waste")
def run_payroll_waste(data: EfficiencyAutoInput):
    return calculate_efficiency_loss_and_roi(data)

@app.post("/run-churn-calculator")
def run_churn(data: ChurnCalculatorRequest):
    return calculate_customer_churn_loss(data)

@app.post("/run-leadership-drag-calculator")
def run_leadership_drag(data: LeadershipDragCalculatorRequest):
    return calculate_leadership_drag_loss(data)

@app.post("/run-workforce-productivity")
def run_workforce_productivity(data: WorkforceProductivityFullRequest):
    return calculate_productivity_metrics(data)

@app.post("/run-productivity-dive")
def run_productivity_dive(data: ProductivityDeepDiveInput):
    return calculate_productivity_metrics_dive(data)

@app.get("/get-industry-benchmarks")
def get_industry_benchmarks(industry: str):
    b = industry_benchmarks(industry)
    return {
        "churn_rate": int(b.get("Customer Churn Rate (%) (Value)", 0)),
        "inefficiency_rate": int(b.get("Process Inefficiency Rate (%) (Value)", 0)),
        "leadership_drag": int(b.get("Leadership Drag Impact (%) (Value)", 10)),
        "target_hours_per_employee": int(b.get("Target Hours per Employee (Value)", 160)),
        # Expose per-employee source of truth and keep back-compat key
        "absenteeism_days_per_employee": float(b.get("Absenteeism Days per Month (Value)", 1.0)),
        "absenteeism_days": float(b.get("Absenteeism Days per Month (Value)", 1.0)),
        "cac": int(b.get("Customer Acquisition Cost (CAC) (AUD) (Value)", 800))
    }

@app.get("/get-all-industries")
def get_all_industries():
    df = pd.read_csv("benchmarks/final_cleaned_benchmarks_with_certainty.csv")
    return {"industries": sorted(df["Industry"].dropna().unique().tolist())}


# === ORS Scoring Endpoint ===
@app.post("/run-operational-risk")
def run_operational_risk_calculator(data: RiskInput):
    try:
        return run_operational_risk(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === ORS Email Report (existing) ===
def format_dollars(value):
    if value is None or value == "N/A":
        return "$N/A"
    try:
        return f"${float(value):,.0f}"
    except:
        return "$N/A"

def render_report_html(data):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>ORS Report</title>
    <!-- Montserrat webfont -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
      body {{
        font-family: "Montserrat", Arial, Helvetica, sans-serif;
        background-color: #ffffff;
        color: #333333;
        max-width: 640px;
        margin: 0 auto;
        padding: 30px 20px;
        line-height: 1.6;
        -webkit-font-smoothing: antialiased;
        text-rendering: optimizeLegibility;
      }}
      h2 {{
        text-align: center;
        color: #111111;
        font-size: 24px;
        margin-bottom: 10px;
        font-weight: 600;
      }}
      h3 {{
        font-size: 20px;
        border-bottom: 1px solid #ddd;
        padding-bottom: 6px;
        margin-top: 30px;
        color: #000;
        font-weight: 600;
      }}
      h4 {{
        font-size: 16px;
        color: #555;
        margin-top: 24px;
        margin-bottom: 6px;
        font-weight: 600;
      }}
      ul {{
        list-style: none;
        padding-left: 0;
        margin-top: 0;
      }}
      li {{
        padding: 4px 0;
        border-bottom: 1px solid #eee;
      }}
      li:last-child {{
        border-bottom: none;
      }}
      p, li {{
        font-size: 14px;
        font-weight: 400;
      }}
      em {{
        font-style: italic;
        color: #777;
      }}
      .small-note {{
        font-size: 12px;
        color: #666;
        margin-top: 6px;
      }}
      .footer-note {{
        margin-top: 30px;
        font-size: 13px;
        color: #777;
        text-align: center;
      }}
      .cta {{
        text-align: center;
        background: #f7f7f7;
        padding: 16px;
        margin: 20px 0;
        border: 1px solid #e1e1e1;
        border-radius: 6px;
      }}
      .cta a {{
        color: #0066cc;
        text-decoration: none;
        font-weight: bold;
      }}
    </style>
  </head>
  <body>
    <!-- LOGO -->
    <div style="text-align: center; margin-bottom: 20px;">
      <img src="https://cdn.prod.website-files.com/6837cb68fba35c01d42b2008/683bf2a9cdebe0a37abc749f_icons%20website-p-500.png"
           alt="Candoo Culture" width="140" style="max-width: 100%; height: auto;" />
    </div>

    <!-- SINGLE CTA -->
    <div class="cta">
      <p>Ready to take action? <a href="mailto:aaron@candooculture.com" target="_blank" rel="noopener">Book a 15-minute strategy call</a> to unpack your results.</p>
    </div>

    <!-- TITLE -->
    <h2>📊 Operational Risk Summary</h2>
    <p style="text-align: center; color: #666;">Snapshot of your financial risk due to operational inefficiencies.</p>
    <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;" />

    <!-- EBITDA -->
    <h3>🔥 EBITDA at Risk</h3>
    <ul>
      <li><strong>Total Risk Impact:</strong> {format_dollars(data.get("total_risk_dollars"))}</li>
      <li><strong>Estimated EBITDA Margin:</strong> {data.get("ebitda_margin", "N/A")}%</li>
      <li><strong>EBITDA at Risk:</strong> {data.get("ebitda_risk_pct", "N/A")}%</li>
    </ul>
    <p class="small-note"><em>If EBITDA at Risk &gt; 100%, the at-risk total exceeds current EBITDA.</em></p>

    <!-- MODULE BREAKDOWN -->
    <h3>📋 Risk Breakdown</h3>
    <ul>
      <li><strong>Payroll Waste:</strong> {format_dollars(data.get("module_breakdown", {}).get("Payroll Waste"))}</li>
      <li><strong>Customer Churn:</strong> {format_dollars(data.get("module_breakdown", {}).get("Customer Churn"))}</li>
      <li><strong>Leadership Drag:</strong> {format_dollars(data.get("module_breakdown", {}).get("Leadership Drag"))}</li>
      <li><strong>Workforce Productivity:</strong> {format_dollars(data.get("module_breakdown", {}).get("Workforce Productivity"))}</li>
      <li><strong>Productivity (Deep Dive):</strong> {format_dollars(data.get("module_breakdown", {}).get("Productivity (Deep Dive)"))}</li>
    </ul>

    <!-- INPUTS SUMMARY -->
    <h3>🧠 Inputs Summary</h3>
    <p><em>This is a direct summary of the inputs used. Some values may reflect industry benchmarks.</em></p>

    <h4>Business Context</h4>
    <ul>
      <li><strong>Industry:</strong> {data.get("industry", "N/A")}</li>
      <li><strong>Total Employees:</strong> {data.get("total_employees", "N/A")}</li>
      <li><strong>Average Salary:</strong> {format_dollars(data.get("avg_salary"))}</li>
      <li><strong>Total Revenue:</strong> {format_dollars(data.get("total_revenue"))}</li>
    </ul>

    <h4>Customer Economics</h4>
    <ul>
      <li><strong>Number of Customers:</strong> {data.get("num_customers", "N/A")}</li>
      <li><strong>Average Revenue per Customer:</strong> {format_dollars(data.get("avg_revenue"))}</li>
      <li><strong>CAC:</strong> {format_dollars(data.get("cac"))}</li>
      <li><strong>Churn Rate:</strong> {data.get("churn_rate", "N/A")}%</li>
      <li><strong>Desired Improvement:</strong> {data.get("desired_improvement", "N/A")}%</li>
    </ul>

    <h4>Workforce &amp; Operations</h4>
    <ul>
      <li><strong>Leadership Drag:</strong> {data.get("leadership_drag", "N/A")}%</li>
      <li><strong>Productive Hours (org/month):</strong> {data.get("productive_hours", "N/A")}</li>
      <li><strong>Target Hours per Employee (per month):</strong> {data.get("target_hours_per_employee", "N/A")}</li>
      <li><strong>Average Weekly Hours (per employee):</strong> {data.get("avg_hours", "N/A")}</li>
      <li><strong>Overtime Hours (org/month):</strong> {data.get("overtime_hours", "N/A")}</li>
      <li><strong>Absenteeism Days (per employee/month):</strong> {data.get("absenteeism_days", "N/A")}</li>
    </ul>

    <h4>Calculated &amp; Efficiency Factors</h4>
    <ul>
      <li><strong>Payroll Cost:</strong> {format_dollars(data.get("payroll_cost"))}</li>
      <li><strong>Improvement Rate:</strong> {data.get("improvement_rate", "N/A")}%</li>
    </ul>

    <p class="footer-note">
      All amounts in AUD. Time-based metrics are monthly unless stated.<br>
      Generated by the Candoo Culture ORS Engine<br>
      <a href="https://www.candooculture.com" style="color: #0066cc; text-decoration: none;">www.candooculture.com</a>
    </p>
  </body>
</html>
    """


@app.post("/send-risk-report")
async def send_risk_report(request: Request):
    try:
        data = await request.json()

        # === CAPTCHA VALIDATION ===
        captcha_token = data.get("captcha_token")
        secret = os.getenv("RECAPTCHA_SECRET_KEY")
        if not captcha_token:
            raise HTTPException(status_code=400, detail="Missing CAPTCHA token")
        if not secret:
            raise HTTPException(status_code=500, detail="Missing CAPTCHA secret key")

        verify_response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": captcha_token}
        )
        if not verify_response.json().get("success"):
            raise HTTPException(status_code=400, detail="CAPTCHA validation failed")

        # === ORS calculation ===
        try:
            ors_result = run_operational_risk(RiskInput(**data))
            data.update(ors_result)  # adds total_risk_dollars, module_breakdown, etc.
        except Exception as calc_error:
            print("ORS calculation failed:", calc_error)
            ors_result = {}

        # ---------- Build snapshot ----------
        def _num(x):
            try:
                if x is None or x == "":
                    return None
                return float(x)
            except Exception:
                return None

        breakdown = (data.get("module_breakdown") or ors_result.get("module_breakdown") or {})

        def bdnum(label, fallback_key=None):
            v = _num(breakdown.get(label))
            if v is None and fallback_key:
                v = _num(data.get(fallback_key))
            return v

        snapshot = {
            "report_id": str(uuid4()),
            "email": data.get("recipient"),
            "snapshot_at": pd.Timestamp.utcnow().isoformat() + "Z",
            "version": "ors-snapshot-1",
            "currency": "AUD",
            "inputs": {
                "revenue":   _num(data.get("total_revenue")),
                "cogs":      _num(data.get("cogs")),
                "opex":      _num(data.get("opex")),
                "gross_now": _num(data.get("gross_now")),
                "net_now":   _num(data.get("net_now")),
            },
            "savings": {
                "payroll_savings":      bdnum("Payroll Waste",            "payroll_savings"),
                "churn_recovery":       bdnum("Customer Churn",           "churn_recovery"),
                "workforce_gain":       bdnum("Workforce Productivity",   "workforce_gain"),
                "deep_dive_gain":       bdnum("Productivity (Deep Dive)", "deep_dive_gain"),
                "leadership_reduction": bdnum("Leadership Drag",          "leadership_reduction"),
            },
            "risk": {
                "ors_ebitda_at_risk": _num(data.get("total_risk_dollars") or ors_result.get("total_risk_dollars")),
            },
        }

        fixes_vals = [v for v in snapshot["savings"].values() if isinstance(v, (int, float))]
        fixes_total = sum(fixes_vals) if fixes_vals else None
        net_now = snapshot["inputs"].get("net_now")
        ors_risk = snapshot["risk"].get("ors_ebitda_at_risk")
        best_case_net = None
        if isinstance(net_now, (int, float)):
            best_case_net = net_now + (fixes_total or 0) + (ors_risk or 0)

        snapshot["totals"] = {
            "fixes_total": fixes_total,
            "best_case_net": best_case_net
        }

        # ---- Mailgun send ----
        mg_api_key = os.getenv("MAILGUN_API_KEY")
        mg_domain = os.getenv("MAILGUN_DOMAIN")
        mg_sender = os.getenv("MAILGUN_SENDER")
        if not all([mg_api_key, mg_domain, mg_sender]):
            raise Exception("Missing Mailgun environment variables.")

        response = requests.post(
            f"https://api.mailgun.net/v3/{mg_domain}/messages",
            auth=("api", mg_api_key),
            data={
                "from": f"Candoo Culture Reports <{mg_sender}>",
                "to": [data["recipient"]],
                "bcc": ["aaron@candooculture.com"],
                "subject": data["subject"],
                "html": render_report_html(data)
            }
        )
        if response.status_code != 200:
            raise Exception(f"Mailgun Error: {response.text}")

        return {"success": True, "message": "Report sent.", "snapshot": snapshot}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Protected module loader (index admin) ===
@app.post("/api/load-protected-module")
async def load_protected_module(request: Request):
    data = await request.json()
    password = data.get("password")
    module_file = data.get("module")

    # Password check
    if password != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Resolve path to project root and target HTML file in grill/
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        full_path = os.path.join(project_root, "grill", module_file)

        print("🔍 Attempting to load:", full_path)
        print("📂 File exists:", os.path.isfile(full_path))

        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"❌ Module file not found at path: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        return HTMLResponse(content=html_content, status_code=200)

    except Exception as e:
        print(f"💥 Error loading module HTML: {e}")
        raise HTTPException(status_code=500, detail="Failed to load module HTML")


# ====== Order form endpoint (Mailgun) ======
MAILGUN_API_KEY  = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN   = os.getenv("MAILGUN_DOMAIN")            # e.g. mg.candooculture.com
MAILGUN_SENDER   = os.getenv("MAILGUN_SENDER")            # e.g. orders@candooculture.com
MAILGUN_API_BASE = os.getenv("MAILGUN_API_BASE", "https://api.mailgun.net")  # set to https://api.eu.mailgun.net if EU
ORDER_NOTIFY     = os.getenv("ORDER_NOTIFY")              # optional internal recipient (e.g. aaron@...)

class OrderPayload(BaseModel):
    form: Dict
    signature_png: str
    pdf_base64: str
    pdf_sha256_b64: str
    user_agent: Optional[str] = None
    tz: Optional[str] = None

def _esc(s: str) -> str:
    return (str(s).replace("&","&amp;").replace("<","&lt;")
                 .replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;"))

@app.post("/api/order-sign")
async def order_sign(payload: OrderPayload):
    # Env guard
    if not (MAILGUN_API_KEY and MAILGUN_DOMAIN and MAILGUN_SENDER):
        raise HTTPException(status_code=500, detail="Mailgun not configured")

    # Basic field checks
    f = payload.form or {}
    required = ["company","abn","name","title","email","phone","initial_users","start_date"]
    for k in required:
        if not str(f.get(k, "")).strip():
            raise HTTPException(status_code=422, detail=f"Missing field: {k}")

    # Verify PDF integrity
    pdf_bytes = base64.b64decode(payload.pdf_base64)
    sha_b64 = base64.b64encode(hashlib.sha256(pdf_bytes).digest()).decode()
    if sha_b64 != payload.pdf_sha256_b64:
        raise HTTPException(status_code=400, detail="PDF hash mismatch")

    # Email body
    plan = f.get("plan_tier", "Basic")
    bill = f.get("billing_frequency", "Monthly")
    html = f"""
      <div style="font-family:Montserrat,Arial,sans-serif;line-height:1.55;color:#0b1a21">
        <h2 style="margin:0 0 8px">Candoo Culture – Order Form</h2>
        <p>Thanks for your order. A copy of the signed PDF is attached.</p>
        <h3 style="margin:16px 0 6px">Summary</h3>
        <table style="border-collapse:collapse">
          <tbody>
            <tr><td><strong>Company</strong></td><td style="padding-left:10px">{_esc(f['company'])}</td></tr>
            <tr><td><strong>ABN/ACN</strong></td><td style="padding-left:10px">{_esc(f['abn'])}</td></tr>
            <tr><td><strong>Signer</strong></td><td style="padding-left:10px">{_esc(f['name'])} ({_esc(f['title'])})</td></tr>
            <tr><td><strong>Email</strong></td><td style="padding-left:10px">{_esc(f['email'])}</td></tr>
            <tr><td><strong>Phone</strong></td><td style="padding-left:10px">{_esc(f['phone'])}</td></tr>
            <tr><td><strong>Plan Tier</strong></td><td style="padding-left:10px">{_esc(plan)}</td></tr>
            <tr><td><strong>Billing</strong></td><td style="padding-left:10px">{_esc(bill)}</td></tr>
            <tr><td><strong>Initial Users</strong></td><td style="padding-left:10px">{_esc(f['initial_users'])}</td></tr>
            <tr><td><strong>Start Date</strong></td><td style="padding-left:10px">{_esc(f['start_date'])}</td></tr>
          </tbody>
        </table>
        <p style="margin-top:16px;font-size:12px;color:#445a68">UA: {_esc(payload.user_agent or '')}</p>
      </div>
    """

    # Send to customer + internal
    to_list = [str(f["email"])]
    data = {
        "from": f"Candoo Culture <{MAILGUN_SENDER}>",
        "to": to_list,
        "subject": f"Candoo Order – {f['company']}",
        "html": html,
        "h:Reply-To": "aaron@candooculture.com",
    }
    if ORDER_NOTIFY:
        data["bcc"] = [ORDER_NOTIFY]
    else:
        data["bcc"] = [MAILGUN_SENDER]

    files = [
        ("attachment", ("Candoo-Order.pdf", pdf_bytes, "application/pdf")),
    ]

    r = requests.post(
        f"{MAILGUN_API_BASE}/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data=data,
        files=files,
        timeout=20,
    )

    if r.status_code >= 300:
        raise HTTPException(status_code=502, detail=f"Mailgun error: {r.text}")

    msg_id = r.json().get("id") if "application/json" in r.headers.get("content-type","") else None
    return {"ok": True, "id": msg_id}


# === Profit Report (email) ===
def _fmt(n):
    try:
        return format_dollars(n)
    except Exception:
        return "$N/A"

def render_profit_report_html(recipient: str, payload: dict, result: dict) -> str:
    period   = (payload or {}).get("period") or "This Period"
    inputs   = (payload or {}).get("inputs")   or {}
    savings  = (payload or {}).get("savings")  or {}
    scenarios= (payload or {}).get("scenarios")or {}
    results  = (result  or {}).get("results")  or {}
    computed = (result  or {}).get("computed") or {}

    # Pull flags outside the f-string (avoids any odd brace parsing)
    apply_fixes = bool(scenarios.get("applyFixes"))
    apply_ors   = bool(scenarios.get("applyORS"))

    # Unpack numbers defensively
    gp_now = (results.get("now") or {}).get("gross")
    np_now = (results.get("now") or {}).get("net")
    np_fix = (results.get("fixes") or {}).get("net")
    d_fix  = (results.get("fixes") or {}).get("delta_vs_now")
    np_ors = (results.get("ors") or {}).get("net")
    d_ors  = (results.get("ors") or {}).get("delta_vs_now")

    total_savings = computed.get("totalSavings", 0.0)
    ors_risk      = computed.get("orsEbitdaAtRisk", 0.0)

    # Build HTML (escape CSS braces with doubled {{ }})
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Profit Potential – {period}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: "Montserrat", Arial, sans-serif; color:#0b1a21; max-width:720px; margin:0 auto; padding:28px; line-height:1.55; }}
    h2 {{ margin:0 0 8px; }}
    h3 {{ margin:22px 0 8px; border-bottom:1px solid #e5ecef; padding-bottom:6px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:8px 6px; border-bottom:1px solid #edf2f5; text-align:right; }}
    th:first-child, td:first-child {{ text-align:left; }}
    .muted {{ color:#5a6b75; font-size:13px; }}
    .pos {{ color:#0aa; font-weight:600; }}
    .neg {{ color:#c33; font-weight:600; }}
    .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#f2f7f9; font-size:12px; color:#335; }}
  </style>
</head>
<body>
  <h2>Profit Potential – {period}</h2>
  <p class="muted">Critical when selling the business — EBITDA strength and operational risk directly shape both the valuation multiple and perceived risk.</p>

  <h3>Current Financials</h3>
  <table>
    <tbody>
      <tr><td>Revenue</td><td>{_fmt(inputs.get("revenue"))}</td></tr>
      <tr><td>COGS</td><td>{_fmt(inputs.get("cogs"))}</td></tr>
      <tr><td>Operating Expenses</td><td>{_fmt(inputs.get("opex"))}</td></tr>
      <tr><td><strong>Gross Profit (Now)</strong></td><td><strong>{_fmt(gp_now)}</strong></td></tr>
      <tr><td><strong>Net Profit (Now)</strong></td><td><strong>{_fmt(np_now)}</strong></td></tr>
    </tbody>
  </table>

  <h3>Fixable Savings (from Toolbox)</h3>
  <table>
    <thead><tr><th>Driver</th><th>Amount</th></tr></thead>
    <tbody>
      <tr><td>Payroll Waste</td><td>{_fmt(savings.get("payroll"))}</td></tr>
      <tr><td>Customer Churn</td><td>{_fmt(savings.get("churn"))}</td></tr>
      <tr><td>Leadership Drag</td><td>{_fmt(savings.get("leadership"))}</td></tr>
      <tr><td>Workforce Productivity</td><td>{_fmt(savings.get("workforce"))}</td></tr>
      <tr><td>Productivity Deep Dive</td><td>{_fmt(savings.get("deepDive"))}</td></tr>
      <tr><td><strong>Total Fixable Savings</strong></td><td><strong>{_fmt(total_savings)}</strong></td></tr>
    </tbody>
  </table>

  <h3>Operational Risk (ORS)</h3>
  <p class="muted">EBITDA at risk if operational issues persist.</p>
  <table>
    <tbody>
      <tr><td><strong>ORS – EBITDA at Risk</strong></td><td><strong>{_fmt(ors_risk)}</strong></td></tr>
    </tbody>
  </table>

  <h3>Scenario Comparison</h3>
  <table>
    <thead><tr><th>Scenario</th><th>Net Profit</th><th>Δ vs Now</th></tr></thead>
    <tbody>
      <tr><td>Now</td><td>{_fmt(np_now)}</td><td class="muted">–</td></tr>
      <tr><td>Fix Inefficiencies <span class="pill">applyFixes={str(apply_fixes).lower()}</span></td>
          <td>{_fmt(np_fix)}</td>
          <td>{('<span class="pos">+' if (d_fix or 0) >= 0 else '<span class="neg">') + _fmt(d_fix) + '</span>'}</td></tr>
      <tr><td>Eliminate ORS Risk <span class="pill">applyORS={str(apply_ors).lower()}</span></td>
          <td>{_fmt(np_ors)}</td>
          <td>{('<span class="pos">+' if (d_ors or 0) >= 0 else '<span class="neg">') + _fmt(d_ors) + '</span>'}</td></tr>
    </tbody>
  </table>

  <p class="muted" style="margin-top:18px">All amounts in AUD. Sent to {recipient}.</p>
  <p class="muted">Generated by the Candoo Culture Profit Engine • https://www.candooculture.com</p>
</body>
</html>"""


@app.post("/send-profit-report")
async def send_profit_report(request: Request):
    """
    Accepts: { "email": "user@...", "payload": { period, inputs{}, savings{}, ors{}, scenarios{} } }
    Recomputes results server-side and emails a nicely formatted summary via Mailgun.
    """
    try:
        body = await request.json()
        recipient = str(body.get("email", "")).strip()
        payload = body.get("payload") or {}

        if "@" not in recipient:
            raise HTTPException(status_code=400, detail="Invalid recipient email")

        # Build request model & compute server-side (trust but verify)
        try:
            profit_req = ProfitRequest(**payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Bad payload: {e}")

        result = compute_projection(profit_req).model_dump()

        # Subject
        period = payload.get("period")
        subject = f"Profit Potential – {period}" if period else "Profit Potential Summary"

        # Mailgun env
        mg_api_key = os.getenv("MAILGUN_API_KEY")
        mg_domain  = os.getenv("MAILGUN_DOMAIN")
        mg_sender  = os.getenv("MAILGUN_SENDER")
        if not all([mg_api_key, mg_domain, mg_sender]):
            raise HTTPException(status_code=500, detail="Missing Mailgun environment variables")

        html = render_profit_report_html(recipient, payload, result)

        # Send (same pattern as /send-risk-report)
        r = requests.post(
            f"https://api.mailgun.net/v3/{mg_domain}/messages",
            auth=("api", mg_api_key),
            data={
                "from": f"Candoo Culture Reports <{mg_sender}>",
                "to": [recipient],
                "bcc": ["aaron@candooculture.com"],
                "subject": subject,
                "html": html
            },
            timeout=20
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"Mailgun error: {r.text}")

        # Optional API response snapshot
        snapshot = {
            "report_id": str(uuid4()),
            "email": recipient,
            "snapshot_at": pd.Timestamp.utcnow().isoformat() + "Z",
            "version": "profit-snapshot-1",
            "currency": "AUD",
            "payload": payload,
            "computed": result.get("computed"),
            "results": result.get("results"),
        }

        return {"success": True, "message": "Profit report sent.", "snapshot": snapshot}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
