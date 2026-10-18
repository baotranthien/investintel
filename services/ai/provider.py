from typing import Any, Protocol


class AIProvider(Protocol):
    async def generate(self, prompt: str, system: str = "", model: str | None = None) -> str:
        ...

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        ...

    def status(self) -> dict[str, Any]:
        ...
