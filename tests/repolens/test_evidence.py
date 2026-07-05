from pathlib import Path

from repolens.evidence import EvidenceValidator
from repolens.schemas import EvidenceRef


def test_evidence_validator_accepts_existing_line_range(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    evidence = EvidenceRef(path="app.py", claim="second line", line_start=2, line_end=2)
    assert EvidenceValidator(tmp_path).validate(evidence) is None


def test_evidence_validator_rejects_missing_file_and_invalid_line(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("one\n", encoding="utf-8")
    validator = EvidenceValidator(tmp_path)
    missing = validator.validate(EvidenceRef(path="missing.py", claim="missing"))
    invalid_line = validator.validate(EvidenceRef(path="app.py", claim="bad", line_start=2))
    assert missing and "regular file" in missing.reason
    assert invalid_line and "exceeds" in invalid_line.reason


def test_evidence_text_support_requires_cited_line(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("run pytest\nnot here\n", encoding="utf-8")
    validator = EvidenceValidator(tmp_path)
    assert validator.supports_text(
        EvidenceRef(path="README.md", claim="command", line_start=1), "pytest"
    )
    assert not validator.supports_text(
        EvidenceRef(path="README.md", claim="wrong line", line_start=2), "pytest"
    )
