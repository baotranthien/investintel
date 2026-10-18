from typing import Literal

from .config import OllamaConfig

TaskType = Literal[
    "NEWS_CLASSIFICATION",
    "DOCUMENT_SUMMARY",
    "STOCK_RESEARCH",
    "MACRO_ANALYSIS",
    "DAILY_BRIEF",
    "WEEKLY_BRIEF",
    "MONTHLY_BRIEF",
    "USER_CHAT",
    "DEEP_RESEARCH",
]


class AIRouter:
    def __init__(self, config: OllamaConfig | None = None):
        config = config or OllamaConfig.from_env()
        self.fast_model = config.fast_model
        self.primary_model = config.primary_model
        self.reasoning_model = config.reasoning_model

    def route_task(self, task: TaskType, complexity: Literal["LOW", "MEDIUM", "HIGH"]) -> str:
        """Routes the task to the appropriate local model."""
        if task in ["NEWS_CLASSIFICATION", "DOCUMENT_SUMMARY"] and complexity == "LOW":
            return self.fast_model

        if task in ["MACRO_ANALYSIS", "DEEP_RESEARCH", "MONTHLY_BRIEF"] or complexity == "HIGH":
            return self.reasoning_model

        return self.primary_model
