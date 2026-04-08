"""`module_segment_labels.json` 의 `teamMapping` 편집용 스키마 (관리 API)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TeamWhen(BaseModel):
    """
    경로에서 추출한 모듈 토큰 목록으로 매칭.
    - match=first: 첫 토큰이 modules 중 하나
    - match=any: 경로 어디든 modules 중 하나가 있으면
    """

    model_config = ConfigDict(populate_by_name=True)

    modules: list[str] = Field(default_factory=list)
    match_kind: Literal["first", "any"] = Field(
        default="any",
        alias="match",
        serialization_alias="match",
    )

    @field_validator("modules", mode="before")
    @classmethod
    def _norm_modules(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("modules는 배열이어야 합니다")
        out: list[str] = []
        for x in v:
            s = str(x).strip().lower()
            if s:
                out.append(s)
        return out


class PrecedenceRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    team_id: str = Field(alias="teamId")
    label: str = ""
    when: TeamWhen

    @field_validator("team_id", mode="before")
    @classmethod
    def _team_id_nonempty(cls, v: object) -> str:
        s = str(v or "").strip()
        if not s:
            raise ValueError("teamId는 비울 수 없습니다")
        return s

    @field_validator("label", mode="before")
    @classmethod
    def _label_str(cls, v: object) -> str:
        return str(v or "").strip()

    @model_validator(mode="after")
    def _when_has_modules(self) -> PrecedenceRow:
        if not self.when.modules:
            raise ValueError("각 규칙의 when.modules에 값이 하나 이상 필요합니다")
        return self


class TeamFallback(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    team_id: str = Field(alias="teamId")
    label: str = ""

    @field_validator("team_id", mode="before")
    @classmethod
    def _fallback_id(cls, v: object) -> str:
        s = str(v or "").strip()
        if not s:
            raise ValueError("fallback.teamId는 비울 수 없습니다")
        return s

    @field_validator("label", mode="before")
    @classmethod
    def _fallback_label(cls, v: object) -> str:
        return str(v or "").strip()


class TeamMappingUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    precedence: list[PrecedenceRow]
    fallback: TeamFallback

    @field_validator("precedence")
    @classmethod
    def _precedence_non_empty(cls, v: list[PrecedenceRow]) -> list[PrecedenceRow]:
        if not v:
            raise ValueError("precedence에 최소 한 행이 필요합니다")
        return v

    @model_validator(mode="after")
    def _no_duplicate_team_ids(self) -> TeamMappingUpdate:
        ids = [r.team_id for r in self.precedence]
        if len(ids) != len(set(ids)):
            raise ValueError("precedence 안의 teamId가 중복되었습니다")
        return self

    def to_stored_dict(self, existing_note: str | None) -> dict:
        out: dict = self.model_dump(by_alias=True, mode="json")
        if existing_note and existing_note.strip():
            out["_note"] = existing_note.strip()
        return out
