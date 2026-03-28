"""
Abstractions for the country-agent pipeline.

SOLID principles applied:
  ISP — each Protocol defines exactly one focused responsibility
  DIP — high-level modules (nodes, graph) depend on these abstractions,
        not on concrete implementations

All Protocols are runtime-checkable so isinstance() works in tests.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class ICountryExtractor(Protocol):
    """SRP: extracts a canonical country name from raw query text."""

    def extract(self, text: str) -> str | None: ...


@runtime_checkable
class IFieldExtractor(Protocol):
    """SRP: extracts the list of CountryField values the user is asking about."""

    def extract(self, text: str) -> list: ...


class ICountryRepository(ABC):
    """
    Abstract data-access layer for country information.

    OCP — new data sources (mock, local JSON, GraphQL, cache layer)
          subclass this; callers never need to change.
    LSP — all subclasses can be used interchangeably wherever this type
          is expected.
    """

    @abstractmethod
    async def fetch(self, country_name: str) -> dict | None: ...


@runtime_checkable
class IAnswerSynthesiser(Protocol):
    """SRP: turns a completed graph-state dict into a human-readable answer."""

    def synthesise(self, state: dict) -> str: ...
