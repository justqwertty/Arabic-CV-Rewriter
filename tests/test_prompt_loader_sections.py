import pytest

import prompt_loader


def test_build_section_prompt_returns_base_block_content():
    prompt = prompt_loader.build_section_prompt()
    assert "sections" in prompt.lower()
    assert "json" in prompt.lower()


def test_build_section_prompt_raises_on_missing_file(monkeypatch):
    monkeypatch.setattr(
        prompt_loader, "SECTION_PROMPT_PATH", "/nonexistent/section-prompt.md"
    )
    with pytest.raises(prompt_loader.PromptError):
        prompt_loader.build_section_prompt()
