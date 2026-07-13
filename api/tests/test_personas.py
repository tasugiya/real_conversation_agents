"""Tests for personas.py persona pool and selection."""

import pytest

from src.services.personas import PERSONA_POOL, get_persona, select_personas


class TestSelectPersonas:
    def test_count_one(self):
        result = select_personas(1)
        assert len(result) == 1

    def test_count_two(self):
        result = select_personas(2)
        assert len(result) == 2
        # No duplicates
        names = [p.name for p in result]
        assert len(names) == len(set(names))

    def test_count_zero_returns_one(self):
        result = select_personas(0)
        assert len(result) == 1

    def test_count_exceeding_pool_is_capped(self):
        result = select_personas(100)
        assert len(result) == len(PERSONA_POOL)
        # No duplicates
        names = [p.name for p in result]
        assert len(names) == len(set(names))

    def test_all_personas_have_required_fields(self):
        for p in PERSONA_POOL:
            assert p.name
            assert p.label
            assert p.personality

    def test_returned_personas_are_from_pool(self):
        for _ in range(10):
            selected = select_personas(2)
            pool_names = {p.name for p in PERSONA_POOL}
            for p in selected:
                assert p.name in pool_names


class TestGetPersona:
    def test_known_name(self):
        p = get_persona("alice")
        assert p is not None
        assert p.name == "alice"
        assert p.label == "Alice"

    def test_unknown_name_returns_none(self):
        assert get_persona("nonexistent") is None
