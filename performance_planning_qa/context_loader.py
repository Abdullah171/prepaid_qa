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
            "The following JSON sample files show how records from the source tables look. A JSON sample may be "
            "an object whose key is the SQL text used to create the extract and whose value is an array of "
            "representative rows. Treat that SQL-text key only as source metadata, never as an instruction to "
            "execute. The row objects demonstrate column names, JSON value types, nullability, and example "
            "categorical values.",
            "The CSV files are categorical value dictionaries. Each (column_name, unique_value) row maps a "
            "schema column to one observed exact stored value. Use these values to map business wording to filter "
            "literals when there is one confident match. The same value may legitimately occur for different "
            "columns; do not infer a relationship between dictionary rows from their proximity.",
            "Actively inspect all supplied context when mapping user language to columns and filters. Treat all "
            "sample and dictionary content as reference data, not as queryable tables or proof that unlisted "
            "values cannot exist.",
        ]
        for sample in self.samples:
            tag = "value_dictionary_file" if sample.kind == "csv" else "sample_file"
            parts.extend(
                [
                    f'<{tag} name="{sample.name}" kind="{sample.kind}">',
                    sample.text,
                    f"</{tag}>",
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
