from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
# No dot-import when same directory level

router = APIRouter()


class DummyInput(BaseModel):
    pass  # Placeholder for future user ID / token logic


@router.post("/run-operational-risk")
def run_operational_risk(_: DummyInput):
    try:
        keys = [
            "payroll-waste-inputs",
            "customer-churn-inputs",
            "leadership-drag-inputs",
            "workforce-productivity-inputs",
            "productivity-dive-inputs"
        ]

        inputs = {k: retrieve_input(k) for k in keys if retrieve_input(k)}

        if not inputs:
            raise HTTPException(
                status_code=400, detail="No module inputs found. Run modules first.")

        score = len(inputs) * 20
        tier = "Low" if score <= 40 else "Moderate" if score <= 80 else "High"

        return {
            "formatted_labels": {
                "Operational Risk Score": f"{score}/100",
                "Risk Tier": tier
            },
            "straight_talk": f"Based on completed modules, your operational risk is rated {tier}."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
