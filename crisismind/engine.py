from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from .data_loader import load_dataset
from .location_data import generate_location_dataset
from .models import (
    AgentTrace,
    AnalysisReport,
    AnalysisRequest,
    CitizenGuidance,
    Coordinate,
    DashboardMetrics,
    EvacuationRoute,
    HazardZone,
    RiskSnapshot,
    SafeZone,
    SituationSummary,
)
from .registry import LocalDatasetRegistry, RegistryProtocol, build_registry


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


MAP_UNIT_KM = 0.22


def distance(a: Coordinate, b: Coordinate) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


class WeatherIntelligenceAgent:
    TOOLS = ["weather.snapshot", "maps.context"]

    def __init__(self, registry: RegistryProtocol, dataset: dict[str, Any]):
        self.registry = registry
        self.dataset = dataset

    def run(self, request: AnalysisRequest) -> tuple[dict[str, Any], list[HazardZone], dict[str, Any]]:
        snapshot = self.registry.weather_snapshot(request)
        map_context = self.registry.map_context()
        template_list = self.dataset["hazard_templates"][request.disaster_type]
        pressure = self._pressure(request)
        hazards: list[HazardZone] = []
        for template in template_list:
            radius = template["base_radius"] + pressure * template["radius_factor"]
            intensity = round(clamp(pressure * 100, 25, 98))
            hazards.append(
                HazardZone(
                    name=template["name"],
                    center=Coordinate(**template["center"]),
                    radius=round(radius, 1),
                    severity=self._severity_label(intensity),
                    intensity=intensity,
                    note=template["note"],
                )
            )
        weather_summary = {
            "summary": (
                f"{request.location_name} is seeing {request.rainfall_mm} mm rainfall, "
                f"{request.wind_kph} kph wind, river level {request.river_level:.1f} m, "
                f"temperature {request.temperature_c} C, and AQI {request.air_quality_index}."
            ),
            "pressure": pressure,
            "snapshot": snapshot,
        }
        return weather_summary, hazards, map_context

    def _pressure(self, request: AnalysisRequest) -> float:
        profiles = {
            "flood": (
                request.rainfall_mm / 250,
                request.river_level / 5,
                request.wind_kph / 160,
                request.social_signal_level / 100,
            ),
            "cyclone": (
                request.wind_kph / 180,
                request.rainfall_mm / 220,
                request.news_signal_level / 100,
                request.vulnerable_population_percent / 100,
            ),
            "heatwave": (
                max(request.temperature_c - 30, 0) / 18,
                request.air_quality_index / 250,
                request.population_density / 100,
                request.vulnerable_population_percent / 100,
            ),
        }
        values = profiles.get(request.disaster_type, profiles["flood"])
        return clamp(sum(values) / len(values), 0.0, 1.0)

    @staticmethod
    def _severity_label(intensity: int) -> str:
        if intensity >= 85:
            return "Critical"
        if intensity >= 70:
            return "Severe"
        if intensity >= 55:
            return "Elevated"
        return "Moderate"


class RiskPredictionAgent:
    TOOLS = ["risk.model", "signals.classifier"]

    def run(self, request: AnalysisRequest, weather_summary: dict[str, Any]) -> RiskSnapshot:
        normalized = {
            "rainfall": clamp(request.rainfall_mm / 250, 0, 1),
            "wind": clamp(request.wind_kph / 180, 0, 1),
            "temperature": clamp(max(request.temperature_c - 20, 0) / 25, 0, 1),
            "river": clamp(request.river_level / 5, 0, 1),
            "aqi": clamp(request.air_quality_index / 300, 0, 1),
            "social": clamp(request.social_signal_level / 100, 0, 1),
            "news": clamp(request.news_signal_level / 100, 0, 1),
            "density": clamp(request.population_density / 100, 0, 1),
            "vulnerable": clamp(request.vulnerable_population_percent / 100, 0, 1),
        }
        weights = {
            "flood": {
                "rainfall": 0.25,
                "river": 0.23,
                "social": 0.09,
                "news": 0.09,
                "density": 0.10,
                "wind": 0.08,
                "vulnerable": 0.10,
                "aqi": 0.03,
                "temperature": 0.03,
            },
            "cyclone": {
                "wind": 0.28,
                "rainfall": 0.18,
                "news": 0.10,
                "social": 0.10,
                "density": 0.10,
                "vulnerable": 0.11,
                "river": 0.05,
                "temperature": 0.04,
                "aqi": 0.04,
            },
            "heatwave": {
                "temperature": 0.32,
                "aqi": 0.16,
                "density": 0.14,
                "vulnerable": 0.13,
                "social": 0.08,
                "news": 0.07,
                "wind": 0.04,
                "rainfall": 0.03,
                "river": 0.03,
            },
        }[request.disaster_type]
        score = round(sum(normalized[name] * weight for name, weight in weights.items()) * 100)
        pressure_bonus = round(weather_summary["pressure"] * 12)
        risk_score = min(score + pressure_bonus, 99)
        confidence = round(
            clamp(
                72
                + (request.social_signal_level + request.news_signal_level) * 0.08
                + request.population_density * 0.06,
                70,
                96,
            )
        )
        probability = round((risk_score * 0.82) + (confidence * 0.18))
        severity, status = self._labels(risk_score)
        return RiskSnapshot(
            disaster_type=request.disaster_type.title(),
            risk_score=risk_score,
            probability_score=probability,
            confidence_score=confidence,
            severity_level=severity,
            status=status,
        )

    @staticmethod
    def _labels(risk_score: int) -> tuple[str, str]:
        if risk_score >= 85:
            return "Critical", "HIGH RISK"
        if risk_score >= 70:
            return "Severe", "ELEVATED ALERT"
        if risk_score >= 55:
            return "Elevated", "WATCHLIST"
        if risk_score >= 35:
            return "Moderate", "MONITOR"
        return "Low", "STABLE"


