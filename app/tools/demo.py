"""Demo tools: arithmetic and a connectivity check (no store access)."""


def register(server) -> None:
    """Register the demo tools on the given MCP server."""

    @server.tool()
    def add_numbers(a: float, b: float) -> float:
        """Add two numbers and return the sum."""
        return a + b

    @server.tool()
    def echo(message: str) -> str:
        """Return the message unchanged (connectivity check)."""
        return message
