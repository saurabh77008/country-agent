from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class ICountryExtractor(Protocol):
    def extract(self, text: str) -> str | None: ...


@runtime_checkable
class IFieldExtractor(Protocol):
    def extract(self, text: str) -> list: ...


class ICountryRepository(ABC):
    @abstractmethod
    async def fetch(self, country_name: str) -> dict | None: ...


@runtime_checkable
class IAnswerSynthesiser(Protocol):
    def synthesise(self, state: dict) -> str: ...
