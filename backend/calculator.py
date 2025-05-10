import pandas as pd

# === 1. LOAD INDUSTRY BENCHMARKS ===


def load_benchmark_data():
    df = pd.read_csv("benchmarks/final_cleaned_benchmarks_with_certainty.csv")
    df.set_index("Industry", inplace=True)
    return df

# === 2. LOOKUP ===


def industry_benchmarks(industry):
    df = load_benchmark_data()
    if industry not in df.index:
        raise ValueError(f"Industry '{industry}' not found in benchmarks.")
    return df.loc[industry]

# === 3. BENCHMARK MESSAGES ===


def compare_to_benchmark(industry, improvement_rate):
    b = industry_benchmarks(industry)
    return [
        f"{industry} typically has an employee churn rate of {b.get('Employee Churn Rate (%) (Value)', 'N/A')}%.",
        f"Inefficiency rate in {industry} averages {b.get('Process Inefficiency Rate (%) (Value)', 'N/A')}%.",
        f"You're targeting a {improvement_rate}% improvement."
    ]

# === 4. TEAM EFFICIENCY ===


def calculate_efficiency_loss_and_roi(data):
    b = industry_benchmarks(data.industry)
    monthly_salary = data.avg_salary / 12
    turnover_rate = b.get('Employee Churn Rate (%) (Value)', 0) / 100
    inefficiency_rate = b.get('Process Inefficiency Rate (%) (Value)', 0) / 100
    replacement_cost = b.get('Employee Replacement Cost (AUD) (Value)', 50000)
    intervention_cost = data.total_employees * 7.5

    inefficiency_loss = data.total_employees * monthly_salary * inefficiency_rate
    improved_cost = inefficiency_loss * (1 - data.improvement_rate / 100)
    savings = inefficiency_loss - improved_cost

    churn_loss = (data.total_employees * turnover_rate * replacement_cost) / 12
    total_loss = inefficiency_loss + churn_loss

    return_per_dollar = savings / intervention_cost if intervention_cost else 0
    payback_days = round((intervention_cost / savings) * 30) if savings else 0
    monthly_roi = return_per_dollar * 100

    return {
        "formatted_labels": {
            "Employee Churn Cost": f"AUD ${round(churn_loss):,}",
            "Payroll Inefficiency Cost": f"AUD ${round(inefficiency_loss):,}",
            "Total Monthly Loss": f"AUD ${round(total_loss):,}",
            "Improved Inefficiency Cost": f"AUD ${round(improved_cost):,}",
            "Direct Savings from Initiative": f"AUD ${round(savings):,}",
            "Monthly ROI": f"{round(monthly_roi, 1)}%",
            "Return Per Dollar": f"${round(return_per_dollar, 2)}",
            "Payback Period": f"{payback_days} days"
        },
        "benchmark_messages": compare_to_benchmark(data.industry, data.improvement_rate)
    }

# === 5. CUSTOMER CHURN ===


def calculate_customer_churn_loss(data):
    b = industry_benchmarks(data.industry)
    churn_rate = data.churn_rate / 100
    improved_rate = churn_rate * (1 - data.desired_improvement / 100)

    revenue_loss = data.num_customers * churn_rate * data.avg_revenue
    replacement_cost = data.num_customers * churn_rate * data.cac
    potential_gain = data.num_customers * \
        (churn_rate - improved_rate) * data.avg_revenue

    return {
        "revenue_loss": round(revenue_loss),
        "replacement_cost": round(replacement_cost),
        "potential_gain": round(potential_gain),
        "benchmark_message": f"Your churn rate compared to {data.industry} industry benchmark ({b.get('Customer Churn Rate (%) (Value)', 'N/A')}%)."
    }

# === 6. LEADERSHIP DRAG ===


def calculate_leadership_drag_loss(data):
    b = industry_benchmarks(data.industry)
    drag_rate = data.leadership_drag / 100
    monthly_loss = (data.avg_salary * drag_rate * data.total_employees) / 12
    annual_loss = data.avg_salary * drag_rate * data.total_employees
    industry_avg = b.get('Leadership Drag Impact (%) (Value)', 10.0)

    excess_drag = max(0, data.leadership_drag - industry_avg) / 100
    excess_monthly_cost = round(
        (data.avg_salary * data.total_employees * excess_drag) / 12)

    return {
        "formatted_labels": {
            "Monthly Leadership Drag Loss": f"AUD ${round(monthly_loss):,}",
            "Annual Leadership Drag Loss": f"AUD ${round(annual_loss):,}",
            "Excess Drag Monthly Cost": f"AUD ${excess_monthly_cost:,}"
        },
        "benchmark_messages": [
            f"Your leadership drag factor of {data.leadership_drag}% compared to {data.industry} industry average of {industry_avg}%"
        ]
    }

