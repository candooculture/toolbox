from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
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
import pandas as pd
import os
import requests

app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(admin_router)

# === Input Models ===

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

# === Module Calculators ===

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

# === Email Report Builder ===

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
      <style>
        body {{
          font-family: Arial, sans-serif;
          background-color: #ffffff;
          color: #333333;
          max-width: 640px;
          margin: 0 auto;
          padding: 30px 20px;
          line-height: 1.6;
        }}
        h2 {{
          text-align: center;
          color: #111111;
          font-size: 24px;
          margin-bottom: 10px;
        }}
        h3 {{
          font-size: 20px;
          border-bottom: 1px solid #ddd;
          padding-bottom: 6px;
          margin-top: 30px;
          color: #000;
        }}
        h4 {{
          font-size: 16px;
          color: #555;
          margin-top: 24px;
          margin-bottom: 6px;
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
        }}
        em {{
          font-style: italic;
          color: #777;
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

      <!-- TOP CTA -->
      <div class="cta">
        <p>Ready to take action? <a href="mailto:aaron@candooculture.com" target="_blank">Book a 15-minute strategy call</a> to unpack your results.</p>
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

      <!-- MODULE BREAKDOWN -->
      <h3>📋 Risk Breakdown</h3>
      <ul>
        <li><strong>Payroll Waste:</strong> {format_dollars(data.get("module_breakdown", {}).get("Payroll Waste"))}</li>
        <li><strong>Customer Churn:</strong> {format_dollars(data.get("module_breakdown", {}).get("Customer Churn"))}</li>
        <li><strong>Leadership Drag:</strong> {format_dollars(data.get("module_breakdown", {}).get("Leadership Drag"))}</li>
        <li><strong>Workforce Productivity:</strong> {format_dollars(data.get("module_breakdown", {}).get("Workforce Productivity"))}</li>
        <li><strong>Process Gaps:</strong> {format_dollars(data.get("module_breakdown", {}).get("Process Gaps (Deep Dive)"))}</li>
      </ul>

      <!-- INPUTS SUMMARY -->
      <h3>🧠 Inputs Summary</h3>
      <p><em>Please note: This is a direct summary of the inputs used in your calculation. Some values may reflect benchmark data based on your selected industry.</em></p>

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

      <h4>Workforce & Operations</h4>
      <ul>
        <li><strong>Leadership Drag:</strong> {data.get("leadership_drag", "N/A")}%</li>
        <li><strong>Productive Hours:</strong> {data.get("productive_hours", "N/A")}</li>
        <li><strong>Target Hours per Employee:</strong> {data.get("target_hours_per_employee", "N/A")}</li>
        <li><strong>Average Weekly Hours:</strong> {data.get("avg_hours", "N/A")}</li>
        <li><strong>Overtime Hours:</strong> {data.get("overtime_hours", "N/A")}</li>
        <li><strong>Absenteeism Days:</strong> {data.get("absenteeism_days", "N/A")}</li>
      </ul>

      <h4>Calculated & Efficiency Factors</h4>
      <ul>
        <li><strong>Payroll Cost:</strong> {format_dollars(data.get("payroll_cost"))}</li>
        <li><strong>Improvement Rate:</strong> {data.get("improvement_rate", "N/A")}%</li>
      </ul>

      <!-- BOTTOM CTA -->
      <div class="cta">
        <p>Want to dive deeper? <a href="tel:+61455460580" target="_blank">Call now</a> to chat with our team.</p>
      </div>

      <p class="footer-note">
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

        # === Run ORS Calculation and inject results ===
        try:
            ors_result = run_operational_risk(RiskInput(**data))
            data.update(ors_result)
        except Exception as calc_error:
            print("ORS calculation failed:", calc_error)

        # === Mailgun ===
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
                "subject": data["subject"],
                "html": render_report_html(data)
            }
        )

        if response.status_code != 200:
            raise Exception(f"Mailgun Error: {response.text}")

        return {"success": True, "message": "Report sent."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