class SituationAssessmentAgent:
    TOOLS = ["maps.critical_sites"]

    def __init__(self, registry: RegistryProtocol, dataset: dict[str, Any]):
        self.registry = registry
        self.dataset = dataset

    def run(
        self,
        request: AnalysisRequest,
        risk: RiskSnapshot,
        hazards: list[HazardZone],
        map_context: dict[str, Any],
    ) -> SituationSummary:
        regions = map_context["regions"]
        impacted_regions: list[str] = []
        population_at_risk = 0
        for region in regions:
            center = Coordinate(**region["center"])
            if any(distance(center, hazard.center) <= hazard.radius + 8 for hazard in hazards):
                impacted_regions.append(region["name"])
                population_at_risk += region["population"]
        if not impacted_regions:
            primary = max(regions, key=lambda region: region["population"])
            impacted_regions = [primary["name"]]
            population_at_risk = primary["population"]
        critical_sites = self.registry.critical_sites()
        hospitals_at_risk = self._count_sites_in_hazard(critical_sites["hospitals"], hazards)
        schools_at_risk = self._count_sites_in_hazard(critical_sites["schools"], hazards)
        roads_blocked = max(1, round(len(impacted_regions) * (risk.risk_score / 24)))
        damage_label = {
            "Critical": "Widespread urban flooding, utility failures, and transport disruption likely.",
            "Severe": "Localized structural damage and prolonged service interruptions expected.",
            "Elevated": "Targeted neighborhood disruption with manageable infrastructure strain.",
            "Moderate": "Temporary disruption possible with isolated access constraints.",
            "Low": "Minor operational impact likely.",
        }[risk.severity_level]
        incident_summary = (
            f"{risk.disaster_type} conditions detected near {request.location_name}. "
            f"{len(impacted_regions)} regions are exposed, with the heaviest pressure around {impacted_regions[0]}."
        )
        threat_assessment = (
            f"Threat level is {risk.severity_level.lower()} with probability {risk.probability_score}% "
            f"and model confidence {risk.confidence_score}%."
        )
        conditions = (
            f"Signals indicate rainfall {request.rainfall_mm} mm, wind {request.wind_kph} kph, "
            f"temperature {request.temperature_c} C, river level {request.river_level:.1f} m, "
            f"social escalation {request.social_signal_level}/100."
        )
        current_status = {
            "Critical": "Immediate coordinated response recommended within the next 30 minutes.",
            "Severe": "Emergency teams should pre-position and prepare for rapid deployment.",
            "Elevated": "District operations room should stay on active watch and notify shelters.",
            "Moderate": "Keep field teams on standby and continue monitoring signal spikes.",
            "Low": "Maintain routine monitoring cadence.",
        }[risk.severity_level]
        return SituationSummary(
            incident_summary=incident_summary,
            threat_assessment=threat_assessment,
            current_incident_status=current_status,
            population_at_risk=population_at_risk,
            infrastructure_damage_estimate=damage_label,
            hospitals_at_risk=hospitals_at_risk,
            schools_at_risk=schools_at_risk,
            roads_blocked=roads_blocked,
            weather_and_hazard_conditions=conditions,
            affected_regions=impacted_regions,
        )

    @staticmethod
    def _count_sites_in_hazard(sites: list[dict[str, Any]], hazards: list[HazardZone]) -> int:
        count = 0
        for site in sites:
            point = Coordinate(**site["location"])
            if any(distance(point, hazard.center) <= hazard.radius for hazard in hazards):
                count += 1
        return count


