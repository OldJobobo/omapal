from pathlib import Path

import pytest

import versioning


def test_bump_semver_advances_parts() -> None:
    assert versioning.bump_semver("1.2.3", "patch") == "1.2.4"
    assert versioning.bump_semver("1.2.3", "minor") == "1.3.0"
    assert versioning.bump_semver("1.2.3", "major") == "2.0.0"


def test_parse_semver_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        versioning.parse_semver("1.2")


def test_write_and_read_version_round_trip(tmp_path: Path) -> None:
    version_file = tmp_path / "version.py"
    version_file.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    assert versioning.read_version(version_file) == "0.1.0"
    versioning.write_version("0.2.0", version_file)
    assert versioning.read_version(version_file) == "0.2.0"


def test_ensure_changelog_entry_inserts_new_release(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "\n".join(
            [
                "# Changelog",
                "",
                "All notable changes to this project will be documented in this file.",
                "",
                "## [0.1.0] - 2026-03-04",
                "",
                "### Added",
                "- Initial release",
                "",
            ]
        ),
        encoding="utf-8",
    )
    changed = versioning.ensure_changelog_entry("0.2.0", changelog)
    assert changed is True
    text = changelog.read_text(encoding="utf-8")
    assert "## [0.2.0]" in text
    assert text.index("## [0.2.0]") < text.index("## [0.1.0]")


def test_main_current_reads_custom_version_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    version_file = tmp_path / "version.py"
    version_file.write_text('__version__ = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(versioning, "VERSION_FILE", version_file)
    code = versioning.main(["current"])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "9.9.9"
