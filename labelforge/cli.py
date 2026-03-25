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
from .analyzer import analyze_pdf, analyze_file, extract_labels, _parse_page_range
from .applier import apply_labels, build_labels, load_labels
from .models import Label
from .utils import AI_COMPAT_WARNING, AI_OUTPUT_WARNING, detect_file_type

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
# analyze command
# ---------------------------------------------------------------------------


@app.command()
def analyze(
    input_pdf: Annotated[Path, typer.Argument(help="Path to the source PDF or .ai file.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination labels JSON file."),
    ] = Path("labels.json"),
    pretty: Annotated[
        bool, typer.Option("--pretty/--compact", help="Pretty-print the JSON output.")
    ] = True,
    min_font_size: Annotated[
        float, typer.Option("--min-font-size", "-m", help="Skip spans smaller than this (pt).")
    ] = 0.0,
    page: Annotated[
        Optional[str],
        typer.Option("--page", "-p", help="Page range, e.g. '0-5' or '0,2,4'. Default: all pages."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Extract all text spans from INPUT_PDF (or .ai) into a labels JSON file.

    Each span becomes a Label object with id, bbox, original_text, fontname,
    fontsize, color, and more. Set new_text on any label to queue it for
    replacement, then run 'labelforge apply'.
    """
    _setup_logging(verbose)

    if not input_pdf.exists():
        err_console.print(f"[error]Error:[/error] File not found: {input_pdf}")
        raise typer.Exit(code=1)

    try:
        file_type = detect_file_type(input_pdf)
    except ValueError as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc

    if file_type == "ai":
        console.print(f"[warning]Warning:[/warning] {AI_COMPAT_WARNING}")

    if output.exists():
        console.print(f"[warning]Warning:[/warning] Overwriting existing file: {output}")

    try:
        import fitz
        doc = fitz.open(str(input_pdf))
        total_pages = len(doc)

        page_range = None
        if page:
            page_range = _parse_page_range(page, total_pages)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Extracting labels...", total=None)
            labels = extract_labels(doc, min_font_size=min_font_size, page_range=page_range)
        doc.close()

        output.parent.mkdir(parents=True, exist_ok=True)
        indent = 2 if pretty else None
        with output.open("w", encoding="utf-8") as fh:
            json.dump([lbl.model_dump() for lbl in labels], fh, indent=indent, ensure_ascii=False)

    except ValueError as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        err_console.print(f"[error]Unexpected error:[/error] {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=2) from exc

    # Summary table
    by_page: dict[int, int] = {}
    for lbl in labels:
        by_page[lbl.page] = by_page.get(lbl.page, 0) + 1

    table = Table(title=f"Labels extracted from {input_pdf.name}", show_lines=False)
    table.add_column("Page", style="cyan", justify="right")
    table.add_column("Labels", justify="right")
    for pg, count in sorted(by_page.items()):
        table.add_row(str(pg), str(count))
    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{len(labels)}[/bold]")

    console.print(table)
    console.print(Panel(
        f"[success]Done![/success] Written to [bold]{output}[/bold]",
        expand=False,
    ))


# ---------------------------------------------------------------------------
# apply command
# ---------------------------------------------------------------------------


@app.command()
def apply(
    input_pdf: Annotated[Path, typer.Argument(help="Path to the original PDF or .ai file.")],
    labels_json: Annotated[Path, typer.Argument(help="Path to the edited labels JSON file.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination PDF file."),
    ] = Path("output.pdf"),
    backup: Annotated[
        bool, typer.Option("--backup", "-b", help="Copy input PDF to <input>.bak before writing.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite output if it already exists.")
    ] = False,
    output_format: Annotated[
        str, typer.Option("--output-format", help="Output format: pdf or ai.")
    ] = "pdf",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Apply edited labels JSON to INPUT_PDF (or .ai) and write a modified PDF or .ai.

    Only labels where new_text differs from original_text are processed.
    Use new_text=\"\" to erase a label without inserting replacement text.
    """
    _setup_logging(verbose)

    fmt = output_format.lower()
    if fmt not in ("pdf", "ai"):
        err_console.print(f"[error]Error:[/error] Unsupported output format {output_format!r}. Use 'pdf' or 'ai'.")
        raise typer.Exit(code=1)

    if fmt == "ai":
        console.print(f"[warning]Warning:[/warning] {AI_OUTPUT_WARNING}")
        if output.suffix.lower() != ".ai":
            output = output.with_suffix(".ai")

    if input_pdf.exists():
        try:
            file_type = detect_file_type(input_pdf)
        except ValueError as exc:
            err_console.print(f"[error]Error:[/error] {exc}")
            raise typer.Exit(code=1) from exc
        if file_type == "ai":
            console.print(f"[warning]Warning:[/warning] {AI_COMPAT_WARNING}")

    try:
        labels = load_labels(labels_json)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc

    changed_count = sum(1 for lbl in labels if lbl.is_changed)
    if changed_count == 0:
        console.print("[warning]No labels have new_text set — nothing to apply.[/warning]")
        raise typer.Exit(code=0)

    console.print(f"Applying [bold]{changed_count}[/bold] change(s) to [bold]{input_pdf.name}[/bold]...")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Applying edits...", total=None)
            n = apply_labels(
                input_path=input_pdf,
                labels=labels,
                output_path=output,
                backup=backup,
                force=force,
            )
    except FileNotFoundError as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc
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
        f"[success]Done![/success] {n} label(s) replaced → [bold]{output}[/bold]",
        expand=False,
    ))


# ---------------------------------------------------------------------------
# replace command
# ---------------------------------------------------------------------------


@app.command()
def replace(
    input_pdf: Annotated[Path, typer.Argument(help="Path to the source PDF.")],
    old_text: Annotated[str, typer.Argument(help="Text to find and replace.")],
    new_text: Annotated[str, typer.Argument(help="Replacement text.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination PDF file."),
    ] = Path("output.pdf"),
    page: Annotated[
        Optional[str],
        typer.Option("--page", "-p", help="Limit to page range, e.g. '0' or '0-3'."),
    ] = None,
    all_occurrences: Annotated[
        bool,
        typer.Option("--all", "-a", help="Replace all occurrences (default: first only)."),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite output if it already exists.")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Inline replacement: find OLD_TEXT in INPUT_PDF and replace with NEW_TEXT.

    This is a shortcut that skips the JSON step — useful for quick one-off edits.
    """
    _setup_logging(verbose)

    if not input_pdf.exists():
        err_console.print(f"[error]Error:[/error] File not found: {input_pdf}")
        raise typer.Exit(code=1)

    try:
        import fitz
        doc = fitz.open(str(input_pdf))
        total_pages = len(doc)
        doc.close()

        page_range = None
        if page:
            page_range = _parse_page_range(page, total_pages)

        doc2 = fitz.open(str(input_pdf))
        labels = extract_labels(doc2, page_range=page_range)
        doc2.close()
    except ValueError as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc

    matched: list[Label] = []
    for lbl in labels:
        if lbl.original_text == old_text:
            matched.append(lbl)
            if not all_occurrences:
                break

    if not matched:
        err_console.print(f"[warning]Warning:[/warning] Text {old_text!r} not found in PDF.")
        raise typer.Exit(code=1)

    for lbl in matched:
        lbl.new_text = new_text

    console.print(f"Replacing [bold]{len(matched)}[/bold] occurrence(s) of {old_text!r}...")

    try:
        n = apply_labels(
            input_path=input_pdf,
            labels=labels,
            output_path=output,
            force=force,
        )
    except (FileNotFoundError, FileExistsError) as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        err_console.print(f"[error]Unexpected error:[/error] {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=2) from exc

    console.print(Panel(
        f"[success]Done![/success] {n} replacement(s) → [bold]{output}[/bold]",
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
# convert command
# ---------------------------------------------------------------------------


@app.command()
def convert(
    input_file: Annotated[Path, typer.Argument(help="Path to the source .ai or .pdf file.")],
    to: Annotated[
        str, typer.Option("--to", help="Output format. Currently only 'pdf' is supported.")
    ] = "pdf",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Destination file path."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite output if it already exists.")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Convert an Adobe Illustrator (.ai) or PDF file to PDF.

    Opens the embedded PDF compatibility layer of a .ai file and saves it as
    a standard PDF. This is the recommended first step before editing .ai files.
    """
    _setup_logging(verbose)

    if not input_file.exists():
        err_console.print(f"[error]Error:[/error] File not found: {input_file}")
        raise typer.Exit(code=1)

    try:
        file_type = detect_file_type(input_file)
    except ValueError as exc:
        err_console.print(f"[error]Error:[/error] {exc}")
        raise typer.Exit(code=1) from exc

    if to.lower() != "pdf":
        err_console.print(f"[error]Error:[/error] Unsupported output format {to!r}. Only 'pdf' is supported.")
        raise typer.Exit(code=1)

    if file_type == "ai":
        console.print(f"[warning]Warning:[/warning] {AI_COMPAT_WARNING}")

    dest = output if output is not None else input_file.with_suffix(".pdf")

    if dest.exists() and not force:
        err_console.print(
            f"[error]Error:[/error] Output already exists: {dest}. Use --force to overwrite."
        )
        raise typer.Exit(code=1)

    try:
        import fitz
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Converting {input_file.name} → PDF...", total=None)
            doc: fitz.Document = fitz.open(str(input_file))
            dest.parent.mkdir(parents=True, exist_ok=True)
            doc.save(
                str(dest),
                garbage=4,
                deflate=True,
                expand=True,
            )
            doc.close()
    except Exception as exc:
        err_console.print(f"[error]Unexpected error:[/error] {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=2) from exc

    console.print(Panel(
        f"[success]Done![/success] Converted to [bold]{dest}[/bold]",
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


if __name__ == "__main__":
    app()
