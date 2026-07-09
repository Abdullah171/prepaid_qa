"""Load schema and sample-data context for prompting."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    kind: str
    text: str

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class PromptContext:
    schema: SourceDocument
    samples: tuple[SourceDocument, ...]

    def render_raw(self) -> str:
        parts = [
            "The following schema file is the canonical database contract. Use exact table and column names from it.",
            f'<schema_file name="{self.schema.name}">',
            self.schema.text,
            "</schema_file>",
            "The following sample files are raw extracts. Use them to understand value formats and examples only.",
        ]
        for sample in self.samples:
            parts.extend(
                [
                    f'<sample_file name="{sample.name}" kind="{sample.kind}">',
                    sample.text,
                    "</sample_file>",
                ]
            )
        return "\n".join(parts)


def load_prompt_context(schema_path: Path, sample_data_dir: Path) -> PromptContext:
    return _load_prompt_context_cached(str(schema_path.resolve()), str(sample_data_dir.resolve()))


@lru_cache(maxsize=4)
def _load_prompt_context_cached(schema_path_text: str, sample_data_dir_text: str) -> PromptContext:
    schema_path = Path(schema_path_text)
    sample_data_dir = Path(sample_data_dir_text)

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    if not sample_data_dir.exists():
        raise FileNotFoundError(f"Sample data directory not found: {sample_data_dir}")

    schema = SourceDocument(
        path=schema_path,
        kind="sql_schema",
        text=schema_path.read_text(encoding="utf-8", errors="replace"),
    )

    sample_paths = sorted(sample_data_dir.glob("*.json")) + sorted(sample_data_dir.glob("*.csv"))
    samples = tuple(
        SourceDocument(
            path=path,
            kind=path.suffix.lstrip(".").lower() or "text",
            text=path.read_text(encoding="utf-8", errors="replace"),
        )
        for path in sample_paths
    )
    if not samples:
        raise FileNotFoundError(f"No JSON or CSV sample files found under: {sample_data_dir}")

    return PromptContext(schema=schema, samples=samples)
