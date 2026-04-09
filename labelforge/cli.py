"""LabelForge CLI — built with Typer + Rich."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.theme import Theme

from . import __version__
from .applier import apply_from_components, build_labels, load_labels
from .document_analyzer import extract_components_from_path
from .utils import AI_COMPAT_WARNING, detect_file_type

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "label_id": "dim cyan",
    }
)

console = Console(theme=_THEME, highlight=False)
err_console = Console(stderr=True, theme=_THEME, highlight=False)

app = typer.Typer(
    name="labelforge",
    help="Professional PDF text label editor. Extract → edit → re-apply.",
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[
            RichHandler(
                console=err_console,
                rich_tracebacks=True,
                show_path=verbose,
            )
        ],
    )


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"LabelForge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version."),
    ] = None,
) -> None:
    """LabelForge — extract, edit, and re-apply PDF text labels."""


# ---------------------------------------------------------------------------
# apply command
# ---------------------------------------------------------------------------


@app.command()
def apply(
    components_file: Annotated[
        Path,
        typer.Option("--components", "-c", help="components.json from 'labelforge components'.")
    ],
    changes_file: Annotated[
        Path,
        typer.Option("--changes", help="changes.json mapping component_id to new value.")
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination PDF file."),
    ] = Path("output.pdf"),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite output if it already exists.")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Apply changes to a PDF or .ai file.

      labelforge apply --components components.json --changes changes.json -o out.pdf
    """
    _setup_logging(verbose)

    if not components_file.exists():
        err_console.print(f"[error]Error:[/error] components file not found: {components_file}")
        raise typer.Exit(code=1)
    if not changes_file.exists():
        err_console.print(f"[error]Error:[/error] changes file not found: {changes_file}")
        raise typer.Exit(code=1)
    try:
        n = apply_from_components(
            components_path=components_file,
            changes_path=changes_file,
            output_path=output,
            force=force,
        )
    except FileExistsError as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        err_console.print(f"[error]Unexpected error:[/error] {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=2) from exc
    console.print(Panel(
        f"[success]Done![/success] {n} component(s) changed → [bold]{output}[/bold]",
        expand=False,
    ))


# ---------------------------------------------------------------------------
# build command
# ---------------------------------------------------------------------------


@app.command()
def build(
    labels_json: Annotated[Path, typer.Argument(help="Path to the labels JSON file.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination PDF file."),
    ] = Path("output.pdf"),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite output if it already exists.")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Build a new PDF from a labels JSON file without a source document.

    Places every label at its original bbox position on a blank white page.
    Useful when the original source file is unavailable. Note: background
    graphics, vectors, and images from the original are not included.
    """
    _setup_logging(verbose)

    console.print(
        "[warning]Note:[/warning] Building from labels only — background graphics "
        "and vectors from the original document will not be included."
    )

    try:
        labels = load_labels(labels_json)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Building PDF from {len(labels)} labels...", total=None)
            n = build_labels(labels=labels, output_path=output, force=force)
    except (FileExistsError, ValueError) as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        err_console.print(f"[error]Unexpected error:[/error] {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=2) from exc

    console.print(Panel(
        f"[success]Done![/success] Built [bold]{n}[/bold] labels → [bold]{output}[/bold]",
        expand=False,
    ))


# ---------------------------------------------------------------------------
# inspect command
# ---------------------------------------------------------------------------


@app.command(name="inspect")
def inspect_labels(
    labels_json: Annotated[Path, typer.Argument(help="Path to the labels JSON file.")],
    changed_only: Annotated[
        bool,
        typer.Option("--changed-only", "-c", help="Show only labels with new_text set."),
    ] = False,
) -> None:
    """Show editable fields for each label in a labels JSON file.

    Displays id, page, original_text, new_text, fontname, fontsize, and color
    for every label so you can quickly see what values are present and which
    labels are queued for replacement.
    """
    if not labels_json.exists():
        err_console.print(f"[error]Error:[/error] File not found: {labels_json}")
        raise typer.Exit(code=1)

    try:
        labels = load_labels(labels_json)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc

    if changed_only:
        labels = [lbl for lbl in labels if lbl.new_text is not None]

    if not labels:
        console.print("[warning]No labels to display.[/warning]")
        raise typer.Exit()

    table = Table(
        title=f"Labels — {labels_json.name}",
        show_lines=True,
    )
    table.add_column("ID", style="label_id", no_wrap=True)
    table.add_column("Page", justify="right")
    table.add_column("Original Text")
    table.add_column("New Text")
    table.add_column("Font", style="dim")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Color", justify="center", style="dim")

    for lbl in labels:
        new_text_cell = (
            f"[success]{lbl.new_text}[/success]" if lbl.new_text is not None else "[dim]—[/dim]"
        )
        table.add_row(
            lbl.id,
            str(lbl.page),
            lbl.original_text,
            new_text_cell,
            lbl.fontname,
            f"{lbl.fontsize:.1f}pt",
            lbl.color,
        )

    console.print(table)
    console.print(
        f"[info]{len(labels)} label(s) shown."
        + (" (filtered: changed only)" if changed_only else "")
        + "[/info]"
    )


# ---------------------------------------------------------------------------
# components command
# ---------------------------------------------------------------------------


@app.command()
def components(
    input_file: Annotated[Path, typer.Argument(help="Path to the source PDF or .ai file.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination JSON file."),
    ] = Path("components.json"),
    types: Annotated[
        Optional[str],
        typer.Option("--types", "-t", help="Comma-separated component types to include: TEXT,IMAGE,BARCODE,SHAPE. Default: all."),
    ] = None,
    pretty: Annotated[
        bool, typer.Option("--pretty/--compact", help="Pretty-print the JSON output.")
    ] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Extract all components (text, images, barcodes, shapes) from INPUT_FILE.

    Unlike 'analyze' (text-only), this command extracts every component type
    including images and barcodes. Barcode values are decoded automatically
    if libzbar is installed (brew install zbar / apt install libzbar0).
    """
    _setup_logging(verbose)

    if not input_file.exists():
        err_console.print(f"[error]Error:[/error] File not found: {input_file}")
        raise typer.Exit(code=1)

    filter_types: set[str] | None = None
    if types:
        filter_types = {t.strip().upper() for t in types.split(",")}
        valid = {"TEXT", "IMAGE", "BARCODE", "SHAPE"}
        unknown = filter_types - valid
        if unknown:
            err_console.print(f"[error]Error:[/error] Unknown type(s): {', '.join(sorted(unknown))}. Valid: {', '.join(sorted(valid))}")
            raise typer.Exit(code=1)

    if output.exists():
        console.print(f"[warning]Warning:[/warning] Overwriting existing file: {output}")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Extracting components from {input_file.name}...", total=None)
            all_components = extract_components_from_path(input_file)
    except Exception as exc:
        err_console.print(f"[error]Unexpected error:[/error] {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=2) from exc

    if filter_types:
        all_components.components = [
            c for c in all_components.components if c.type.value in filter_types
        ]

    # Serialize as ComponentsFile (includes source_file); strip large thumbnail blobs
    raw = all_components.model_dump()
    for c in raw["components"]:
        c.pop("thumbnail_b64", None)

    indent = 2 if pretty else None
    output.write_text(json.dumps(raw, indent=indent, default=str), encoding="utf-8")

    # Print summary table
    from collections import Counter
    comps = all_components.components
    counts = Counter(c.type.value for c in comps)
    table = Table(title=f"Components — {input_file.name}", show_lines=False)
    table.add_column("Type", style="bold")
    table.add_column("Count", justify="right")
    for t in ["TEXT", "IMAGE", "BARCODE", "SHAPE"]:
        if counts[t]:
            table.add_row(t, str(counts[t]))
    console.print(table)
    console.print(Panel(
        f"[success]Done![/success] {len(comps)} component(s) written to [bold]{output}[/bold]",
        expand=False,
    ))


if __name__ == "__main__":
    app()
