from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    x: float
    y: float


class HazardZone(BaseModel):
    name: str
    center: Coordinate
    radius: float
    severity: str
    intensity: int
    note: str


class SafeZone(BaseModel):
    id: str
    name: str
    address: str
    zone_type: str
    capacity: int
    available_capacity: int
    contact: str
    location: Coordinate
    facilities: list[str] = Field(default_factory=list)
    distance_km: float = 0.0
    safety_score: float = 0.0
    notes: list[str] = Field(default_factory=list)


class EvacuationRoute(BaseModel):
    safe_zone_id: str
    safe_zone_name: str
    distance_km: float
    travel_time_min: int
    safety_score: float
    notes: list[str] = Field(default_factory=list)
    path: list[Coordinate] = Field(default_factory=list)


class RiskSnapshot(BaseModel):
    disaster_type: str
    risk_score: int
    probability_score: int
    confidence_score: int
    severity_level: str
    status: str


class SituationSummary(BaseModel):
    incident_summary: str
    threat_assessment: str
    current_incident_status: str
    population_at_risk: int
    infrastructure_damage_estimate: str
    hospitals_at_risk: int
    schools_at_risk: int
    roads_blocked: int
    weather_and_hazard_conditions: str
    affected_regions: list[str] = Field(default_factory=list)


class CitizenGuidance(BaseModel):
    immediate_actions: list[str] = Field(default_factory=list)
    before_disaster: list[str] = Field(default_factory=list)
    during_disaster: list[str] = Field(default_factory=list)
    after_disaster: list[str] = Field(default_factory=list)
    emergency_contacts: dict[str, str] = Field(default_factory=dict)
    supply_checklist: list[str] = Field(default_factory=list)
    answer_cards: list[dict[str, str]] = Field(default_factory=list)


class AgentTrace(BaseModel):
    agent: str
    summary: str
    tools_used: list[str] = Field(default_factory=list)
    latency_ms: int


class DashboardMetrics(BaseModel):
    population_at_risk: int
    predicted_damage_index: int
    response_status: str
    ambulances_ready: int
    rescue_teams_ready: int
    shelters_ready: int


class IntegrationStatus(BaseModel):
    server_name: str
    transport: str
    connected: bool
    tools: list[str] = Field(default_factory=list)
    detail: str = ""


class AnalysisRequest(BaseModel):
    scenario_id: str | None = None
    location_name: str
    disaster_type: str
    current_location: Coordinate
    rainfall_mm: int
    wind_kph: int
    temperature_c: int
    river_level: float
    air_quality_index: int
    social_signal_level: int
    news_signal_level: int
    population_density: int
    vulnerable_population_percent: int


class AnalysisReport(BaseModel):
    report_id: str
    generated_at: datetime
    generated_by: str
    request: AnalysisRequest
    executive_summary: str
    risk_assessment: RiskSnapshot
    situation_analysis: SituationSummary
    safe_zones: list[SafeZone] = Field(default_factory=list)
    evacuation_routes: list[EvacuationRoute] = Field(default_factory=list)
    precautionary_measures: CitizenGuidance
    emergency_contacts: dict[str, str] = Field(default_factory=dict)
    emergency_supply_checklist: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    resource_allocation_suggestions: list[str] = Field(default_factory=list)
    dashboard_metrics: DashboardMetrics
    agent_trace: list[AgentTrace] = Field(default_factory=list)
    hazard_zones: list[HazardZone] = Field(default_factory=list)
    map_layers: dict[str, Any] = Field(default_factory=dict)
    data_sources_used: list[str] = Field(default_factory=list)
    mcp_tools_utilized: list[str] = Field(default_factory=list)
    integration_status: list[IntegrationStatus] = Field(default_factory=list)
