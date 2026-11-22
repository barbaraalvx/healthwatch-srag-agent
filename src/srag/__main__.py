"""Command line interface: python -m srag [--uf SP] [--no-pdf] [--output-dir DIR]."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from srag import service
from srag.config import get_settings
from srag.data.repository import NoCasesError
from srag.guardrails.input import InvalidRequestError
from srag.news.client import NewsSearchError
from srag.service import DataNotPreparedError, ReportResult

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INVALID_REQUEST = 2
STATUS_COMPLETED = "completed"
# Problems the user can fix: shown as one clear line, without a stack trace.
EXPECTED_ERRORS = (DataNotPreparedError, NoCasesError, NewsSearchError)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m srag", description="Generate an SRAG report (HTML and PDF)."
    )
    parser.add_argument("--uf", help="state code, e.g. SP (default: all of Brazil)")
    parser.add_argument("--no-pdf", action="store_true", help="write only the HTML report")
    parser.add_argument(
        "--output-dir", type=Path, help="folder for the run folders (default: reports/)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one report and print where the files are. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    if args.output_dir:
        settings = settings.model_copy(update={"reports_dir": args.output_dir.resolve()})
    try:
        result = service.generate_report(args.uf, settings=settings, with_pdf=not args.no_pdf)
    except InvalidRequestError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INVALID_REQUEST
    except EXPECTED_ERRORS as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    except Exception as error:
        logger.debug("Unexpected failure", exc_info=True)
        print(
            f"error: the run failed ({type(error).__name__}). "
            "See the audit log of the run folder, or set LOG_LEVEL=DEBUG.",
            file=sys.stderr,
        )
        return EXIT_FAILURE
    print_summary(result)
    return EXIT_OK


def print_summary(result: ReportResult) -> None:
    print(f"Run {result.run_id}: {result.status}")
    if result.status != STATUS_COMPLETED:
        print(
            f"The automatic text was not generated ({result.stop_reason or 'validation failed'})."
        )
    print(f"HTML:     {result.html_path}")
    print(f"PDF:      {result.pdf_path or 'not generated'}")
    print(f"Audit:    {result.audit_path}")
    print(f"Manifest: {result.manifest_path}")


if __name__ == "__main__":
    raise SystemExit(main())