# === 7. WORKFORCE PRODUCTIVITY ===


def calculate_productivity_metrics(data):
    b = industry_benchmarks(data.industry)
    total_target_hours = data.total_employees * data.target_hours_per_employee
    lost_hours = data.absenteeism_days * 7.6
    extra_hours = 0.05 * total_target_hours

    revenue_per_employee = (
        data.total_revenue / data.total_employees
        if data.total_employees else 0
    )
    payroll_efficiency = (
        (data.total_revenue / data.payroll_cost) * 100
        if data.payroll_cost else 0
    )
    utilisation_rate = (
        (data.productive_hours / total_target_hours) * 100
        if total_target_hours else 0
    )
    absenteeism_rate = (
        (lost_hours / total_target_hours) * 100
        if total_target_hours else 0
    )
    overtime_rate = (
        (data.overtime_hours / data.productive_hours) * 100
        if data.productive_hours else 0
    )
    revenue_per_hour = (
        data.total_revenue / data.productive_hours
        if data.productive_hours else 0
    )
    opportunity_gain = extra_hours * revenue_per_hour

    return {
        "formatted_labels": {
            "revenue_per_employee": f"AUD ${revenue_per_employee:,.2f}",
            "payroll_efficiency": f"{payroll_efficiency:.1f}%",
            "utilisation_rate": f"{utilisation_rate:.1f}%",
            "absenteeism_rate": f"{absenteeism_rate:.1f}%",
            "overtime_rate": f"{overtime_rate:.1f}%",
            "opportunity_gain": f"AUD ${opportunity_gain:,.2f}"
        },
        "benchmark_messages": [
            f"Target utilisation boost of 5% across {data.total_employees} employees."
        ]
    }

# === 8. PRODUCTIVITY DEEP DIVE ===


def calculate_productivity_metrics_dive(data):
    b = industry_benchmarks(data.industry)
    monthly_salary = data.avg_salary / 12
    target_hours = b.get("Target Hours per Employee (Value)", 160)
    utilisation_benchmark = b.get("Utilisation Rate (%) (Value)", 75)
    absenteeism_benchmark = b.get("Absenteeism Days per Month (Value)", 4)
    overtime_benchmark = b.get("Overtime Dependency (%) (Value)", 10)
    output_per_employee = b.get(
        "Output per Employee (AUD/month) (Value)", 12000)

    absenteeism_days = data.absenteeism_days or absenteeism_benchmark
    avg_hours = data.avg_hours or target_hours

    utilisation_gap = max(0, (target_hours - avg_hours) / target_hours)
    underutilisation_cost = utilisation_gap * \
        output_per_employee * data.total_employees
    avg_daily_salary = data.avg_salary / 260
    absenteeism_cost = absenteeism_days * avg_daily_salary

    return {
        "formatted_labels": {
            "Absenteeism Cost": f"AUD ${round(absenteeism_cost):,}/month",
            "Utilisation Gap": f"{round(utilisation_gap * 100, 1)}%",
            "Output Loss from Under-utilisation": f"AUD ${round(underutilisation_cost):,}/month",
            "Output per Employee": f"AUD ${round(output_per_employee):,}/month"
        },
        "benchmark_messages": [
            f"Target Hours: {target_hours} hrs/month",
            f"Utilisation Benchmark: {utilisation_benchmark}%",
            f"Absenteeism Benchmark: {absenteeism_benchmark} days/month",
            f"Overtime Dependency Benchmark: {overtime_benchmark}%",
        ],
        "straight_talk": f"These hidden gaps are costing up to AUD ${round(absenteeism_cost + underutilisation_cost):,} per month in missed productivity."
    }

# === 9. EXPORT FOR ADMIN PANEL ===


def get_industry_benchmarks():
    return load_benchmark_data().to_dict(orient="index")

# === 10. ROUTE ALIASES FOR MAIN ===


run_payroll_waste = calculate_efficiency_loss_and_roi
run_customer_churn = calculate_customer_churn_loss
run_leadership_drag = calculate_leadership_drag_loss
run_workforce_productivity = calculate_productivity_metrics
run_productivity_dive = calculate_productivity_metrics_dive