class SafeZoneAgent:
    TOOLS = ["maps.shelters", "maps.safe-zone-score"]

    def __init__(self, registry: RegistryProtocol):
        self.registry = registry

    def run(self, request: AnalysisRequest, hazards: list[HazardZone]) -> list[SafeZone]:
        safe_zones: list[SafeZone] = []
        for zone_data in self.registry.shelters():
            zone_payload = dict(zone_data)
            zone_payload["location"] = Coordinate(**zone_data["location"])
            zone = SafeZone(**zone_payload)
            nearest_hazard_gap = min(
                max(distance(zone.location, hazard.center) - hazard.radius, 0) for hazard in hazards
            )
            capacity_ratio = zone.available_capacity / max(zone.capacity, 1)
            zone.distance_km = round(distance(request.current_location, zone.location) * MAP_UNIT_KM, 1)
            zone.safety_score = round(
                clamp(55 + nearest_hazard_gap * 2.4 + capacity_ratio * 22, 0, 100),
                1,
            )
            zone.notes = [
                f"{zone.available_capacity} beds available out of {zone.capacity}.",
                f"Nearest hazard buffer: {nearest_hazard_gap:.1f} map units.",
                f"Facilities: {', '.join(zone.facilities[:3])}.",
            ]
            safe_zones.append(zone)
        safe_zones.sort(key=lambda zone: (-zone.safety_score, zone.distance_km))
        return safe_zones[:4]


class EvacuationPlanningAgent:
    TOOLS = ["maps.routing", "maps.hazard-avoidance", "traffic.simulation"]

    def run(
        self,
        request: AnalysisRequest,
        safe_zones: list[SafeZone],
        hazards: list[HazardZone],
    ) -> list[EvacuationRoute]:
        routes: list[EvacuationRoute] = []
        for zone in safe_zones[:3]:
            notes: list[str] = []
            points = [request.current_location]
            detours = self._detours(request.current_location, zone.location, hazards)
            if detours:
                points.extend(detours)
                notes.append("Direct corridor intersects active hazard zones; detour applied.")
            points.append(zone.location)
            total_distance = sum(distance(points[index], points[index + 1]) for index in range(len(points) - 1))
            distance_km = round(total_distance * MAP_UNIT_KM, 1)
            traffic_penalty = (request.social_signal_level + request.news_signal_level) / 40
            speed_kph = clamp(34 - traffic_penalty, 18, 34)
            travel_time = max(4, round((distance_km / speed_kph) * 60))
            route_safety = round(clamp(zone.safety_score - len(detours) * 6, 0, 100), 1)
            notes.extend(
                [
                    f"Estimated average ground speed {speed_kph:.1f} kph.",
                    "Prefer elevated corridors and avoid low-lying junctions.",
                ]
            )
            routes.append(
                EvacuationRoute(
                    safe_zone_id=zone.id,
                    safe_zone_name=zone.name,
                    distance_km=distance_km,
                    travel_time_min=travel_time,
                    safety_score=route_safety,
                    notes=notes,
                    path=points,
                )
            )
        return routes

    def _detours(self, start: Coordinate, end: Coordinate, hazards: list[HazardZone]) -> list[Coordinate]:
        detours: list[Coordinate] = []
        for hazard in hazards:
            if self._segment_hits_circle(start, end, hazard.center, hazard.radius + 4):
                dx = end.x - start.x
                dy = end.y - start.y
                magnitude = math.hypot(dx, dy) or 1
                perp_x = -dy / magnitude
                perp_y = dx / magnitude
                direction = -1 if (hazard.center.x - start.x) * perp_x + (hazard.center.y - start.y) * perp_y > 0 else 1
                detour = Coordinate(
                    x=clamp(hazard.center.x + perp_x * (hazard.radius + 10) * direction, 4, 96),
                    y=clamp(hazard.center.y + perp_y * (hazard.radius + 10) * direction, 4, 96),
                )
                detours.append(detour)
                if len(detours) == 2:
                    break
        return detours

    @staticmethod
    def _segment_hits_circle(start: Coordinate, end: Coordinate, center: Coordinate, radius: float) -> bool:
        dx = end.x - start.x
        dy = end.y - start.y
        if dx == 0 and dy == 0:
            return distance(start, center) <= radius
        t = ((center.x - start.x) * dx + (center.y - start.y) * dy) / (dx * dx + dy * dy)
        t = clamp(t, 0, 1)
        nearest = Coordinate(x=start.x + dx * t, y=start.y + dy * t)
        return distance(nearest, center) <= radius


