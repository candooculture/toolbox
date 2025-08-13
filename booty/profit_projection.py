# booty/profit_projection.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/profit", tags=["profit-projection"])

# ---------- Models ----------


class Savings(BaseModel):
    payroll: float = 0
    churn: float = 0
    workforce: float = 0
    deepDive: float = 0
    leadership: float = 0


class Inputs(BaseModel):
    revenue: Optional[float] = Field(
        default=None, description="Revenue for the period")
    cogs:    Optional[float] = Field(
        default=None, description="Cost of goods sold")
    opex:    Optional[float] = Field(
        default=None, description="Operating expenses excluding COGS")
    grossNow: Optional[float] = Field(
        default=None, description="If known; otherwise computed as revenue - cogs")
    netNow:   Optional[float] = Field(
        default=None, description="If known; otherwise computed as gross - opex")


class Scenarios(BaseModel):
    applyFixes: bool = True
    applyORS:   bool = True


class ProfitRequest(BaseModel):
    period: Optional[str] = None
    inputs: Inputs
    savings: Savings = Savings()
    ors: dict = Field(default_factory=lambda: {"ebitdaAtRisk": 0})
    scenarios: Scenarios = Scenarios()


class ProfitScenario(BaseModel):
    gross: float
    net: float
    delta_vs_now: float


class ProfitResponse(BaseModel):
    period: Optional[str]
    computed: dict
    results: dict

# ---------- Logic ----------


def _safe(n: Optional[float]) -> float:
    try:
        return float(n) if n is not None else 0.0
    except Exception:
        return 0.0


def compute_now(i: Inputs) -> tuple[Optional[float], float]:
    rev = i.revenue
    cogs = i.cogs
    opex = i.opex

    gp = i.grossNow
    np = i.netNow

    if gp is None and rev is not None and cogs is not None:
        gp = rev - cogs
    if np is None:
        if gp is not None and opex is not None:
            np = gp - opex
        else:
            # Last resort: if user only gave netNow earlier, keep it; else zero
            np = 0.0 if np is None else np
    return gp, float(np)


def compute_projection(req: ProfitRequest) -> ProfitResponse:
    gp_now, np_now = compute_now(req.inputs)
    gp_now = 0.0 if gp_now is None else float(gp_now)

    total_fixes = (
        _safe(req.savings.payroll)
        + _safe(req.savings.churn)
        + _safe(req.savings.workforce)
        + _safe(req.savings.deepDive)
        + _safe(req.savings.leadership)
    )
    ors_risk = _safe(req.ors.get("ebitdaAtRisk", 0))

    use_fixes = bool(req.scenarios.applyFixes)
    use_ors = bool(req.scenarios.applyORS)

    # Scenarios
    np_fix = np_now + (total_fixes if use_fixes else 0.0)
    np_ors = np_now + (ors_risk if use_ors else 0.0)
    np_best = np_now + (total_fixes if use_fixes else 0.0) + \
        (ors_risk if use_ors else 0.0)

    results = {
        "now":    ProfitScenario(gross=gp_now, net=np_now, delta_vs_now=0.0).model_dump(),
        "fixes":  ProfitScenario(gross=gp_now, net=np_fix, delta_vs_now=np_fix - np_now).model_dump(),
        "ors":    ProfitScenario(gross=gp_now, net=np_ors, delta_vs_now=np_ors - np_now).model_dump(),
        "best":   ProfitScenario(gross=gp_now, net=np_best, delta_vs_now=np_best - np_now).model_dump(),
    }

    computed = {
        "totalSavings": total_fixes,
        "orsEbitdaAtRisk": ors_risk,
        "applyFixes": use_fixes,
        "applyORS": use_ors,
        "gpNow": gp_now,
        "npNow": np_now,
    }

    return ProfitResponse(period=req.period, computed=computed, results=results)

# ---------- Routes ----------


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/compute", response_model=ProfitResponse)
def compute(req: ProfitRequest):
    try:
        return compute_projection(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
