"""
src/agent/prompts.py
Prompt templates for the AI business analyst.
These are the ONLY places where AI prompt text is defined — never in app.py.
"""
from __future__ import annotations

SYSTEM_PROMPT = """You are a professional business analyst assistant.
Your role is to interpret statistical data findings and help business managers understand what the numbers mean.

Rules you must follow at all times:
- Use ONLY the data and statistics provided to you. Do not invent numbers.
- Label possible explanations clearly as hypotheses, not proven facts.
- Never state a correlation as causation.
- Do not fabricate business context that was not provided.
- Write in clear, professional English. No jargon, no filler phrases.
- Keep your analysis concise and actionable.
- If data is insufficient to draw a conclusion, say so explicitly.
- Format your output in the requested sections only.
"""

ANALYSIS_PROMPT_TEMPLATE = """
BUSINESS CONTEXT
================
Business name: {business_name}
Industry: {industry}
Description: {description}
Additional notes: {notes}

KPI SUMMARIES (calculated statistics — treat as ground truth)
=============================================================
{kpi_summaries}

DETECTED ANOMALIES
==================
{anomaly_list}

DATA QUALITY NOTES
==================
{quality_notes}

TASK
====
Produce a structured business analysis with exactly these sections:

1. EXECUTIVE SUMMARY
   Two to four sentences summarising the most important findings.

2. KEY FINDINGS
   Bullet list of the three to six most significant observations. Reference specific numbers.

3. ANOMALIES REQUIRING ATTENTION
   For each anomaly above medium severity: state what happened, when, and what the data shows.
   Label any explanation of cause as a hypothesis.

4. BUSINESS RISKS
   Risks suggested by the data. Clearly state when evidence is limited.

5. OPPORTUNITIES
   Positive trends or improvements visible in the data.

6. RECOMMENDED NEXT STEPS
   Three to five concrete, actionable recommendations for the business manager.

7. QUESTIONS TO INVESTIGATE
   Three to five questions a manager should ask internally to explain the findings.

Do not add any other sections. Do not repeat the raw numbers table.
"""


def build_analysis_prompt(
    business_name: str,
    industry: str,
    description: str,
    notes: str,
    kpi_summaries: str,
    anomaly_list: str,
    quality_notes: str,
) -> str:
    return ANALYSIS_PROMPT_TEMPLATE.format(
        business_name=business_name or "Not specified",
        industry=industry or "Not specified",
        description=description or "Not specified",
        notes=notes or "None",
        kpi_summaries=kpi_summaries,
        anomaly_list=anomaly_list or "No anomalies detected.",
        quality_notes=quality_notes or "No data quality issues.",
    )