class CitizenAssistantAgent:
    TOOLS = ["command.contacts", "command.checklist", "guidance.playbooks"]

    PLAYBOOKS = {
        "flood": {
            "before": [
                "Charge phones, power banks, and emergency lights before peak rainfall hits.",
                "Move documents, medicines, and electronics to higher shelves or waterproof bags.",
                "Share a family rendezvous point and a check-in routine before roads close.",
            ],
            "during": [
                "Move immediately to the highest safe level available and avoid walking through moving water.",
                "Switch off main electrical supply if water enters the building and it is safe to do so.",
                "Use SMS or low-bandwidth messaging to preserve phone battery and network capacity.",
            ],
            "after": [
                "Return only after local authorities confirm the corridor is safe.",
                "Boil or purify stored water and disinfect surfaces touched by floodwater.",
                "Document home or shop damage with photos for relief claims.",
            ],
        },
        "cyclone": {
            "before": [
                "Secure loose outdoor objects and reinforce windows and roof access points.",
                "Park vehicles away from trees, weak poles, and drainage channels.",
                "Download offline maps and save local emergency numbers on every household phone.",
            ],
            "during": [
                "Stay away from windows and shelter in the strongest interior room available.",
                "Do not travel during the eye of the storm unless authorities declare movement safe.",
                "Keep battery-powered radio monitoring official updates every 15 minutes.",
            ],
            "after": [
                "Avoid fallen power lines, damaged transformers, and unstable trees.",
                "Check neighbors, especially older adults, once the wind threat passes.",
                "Report blocked routes and medical emergencies immediately to district control.",
            ],
        },
        "heatwave": {
            "before": [
                "Stock oral rehydration salts, shade materials, and extra drinking water.",
                "Move daytime work for high-risk people to early morning or late evening slots.",
                "Identify the nearest cooling center and transport option ahead of peak temperatures.",
            ],
            "during": [
                "Drink water every 20 to 30 minutes even if you do not feel thirsty.",
                "Use wet cloth cooling, cross-ventilation, and shaded rooms to reduce heat stress.",
                "Check on children, outdoor workers, and people with chronic illnesses frequently.",
            ],
            "after": [
                "Continue hydration and observe for delayed heat exhaustion symptoms.",
                "Restock water, medicines, and electrolytes immediately for the next heat spike.",
                "Review missed cooling-center demand and expand coverage where possible.",
            ],
        },
    }

    def __init__(self, registry: RegistryProtocol):
        self.registry = registry

    def run(self, request: AnalysisRequest, risk: RiskSnapshot) -> CitizenGuidance:
        playbook = self.PLAYBOOKS[request.disaster_type]
        immediate_actions = [
            f"Move toward the recommended shelter corridor within {30 if risk.risk_score >= 75 else 90} minutes.",
            "Keep one phone on low-power mode for emergency communication only.",
            "Carry water, medicines, ID, and a flashlight before leaving.",
        ]
        answer_cards = [
            {
                "question": f"I am trapped in a {request.disaster_type}.",
                "answer": "Stay visible, move to the safest elevated or shaded position, and send location details to emergency contacts immediately.",
            },
            {
                "question": "Nearest shelter?",
                "answer": "Use the top-ranked safe zone card and route panel; both are recalculated from your current map position.",
            },
            {
                "question": "How do I purify water?",
                "answer": "Boil for at least one minute if possible, or use chlorine tablets per package directions.",
            },
            {
                "question": "Emergency contacts?",
                "answer": "Open the contact panel for police, fire, ambulance, and disaster management hotlines.",
            },
        ]
        return CitizenGuidance(
            immediate_actions=immediate_actions,
            before_disaster=playbook["before"],
            during_disaster=playbook["during"],
            after_disaster=playbook["after"],
            emergency_contacts=self.registry.contacts(),
            supply_checklist=self.registry.checklist(),
            answer_cards=answer_cards,
        )


