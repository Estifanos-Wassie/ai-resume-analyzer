"""Public analysis contract shared by validation, OpenAPI, and the prompt."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

FeedbackText = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=1000)
]
FeedbackItems = Annotated[list[FeedbackText], Field(max_length=20)]


class AnalysisResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    match_score: Annotated[int, Field(ge=0, le=100)]
    strengths: FeedbackItems
    missing_skills: FeedbackItems
    suggestions: FeedbackItems

    @classmethod
    def provider_schema(cls) -> dict:
        """Documented structural subset; application bounds stay authoritative."""
        fields = cls.model_json_schema()['properties']
        properties = {}
        for name, field in fields.items():
            properties[name] = {'type': field['type']}
            if field['type'] == 'array':
                properties[name]['items'] = {'type': field['items']['type']}
        return {
            'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False,
        }
