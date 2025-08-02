from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class RiskInput(BaseModel):
    # Payroll Module
    payroll_cost: float = 0
    avg_salary: float = 0
    improvement_rate: float = 0

    # Churn Module
    churn_rate: float = 0
    desired_improvement: float = 0
    cac: float = 0
    avg_revenue: float = 0
    num_customers: int = 0

    # Leadership Module
    leadership_drag: float = 0

    # Workforce Productivity
    total_revenue: float = 0
    productive_hours: float = 0
    target_hours_per_employee: float = 0
    overtime_hours: float = 0

    # Deep Dive
    absenteeism_days: float = 0
    avg_hours: float = 0

    # Shared
    total_employees: int = 0
    industry: str = ""
    ebitda_margin: float = 20.0  # Default if not provided

@router.post("/run-operational-risk")
def run_operational_risk(data: RiskInput):
    try:
        inputs = data.dict()
        print("🔍 ORS Received Payload:", inputs)

        # === Resolve Payroll Cost ===
        payroll_cost = inputs.get("payroll_cost", 0)
        if payroll_cost <= 0:
            # Estimate it if missing
            payroll_cost = inputs["avg_salary"] * inputs["total_employees"]
            print(f"⚠️ Estimated payroll_cost as {payroll_cost} from avg_salary and total_employees")

        # === Baseline EBITDA Calculation ===
        ebitda_value = inputs["total_revenue"] * (inputs["ebitda_margin"] / 100)
        module_losses = {}

        # === Payroll Waste ===
        if inputs["improvement_rate"] > 0:
            module_losses["Payroll Waste"] = round(payroll_cost * (inputs["improvement_rate"] / 100), 2)

        # === Customer Churn ===
        if inputs["churn_rate"] > 0 and inputs["avg_revenue"] > 0 and inputs["num_customers"] > 0:
            churn_loss = inputs["churn_rate"] / 100 * inputs["avg_revenue"] * inputs["num_customers"]
            module_losses["Customer Churn"] = round(churn_loss, 2)

        # === Leadership Drag ===
        if inputs["leadership_drag"] > 0:
            module_losses["Leadership Drag"] = round(payroll_cost * (inputs["leadership_drag"] / 100), 2)

        # === Workforce Productivity ===
        if (
            inputs["productive_hours"] > 0
            and inputs["target_hours_per_employee"] > 0
            and inputs["total_employees"] > 0
        ):
            expected_total_hours = inputs["target_hours_per_employee"] * inputs["total_employees"]
            productivity_gap_pct = 1 - (inputs["productive_hours"] / expected_total_hours)
            productivity_loss = productivity_gap_pct * payroll_cost
            module_losses["Workforce Productivity"] = round(max(productivity_loss, 0), 2)

        # === Process Gaps (Deep Dive) ===
        if inputs["avg_hours"] > 0 and inputs["absenteeism_days"] > 0:
            deep_dive_loss = (inputs["absenteeism_days"] / 20) * inputs["avg_salary"] * inputs["total_employees"]
            module_losses["Process Gaps (Deep Dive)"] = round(deep_dive_loss, 2)

        # === Totals and Risk Score ===
        total_risk = sum(module_losses.values())
        ebitda_risk_pct = round((total_risk / ebitda_value) * 100, 1) if ebitda_value > 0 else 0

        return {
            "ebitda_margin": inputs["ebitda_margin"],
            "ebitda_value": round(ebitda_value, 2),
            "total_risk_dollars": round(total_risk, 2),
            "ebitda_risk_pct": ebitda_risk_pct,
            "module_breakdown": module_losses,
            "summary": f"You're putting {ebitda_risk_pct}% of your profit at risk due to operational inefficiencies.",
            "cta": f"If nothing changes, you'll forfeit ${round(total_risk, 2)} in profit this year."
        }

    except Exception as e:
        print("🔥 ORS Exception:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