class ResourceAllocationAgent:
    TOOLS = ["command.resources", "dispatch.optimizer"]

    def __init__(self, registry: RegistryProtocol):
        self.registry = registry

    def run(
        self,
        request: AnalysisRequest,
        risk: RiskSnapshot,
        situation: SituationSummary,
        safe_zones: list[SafeZone],
    ) -> tuple[DashboardMetrics, list[str]]:
        resources = self.registry.resources()
        demand_factor = clamp(risk.risk_score / 100, 0.25, 0.95)
        ambulances_ready = max(2, round(resources["ambulances"] * (1 - demand_factor * 0.35)))
        rescue_teams_ready = max(1, round(resources["rescue_teams"] * (1 - demand_factor * 0.28)))
        shelters_ready = sum(1 for zone in safe_zones if zone.available_capacity >= 200)
        damage_index = round(clamp((risk.risk_score * 0.7) + (situation.roads_blocked * 2), 12, 98))
        metrics = DashboardMetrics(
            population_at_risk=situation.population_at_risk,
            predicted_damage_index=damage_index,
            response_status=situation.current_incident_status,
            ambulances_ready=ambulances_ready,
            rescue_teams_ready=rescue_teams_ready,
            shelters_ready=shelters_ready,
        )
        suggestions = [
            f"Pre-position {max(2, rescue_teams_ready // 2)} rescue teams near {situation.affected_regions[0]}.",
            f"Reserve {min(12, ambulances_ready)} ambulances for high-risk neighborhoods and hospital transfers.",
            f"Activate overflow registration for {safe_zones[0].name} and {safe_zones[1].name}.",
        ]
        return metrics, suggestions


class EmergencyReportAgent:
    TOOLS = ["reports.pdf", "reports.situation-summary", "maps.snapshot"]

    def run(self, report: AnalysisReport) -> list[str]:
        return [
            f"Issue district bulletin with {report.risk_assessment.status} status.",
            f"Route citizens first toward {report.safe_zones[0].name}.",
            f"Keep alternate corridor to {report.evacuation_routes[1].safe_zone_name if len(report.evacuation_routes) > 1 else report.safe_zones[0].name} open for overflow movement.",
        ]


