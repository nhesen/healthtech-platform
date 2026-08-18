"""Central, safety-first AI adapter. Domain rules stay outside this module."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from typing import Any

from pydantic import BaseModel, Field

log = logging.getLogger("healthtech.ai")

SAFETY_PROMPT = """You are a HealthTech decision-support assistant. Use only supplied data. Never diagnose, prescribe, invent facts, change numbers, authorize access, or change operational state. Use cautious language: clinical review may be appropriate. Return valid JSON only."""

class AIResult(BaseModel):
    source: str
    feature: str
    content: dict[str, Any]
    fallback_used: bool = False

class BriefContent(BaseModel):
    summary: str
    important_history: list[str] = []
    relevant_metrics: list[dict[str, Any]] = []
    medications: list[dict[str, Any]] = []
    allergies: list[dict[str, Any]] = []
    warnings: list[str] = []
    suggested_review_points: list[str] = []

class MockAIProvider:
    """High-quality deterministic demo responses generated only from supplied context."""
    def generate(self, feature: str, context: dict[str, Any]) -> dict[str, Any]:
        if feature == "patient_brief":
            metrics = context.get("relevant_metrics", [])
            return BriefContent(
                summary="Patient presents for endocrinology review following a persistent upward HbA1c trend. This is decision support and requires clinician review.",
                important_history=["HbA1c increased from 5.4 to 6.3 between 2024 and 2026"], relevant_metrics=metrics,
                medications=context.get("medications", []), allergies=context.get("allergies", []),
                warnings=["Penicillin allergy recorded in 2024"] if context.get("allergies") else [],
                suggested_review_points=["Review metabolic trend and current medication details."]
            ).model_dump()
        if feature == "lab_explanation":
            trend=context["trend"]
            return {"title":f"{trend['metric']} has {trend['trend']} over time", "explanation":f"The latest value is {trend['current']}, compared with {trend.get('previous', 'an earlier value')}. This is a measured change, not a diagnosis.", "suggested_action":"An endocrinology review may be appropriate."}
        if feature == "specialty":
            return {"specialty":context["specialty"],"reason":context["reason"],"type":"suggested_review"}
        if feature == "consultation_draft":
            text=context.get("notes", "")
            return {"chief_complaint":"Not available","history":text or "Not available","relevant_findings":[],"assessment_draft":"Draft for clinician review; no diagnosis generated.","plan_draft":"Document clinician-reviewed next steps."}
        if feature == "missing_information":
            return {"missing_items":[{"field":"documentation","message":item,"severity":"review"} for item in context.get("missing",[])]}
        if feature == "record_conflict":
            return {"explanation":"These records contain inconsistent information and should be reviewed by a clinician."}
        if feature == "post_discharge":
            return {"summary":"Your reported symptoms have worsened over recent check-ins. A clinical review may be appropriate."}
        if feature == "hospital_recommendation":
            return {"title":context["title"],"reason":context["reason"],"expected_impact":context["impact"]}
        return {"summary":"AI support is available with clinician review."}

class LiveAIProvider:
    def __init__(self) -> None:
        self.key=os.getenv("AI_API_KEY", ""); self.model=os.getenv("AI_MODEL", "gpt-4o-mini"); self.base=os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
    def generate(self, feature: str, context: dict[str, Any]) -> dict[str, Any]:
        if not self.key: raise RuntimeError("AI_API_KEY is not configured")
        body={"model":self.model,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":SAFETY_PROMPT},{"role":"user","content":f"Feature: {feature}\nContext: {json.dumps(context)}"}]}
        request=urllib.request.Request(f"{self.base}/chat/completions",data=json.dumps(body).encode(),headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            payload=json.loads(response.read()); return json.loads(payload["choices"][0]["message"]["content"])

class AIService:
    def __init__(self) -> None: self.live=LiveAIProvider(); self.mock=MockAIProvider()
    def generate(self, feature: str, context: dict[str, Any]) -> AIResult:
        started=time.perf_counter()
        try:
            if os.getenv("AI_PROVIDER", "mock").lower() == "openai":
                content=self.live.generate(feature,context)
                if not isinstance(content,dict): raise ValueError("AI returned invalid JSON")
                log.info("feature=%s provider=live duration=%.3f",feature,time.perf_counter()-started)
                return AIResult(source="live_ai",feature=feature,content=content)
        except Exception as exc:
            log.warning("feature=%s provider=live failed=%s fallback=true",feature,type(exc).__name__)
        return AIResult(source="fallback",feature=feature,content=self.mock.generate(feature,context),fallback_used=True)

ai_service=AIService()
