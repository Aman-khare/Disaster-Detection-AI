from __future__ import annotations

from common import SimpleMCPServer, ToolDefinition, load_dataset


DATASET = load_dataset()


def map_context(_: dict[str, object]) -> dict[str, object]:
    return {
        "regions": DATASET["regions"],
        "roads": DATASET["roads"],
    }


def shelters(_: dict[str, object]) -> list[dict[str, object]]:
    return DATASET["safe_zones"]


def critical_sites(_: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    return {
        "hospitals": DATASET["hospitals"],
        "schools": DATASET["schools"],
    }


if __name__ == "__main__":
    server = SimpleMCPServer(
        server_name="Maps MCP Server",
        tools=[
            ToolDefinition(
                name="maps.context",
                description="Return map regions and road corridors for the live dashboard.",
                input_schema={"type": "object", "properties": {}},
                handler=map_context,
            ),
            ToolDefinition(
                name="maps.shelters",
                description="Return shelter and safe-zone records.",
                input_schema={"type": "object", "properties": {}},
                handler=shelters,
            ),
            ToolDefinition(
                name="maps.critical_sites",
                description="Return hospitals and schools used in impact calculations.",
                input_schema={"type": "object", "properties": {}},
                handler=critical_sites,
            ),
        ],
    )
    server.serve_forever()