class CrisisMindService:
    def __init__(self, dataset: dict[str, Any] | None = None, prefer_mcp: bool = True):
        self.dataset = dataset or load_dataset()
        self.registry = build_registry(self.dataset, prefer_mcp=prefer_mcp)
        self.weather_agent = WeatherIntelligenceAgent(self.registry, self.dataset)
        self.risk_agent = RiskPredictionAgent()
        self.situation_agent = SituationAssessmentAgent(self.registry, self.dataset)
        self.safe_zone_agent = SafeZoneAgent(self.registry)
        self.routing_agent = EvacuationPlanningAgent()
        self.citizen_agent = CitizenAssistantAgent(self.registry)
        self.resource_agent = ResourceAllocationAgent(self.registry)
        self.report_agent = EmergencyReportAgent()

    def list_scenarios(self) -> list[dict[str, Any]]:
        return self.dataset["scenarios"]

    @property
    def registry_mode(self) -> str:
        return self.registry.mode

    def integration_status(self) -> list[dict[str, Any]]:
        return [status.model_dump(mode="json") for status in self.registry.integration_status()]

    def data_sources_used(self) -> list[str]:
        return self.registry.data_sources_used() + ["Local disaster scenario knowledge base"]

    def analyze(self, payload: dict[str, Any]) -> AnalysisReport:
        request = self._coerce_request(payload)

        # Generate location-specific data for the requested location
        loc_dataset = generate_location_dataset(
            location_name=request.location_name,
            disaster_type=request.disaster_type,
        )
        # Merge with the base dataset (keep scenarios for lookup, override everything else)
        active_dataset = {**self.dataset, **loc_dataset}
        active_dataset["scenarios"] = self.dataset["scenarios"]

        # Build per-request registry with location-specific data.
        # We use LocalDatasetRegistry directly so the dynamically generated
        # regions, shelters, contacts, etc. are used — the MCP stdio servers
        # carry their own copy of the static dataset and would override these.
        loc_registry = LocalDatasetRegistry(active_dataset)
        weather_agent = WeatherIntelligenceAgent(loc_registry, active_dataset)
        situation_agent = SituationAssessmentAgent(loc_registry, active_dataset)
        safe_zone_agent = SafeZoneAgent(loc_registry)
        citizen_agent = CitizenAssistantAgent(loc_registry)
        resource_agent = ResourceAllocationAgent(loc_registry)

        traces: list[AgentTrace] = []
        weather_summary, hazards, map_context = self._measure(
            "Weather Intelligence Agent",
            weather_agent.TOOLS,
            traces,
            lambda: weather_agent.run(request),
            "Built live hazard footprint from weather and geospatial context.",
        )
        risk = self._measure(
            "Disaster Prediction Agent",
            self.risk_agent.TOOLS,
            traces,
            lambda: self.risk_agent.run(request, weather_summary),
            "Scored disaster probability, confidence, and alert state.",
        )
        situation = self._measure(
            "Situation Assessment Agent",
            situation_agent.TOOLS,
            traces,
            lambda: situation_agent.run(request, risk, hazards, map_context),
            "Estimated impact on population and critical infrastructure.",
        )
        safe_zones = self._measure(
            "Safe Zone Agent",
            safe_zone_agent.TOOLS,
            traces,
            lambda: safe_zone_agent.run(request, hazards),
            "Ranked shelter locations by safety buffer and capacity.",
        )
        routes = self._measure(
            "Evacuation Planning Agent",
            self.routing_agent.TOOLS,
            traces,
            lambda: self.routing_agent.run(request, safe_zones, hazards),
            "Computed hazard-aware evacuation routes and travel times.",
        )
        guidance = self._measure(
            "Citizen Survival Assistant",
            citizen_agent.TOOLS,
            traces,
            lambda: citizen_agent.run(request, risk),
            "Prepared citizen instructions, checklists, and contact guidance.",
        )
        metrics, resource_suggestions = self._measure(
            "Resource Allocation Agent",
            resource_agent.TOOLS,
            traces,
            lambda: resource_agent.run(request, risk, situation, safe_zones),
            "Suggested field deployment and command metrics.",
        )
        report = AnalysisReport(
            report_id=f"DDAI-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
            generated_at=datetime.now(timezone.utc),
            generated_by="Disaster Detection AI",
            request=request,
            executive_summary=(
                f"Disaster Detection AI has flagged {request.location_name} for a {risk.severity_level.lower()} "
                f"{request.disaster_type} event with {risk.probability_score}% probability."
            ),
            risk_assessment=risk,
            situation_analysis=situation,
            safe_zones=safe_zones,
            evacuation_routes=routes,
            precautionary_measures=guidance,
            emergency_contacts=guidance.emergency_contacts,
            emergency_supply_checklist=guidance.supply_checklist,
            recommended_actions=[],
            resource_allocation_suggestions=resource_suggestions,
            dashboard_metrics=metrics,
            agent_trace=traces,
            hazard_zones=hazards,
            map_layers={
                "regions": map_context["regions"],
                "roads": map_context["roads"],
                "current_location": request.current_location.model_dump(),
            },
            data_sources_used=self.data_sources_used(),
            mcp_tools_utilized=self.registry.tools_used(),
            integration_status=self.registry.integration_status(),
        )
        report.recommended_actions = self._measure(
            "Emergency Report Agent",
            self.report_agent.TOOLS,
            traces,
            lambda: self.report_agent.run(report),
            "Compiled authority-facing incident recommendations.",
        )
        report.agent_trace = traces
        report.mcp_tools_utilized = self.registry.tools_used()
        report.integration_status = self.registry.integration_status()
        return report

    def _coerce_request(self, payload: dict[str, Any]) -> AnalysisRequest:
        scenario_lookup = {scenario["id"]: scenario for scenario in self.dataset["scenarios"]}
        scenario_id = payload.get("scenario_id")
        base: dict[str, Any] = {}
        if scenario_id and scenario_id in scenario_lookup:
            scenario = scenario_lookup[scenario_id]
            base = {
                "scenario_id": scenario_id,
                "location_name": scenario["location_name"],
                "disaster_type": scenario["disaster_type"],
                "current_location": scenario["current_location"],
                **scenario["inputs"],
            }
        merged = {**base, **payload}
        return AnalysisRequest.model_validate(merged)

    @staticmethod
    def _measure(
        agent_name: str,
        tools_used: list[str],
        traces: list[AgentTrace],
        action: Callable[[], Any],
        summary: str,
    ) -> Any:
        started = time.perf_counter()
        result = action()
        elapsed = round((time.perf_counter() - started) * 1000)
        traces.append(
            AgentTrace(
                agent=agent_name,
                summary=summary,
                tools_used=tools_used,
                latency_ms=elapsed,
            )
        )
        return result
