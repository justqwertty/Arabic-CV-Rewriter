import pytest

from sectioning import SectioningError, fallback_section, parse_sections, split_oversized


# --- parse_sections -------------------------------------------------------

def test_parse_sections_valid_json():
    raw = '{"sections": [{"name": "Experience", "bullets": ["did a thing", "did another"]}]}'
    result = parse_sections(raw)
    assert result == [{"name": "Experience", "bullets": ["did a thing", "did another"]}]


def test_parse_sections_invalid_json_raises():
    with pytest.raises(SectioningError):
        parse_sections("not json at all")


def test_parse_sections_missing_sections_key_raises():
    with pytest.raises(SectioningError):
        parse_sections('{"foo": "bar"}')


def test_parse_sections_empty_list_raises():
    with pytest.raises(SectioningError):
        parse_sections('{"sections": []}')


def test_parse_sections_bad_section_shape_raises():
    with pytest.raises(SectioningError):
        parse_sections('{"sections": [{"name": "Experience"}]}')


def test_parse_sections_strips_whitespace_and_drops_blank_bullets():
    raw = '{"sections": [{"name": "  Skills  ", "bullets": ["  Python  ", "  ", "Go"]}]}'
    result = parse_sections(raw)
    assert result == [{"name": "Skills", "bullets": ["Python", "Go"]}]


# --- fallback_section ------------------------------------------------------

def test_fallback_section_wraps_raw_text():
    result = fallback_section("some raw cv text")
    assert result == [{"name": "Full text", "bullets": ["some raw cv text"]}]


# --- split_oversized ---------------------------------------------------------

def test_split_oversized_under_limit_passes_through_unchanged():
    sections = [{"name": "Skills", "bullets": ["Python", "Go"]}]
    result = split_oversized(sections, max_chars=3000)
    assert result == sections


def test_split_oversized_splits_into_numbered_parts():
    bullets = [f"bullet number {i} " + "x" * 100 for i in range(10)]
    sections = [{"name": "Experience", "bullets": bullets}]
    result = split_oversized(sections, max_chars=300)

    assert len(result) > 1
    for part in result:
        assert part["name"].startswith("Experience (")
        assert "\n".join(part["bullets"]).__len__() <= 300 or len(part["bullets"]) == 1


def test_split_oversized_single_oversized_bullet_is_left_as_one_part():
    huge_bullet = "x" * 5000
    sections = [{"name": "Summary", "bullets": [huge_bullet]}]
    result = split_oversized(sections, max_chars=3000)

    assert len(result) == 1
    assert result[0]["bullets"] == [huge_bullet]
