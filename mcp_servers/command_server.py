from __future__ import annotations

from common import SimpleMCPServer, ToolDefinition, load_dataset


DATASET = load_dataset()


def contacts(_: dict[str, object]) -> dict[str, str]:
    return DATASET["emergency_contacts"]


def resources(_: dict[str, object]) -> dict[str, int]:
    return DATASET["resources"]


def checklist(_: dict[str, object]) -> list[str]:
    return DATASET["supply_checklist"]


if __name__ == "__main__":
    server = SimpleMCPServer(
        server_name="Command MCP Server",
        tools=[
            ToolDefinition(
                name="command.contacts",
                description="Return emergency contact numbers and control room data.",
                input_schema={"type": "object", "properties": {}},
                handler=contacts,
            ),
            ToolDefinition(
                name="command.resources",
                description="Return ambulances, rescue teams, and logistics resources.",
                input_schema={"type": "object", "properties": {}},
                handler=resources,
            ),
            ToolDefinition(
                name="command.checklist",
                description="Return the emergency supply checklist for citizens.",
                input_schema={"type": "object", "properties": {}},
                handler=checklist,
            ),
        ],
    )
    server.serve_forever()
