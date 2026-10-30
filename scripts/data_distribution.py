#!/usr/bin/env python3
"""data_distribution.py.

Analyzes dataset conversations and displays distribution statistics across:
1. Config parameters (socratic_level, student_level, hint_frequency,
   mistake_frequency, verbosity, difficulty)
2. Domain parameter
3. Topics under each domain (optional, shown with --show-topics flag)

Supports readable line-by-line formatted output (default) or table output (--format table),
and logs all output to data_distribution.log.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from tabulate import tabulate

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"


def setup_logger(log_file: Path, append: bool = False) -> logging.Logger:
    logger = logging.getLogger("data_distribution")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    # File Handler
    mode = "a" if append else "w"
    file_handler = logging.FileHandler(log_file, mode=mode, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

    return logger


# ── Configuration parameters & expected value ordering ─────────────────────────
CONFIG_SPECS: dict[str, list[str]] = {
    "socratic_level": ["low", "medium", "high"],
    "student_level": ["beginner", "intermediate", "advanced"],
    "hint_frequency": ["low", "medium", "high"],
    "mistake_frequency": ["low", "medium", "high"],
    "verbosity": ["low", "medium", "high"],
    "difficulty": ["easy", "medium", "hard"],
}


def load_dataset(
    data_dir: Path,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    set[str],
    dict[str, set[str]],
]:
    """Scan data directory and load all conversations grouped by folder."""
    folder_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_domains: set[str] = set()
    domain_to_topics: dict[str, set[str]] = defaultdict(set)

    subdirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    for folder in subdirs:
        _ = folder_records[folder.name]

        for json_file in sorted(folder.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as fp:
                    content = json.load(fp)

                records = content if isinstance(content, list) else [content]
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    folder_records[folder.name].append(rec)

                    domain = rec.get("domain")
                    topic = rec.get("topic")
                    if domain:
                        all_domains.add(domain)
                        if topic:
                            domain_to_topics[domain].add(topic)

            except Exception as exc:
                print(f"Warning: Failed to read {json_file}: {exc}", file=sys.stderr)

    return folder_records, all_domains, domain_to_topics


def format_cell(count: int, total: int) -> str:
    """Format cell value as 'count (pct%)'."""
    pct = (count / total * 100.0) if total > 0 else 0.0
    return f"{count} ({pct:.1f}%)"


# ══════════════════════════════════════════════════════════════════════════════
# LINE-BY-LINE FORMATTERS (Readable with clean separation)
# ══════════════════════════════════════════════════════════════════════════════


def format_config_lines(
    param_name: str,
    categories: list[str],
    folder_records: dict[str, list[dict[str, Any]]],
    active_folders: list[str],
    grand_total: int,
) -> str:
    """Render a clean, line-by-line breakdown for a config parameter."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"CONFIG PARAMETER: {param_name}")
    lines.append("=" * 80)

    # 1. Overall Total
    overall_counts: dict[str, int] = {cat: 0 for cat in categories}
    folder_counts_map: dict[str, dict[str, int]] = {}

    for folder in active_folders:
        counts = {cat: 0 for cat in categories}
        for rec in folder_records[folder]:
            val = str(rec.get("config", {}).get(param_name, "")).strip().lower()
            if val in counts:
                counts[val] += 1
                overall_counts[val] += 1
        folder_counts_map[folder] = counts

    lines.append(f"\nOVERALL DATASET TOTAL: {grand_total:,} conversations")
    max_cat_len = max(len(c) for c in categories)
    for cat in categories:
        cnt = overall_counts[cat]
        pct = (cnt / grand_total * 100.0) if grand_total > 0 else 0.0
        lines.append(f"  • {cat.ljust(max_cat_len)} : {cnt:>6,}  ({pct:5.1f}%)")

    lines.append("\n" + "-" * 80)
    lines.append("BREAKDOWN BY FOLDER:")
    lines.append("-" * 80)

    # 2. Folder-by-folder
    for folder in active_folders:
        f_total = len(folder_records[folder])
        f_pct = (f_total / grand_total * 100.0) if grand_total > 0 else 0.0
        counts = folder_counts_map[folder]

        lines.append(f"\n[ {folder} ]")
        lines.append(f"  Folder Total: {f_total:,} ({f_pct:.1f}% of dataset)")

        for cat in categories:
            cnt = counts[cat]
            pct = (cnt / f_total * 100.0) if f_total > 0 else 0.0
            lines.append(f"    • {cat.ljust(max_cat_len)} : {cnt:>5,}  ({pct:5.1f}%)")

    return "\n".join(lines)


def format_domain_lines(
    domains: list[str],
    folder_records: dict[str, list[dict[str, Any]]],
    active_folders: list[str],
    grand_total: int,
) -> str:
    """Render a clean, line-by-line breakdown for domains."""
    sorted_domains = sorted(domains)
    domain_overall_counts: dict[str, int] = defaultdict(int)
    folder_domain_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for folder in active_folders:
        for rec in folder_records[folder]:
            d = rec.get("domain")
            if d:
                domain_overall_counts[d] += 1
                folder_domain_counts[folder][d] += 1

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("DOMAIN DISTRIBUTION")
    lines.append("=" * 80)

    # 1. Overall Total
    lines.append(f"\nOVERALL DATASET TOTAL: {grand_total:,} conversations")
    max_d_len = max(len(d) for d in sorted_domains)

    # Sort domains by frequency descending for the summary
    by_freq = sorted(sorted_domains, key=lambda d: domain_overall_counts[d], reverse=True)
    for d in by_freq:
        cnt = domain_overall_counts[d]
        pct = (cnt / grand_total * 100.0) if grand_total > 0 else 0.0
        lines.append(f"  • {d.ljust(max_d_len)} : {cnt:>5,}  ({pct:5.1f}%)")

    lines.append("\n" + "-" * 80)
    lines.append("BREAKDOWN BY FOLDER:")
    lines.append("-" * 80)

    # 2. Folder-by-folder
    for folder in active_folders:
        f_total = len(folder_records[folder])
        f_pct = (f_total / grand_total * 100.0) if grand_total > 0 else 0.0
        counts = folder_domain_counts[folder]

        lines.append(f"\n[ {folder} ]")
        lines.append(f"  Folder Total: {f_total:,} ({f_pct:.1f}% of dataset)")

        for d in sorted_domains:
            cnt = counts[d]
            pct = (cnt / f_total * 100.0) if f_total > 0 else 0.0
            lines.append(f"    • {d.ljust(max_d_len)} : {cnt:>4,}  ({pct:5.1f}%)")

    return "\n".join(lines)


def format_topic_lines_for_domain(
    domain: str,
    topics: list[str],
    folder_records: dict[str, list[dict[str, Any]]],
    active_folders: list[str],
    grand_total: int,
) -> str:
    """Render a clean, line-by-line topic breakdown for a specific domain."""
    sorted_topics = sorted(topics)
    max_t_len = max(len(t) for t in sorted_topics)

    # Topic counts
    overall_topic_counts: dict[str, int] = defaultdict(int)
    folder_topic_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    domain_total = 0

    for folder in active_folders:
        for rec in folder_records[folder]:
            if rec.get("domain") == domain:
                domain_total += 1
                t = rec.get("topic")
                if t:
                    overall_topic_counts[t] += 1
                    folder_topic_counts[folder][t] += 1

    domain_pct_dataset = (domain_total / grand_total * 100.0) if grand_total > 0 else 0.0

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"TOPIC DISTRIBUTION: {domain}")
    lines.append(
        f"Domain Total: {domain_total:,} conversations ({domain_pct_dataset:.1f}% of dataset)"
    )
    lines.append("=" * 80)

    # 1. Overall Topic Distribution in this domain (sorted by frequency)
    lines.append(f"\nOVERALL TOPICS IN {domain.upper()}:")
    by_freq = sorted(sorted_topics, key=lambda t: overall_topic_counts[t], reverse=True)
    for t in by_freq:
        cnt = overall_topic_counts[t]
        pct_domain = (cnt / domain_total * 100.0) if domain_total > 0 else 0.0
        lines.append(f"  • {t.ljust(max_t_len)} : {cnt:>4,}  ({pct_domain:5.1f}%)")

    lines.append("\n" + "-" * 80)
    lines.append("BREAKDOWN BY FOLDER:")
    lines.append("-" * 80)

    # 2. Folder-by-folder
    for folder in active_folders:
        counts = folder_topic_counts[folder]
        f_domain_total = sum(counts.values())
        if f_domain_total == 0:
            continue

        f_domain_pct = (
            (f_domain_total / domain_total * 100.0) if domain_total > 0 else 0.0
        )
        lines.append(f"\n[ {folder} ]")
        lines.append(
            f"  {domain.capitalize()} Total in Folder: {f_domain_total:,} ({f_domain_pct:.1f}% of domain total)"
        )

        for t in sorted_topics:
            cnt = counts[t]
            pct = (cnt / f_domain_total * 100.0) if f_domain_total > 0 else 0.0
            lines.append(f"    • {t.ljust(max_t_len)} : {cnt:>3,}  ({pct:5.1f}%)")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# TABULAR FORMATTERS (Optional via --format table)
# ══════════════════════════════════════════════════════════════════════════════


def generate_config_table(
    param_name: str,
    categories: list[str],
    folder_records: dict[str, list[dict[str, Any]]],
    active_folders: list[str],
    grand_total: int,
    table_fmt: str = "grid",
) -> str:
    """Generate a distribution table for a single config parameter."""
    headers = ["Folder"] + [cat.capitalize() for cat in categories] + ["Total"]
    rows = []
    col_totals: dict[str, int] = {cat: 0 for cat in categories}

    for folder in active_folders:
        records = folder_records[folder]
        folder_total = len(records)

        counts = {cat: 0 for cat in categories}
        for rec in records:
            cfg = rec.get("config", {})
            val = str(cfg.get(param_name, "")).strip().lower()
            if val in counts:
                counts[val] += 1

        for cat in categories:
            col_totals[cat] += counts.get(cat, 0)

        row = [folder]
        for cat in categories:
            row.append(format_cell(counts.get(cat, 0), folder_total))

        folder_pct = (folder_total / grand_total * 100.0) if grand_total > 0 else 0.0
        row.append(f"{folder_total} ({folder_pct:.1f}%)")
        rows.append(row)

    total_row = ["TOTAL"]
    for cat in categories:
        tot_cnt = col_totals[cat]
        tot_pct = (tot_cnt / grand_total * 100.0) if grand_total > 0 else 0.0
        total_row.append(f"{tot_cnt} ({tot_pct:.1f}%)")
    total_row.append(f"{grand_total} (100.0%)")
    rows.append(total_row)

    return tabulate(rows, headers=headers, tablefmt=table_fmt)


def generate_domain_summary_table(
    domains: list[str],
    folder_records: dict[str, list[dict[str, Any]]],
    active_folders: list[str],
    grand_total: int,
    table_fmt: str = "grid",
) -> str:
    """Generate a summary table of overall domain counts and percentages."""
    domain_counts: dict[str, int] = defaultdict(int)
    for folder in active_folders:
        for rec in folder_records[folder]:
            d = rec.get("domain")
            if d:
                domain_counts[d] += 1

    headers = ["Domain", "Count", "Percentage"]
    rows = []
    for d in sorted(domains):
        cnt = domain_counts[d]
        pct = (cnt / grand_total * 100.0) if grand_total > 0 else 0.0
        rows.append([d, cnt, f"{pct:.2f}%"])

    rows.append(["TOTAL", grand_total, "100.00%"])
    return tabulate(rows, headers=headers, tablefmt=table_fmt)


def generate_domain_folder_table(
    domains: list[str],
    folder_records: dict[str, list[dict[str, Any]]],
    active_folders: list[str],
    grand_total: int,
    table_fmt: str = "grid",
) -> str:
    """Generate a Folder x Domain table."""
    headers = ["Folder"] + sorted(domains) + ["Total"]
    rows = []
    col_totals: dict[str, int] = {d: 0 for d in domains}

    for folder in active_folders:
        records = folder_records[folder]
        folder_total = len(records)

        counts = {d: 0 for d in domains}
        for rec in records:
            d = rec.get("domain")
            if d in counts:
                counts[d] += 1

        for d in domains:
            col_totals[d] += counts[d]

        row = [folder]
        for d in sorted(domains):
            row.append(format_cell(counts[d], folder_total))

        folder_pct = (folder_total / grand_total * 100.0) if grand_total > 0 else 0.0
        row.append(f"{folder_total} ({folder_pct:.1f}%)")
        rows.append(row)

    total_row = ["TOTAL"]
    for d in sorted(domains):
        tot_cnt = col_totals[d]
        tot_pct = (tot_cnt / grand_total * 100.0) if grand_total > 0 else 0.0
        total_row.append(f"{tot_cnt} ({tot_pct:.1f}%)")
    total_row.append(f"{grand_total} (100.0%)")
    rows.append(total_row)

    return tabulate(rows, headers=headers, tablefmt=table_fmt)


def generate_topic_folder_table_for_domain(
    domain: str,
    topics: list[str],
    folder_records: dict[str, list[dict[str, Any]]],
    active_folders: list[str],
    table_fmt: str = "grid",
) -> str:
    """Generate a topic distribution table across folders for a specific domain."""
    sorted_topics = sorted(topics)
    headers = ["Folder"] + sorted_topics + [f"Total ({domain})"]
    rows = []

    domain_grand_total = 0
    for folder in active_folders:
        for rec in folder_records[folder]:
            if rec.get("domain") == domain:
                domain_grand_total += 1

    col_totals: dict[str, int] = {t: 0 for t in sorted_topics}

    for folder in active_folders:
        records = [r for r in folder_records[folder] if r.get("domain") == domain]
        folder_domain_total = len(records)

        counts = {t: 0 for t in sorted_topics}
        for rec in records:
            t = rec.get("topic")
            if t in counts:
                counts[t] += 1

        for t in sorted_topics:
            col_totals[t] += counts[t]

        row = [folder]
        for t in sorted_topics:
            row.append(format_cell(counts[t], folder_domain_total))

        pct_of_domain = (
            (folder_domain_total / domain_grand_total * 100.0)
            if domain_grand_total > 0
            else 0.0
        )
        row.append(f"{folder_domain_total} ({pct_of_domain:.1f}%)")
        rows.append(row)

    total_row = ["TOTAL"]
    for t in sorted_topics:
        tot_cnt = col_totals[t]
        tot_pct = (
            (tot_cnt / domain_grand_total * 100.0) if domain_grand_total > 0 else 0.0
        )
        total_row.append(f"{tot_cnt} ({tot_pct:.1f}%)")
    total_row.append(f"{domain_grand_total} (100.0%)")
    rows.append(total_row)

    return tabulate(rows, headers=headers, tablefmt=table_fmt)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Display and log distribution statistics for dataset config parameters, domains, and topics."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
        help="Path to the data directory containing model folders (default: ./data)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path(__file__).parent / "data_distribution.log",
        help="Path to log file (default: ./data_distribution.log)",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="line",
        choices=["line", "table"],
        help="Display format: 'line' (clean line-by-line data with separation, default) or 'table' (grid tables)",
    )
    parser.add_argument(
        "--table-style",
        type=str,
        default="grid",
        choices=["grid", "pipe", "simple", "fancy_grid", "github", "rounded_outline"],
        help="Tabulate style when --format is table (default: grid)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        default=False,
        help="Append to log file instead of overwriting (default: False)",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        default=False,
        help="Include folders with 0 conversations (default: False, empty folders are excluded)",
    )
    parser.add_argument(
        "--show-topics",
        "--topics",
        action="store_true",
        default=False,
        help="Enable displaying topic distribution under each domain (default: False)",
    )
    parser.add_argument(
        "--section",
        type=str,
        default="all",
        choices=["all", "config", "domain"],
        help="Section to output: 'all', 'config', or 'domain' (default: all)",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Filter topic breakdown to a specific domain (e.g., chemistry)",
    )

    args = parser.parse_args()

    if not args.data_dir.exists():
        print(f"Error: Data directory '{args.data_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    log = setup_logger(args.log_file, append=args.append)

    log.info("=" * 80)
    log.info("DATA DISTRIBUTION AND CONFIG STATISTICS REPORT")
    log.info("=" * 80)
    log.info("Data Directory : %s", args.data_dir.resolve())
    log.info("Log File       : %s", args.log_file.resolve())
    log.info("Display Format : %s", args.format)
    log.info("Show Topics    : %s", "Yes" if args.show_topics else "No (use --show-topics to view)")

    # 1. Load data
    folder_records, all_domains, domain_to_topics = load_dataset(args.data_dir)
    all_folders = sorted(folder_records.keys())

    # Filter folders
    if args.include_empty:
        active_folders = all_folders
    else:
        active_folders = [f for f in all_folders if len(folder_records[f]) > 0]

    grand_total = sum(len(folder_records[f]) for f in active_folders)

    log.info(
        "Total Folders: %d (Active: %d, Excluded empty: %d)",
        len(all_folders),
        len(active_folders),
        len(all_folders) - len(active_folders),
    )
    log.info("Total Conversations Analyzed: %d", grand_total)
    log.info("=" * 80)

    if grand_total == 0:
        log.warning("No conversation records found in %s", args.data_dir)
        return

    # Section 1: Config Parameters
    if args.section in ("all", "config"):
        log.info("\n" + "#" * 80)
        log.info("# SECTION 1: CONFIG PARAMETERS DISTRIBUTION")
        log.info("#" * 80)

        for param_name, categories in CONFIG_SPECS.items():
            if args.format == "line":
                content = format_config_lines(
                    param_name=param_name,
                    categories=categories,
                    folder_records=folder_records,
                    active_folders=active_folders,
                    grand_total=grand_total,
                )
                log.info("\n" + content)
            else:
                log.info("\n[Config Parameter: %s]", param_name)
                tbl = generate_config_table(
                    param_name=param_name,
                    categories=categories,
                    folder_records=folder_records,
                    active_folders=active_folders,
                    grand_total=grand_total,
                    table_fmt=args.table_style,
                )
                log.info(tbl)

    # Section 2: Domain Distribution
    if args.section in ("all", "domain"):
        log.info("\n" + "#" * 80)
        log.info("# SECTION 2: DOMAIN DISTRIBUTION")
        log.info("#" * 80)

        if args.format == "line":
            content = format_domain_lines(
                domains=sorted(all_domains),
                folder_records=folder_records,
                active_folders=active_folders,
                grand_total=grand_total,
            )
            log.info("\n" + content)
        else:
            log.info("\n[Domain Overall Summary]")
            summary_tbl = generate_domain_summary_table(
                domains=sorted(all_domains),
                folder_records=folder_records,
                active_folders=active_folders,
                grand_total=grand_total,
                table_fmt=args.table_style,
            )
            log.info(summary_tbl)

            log.info("\n[Folder × Domain Distribution Breakdown]")
            folder_domain_tbl = generate_domain_folder_table(
                domains=sorted(all_domains),
                folder_records=folder_records,
                active_folders=active_folders,
                grand_total=grand_total,
                table_fmt=args.table_style,
            )
            log.info(folder_domain_tbl)

    # Section 3: Topic Breakdown (Only if --show-topics flag is on)
    if args.show_topics:
        log.info("\n" + "#" * 80)
        log.info("# SECTION 3: TOPIC DISTRIBUTION UNDER EACH DOMAIN")
        log.info("#" * 80)

        selected_domains = sorted(all_domains)
        if args.domain:
            if args.domain not in all_domains:
                log.error(
                    "Specified domain '%s' not found. Available: %s",
                    args.domain,
                    sorted(all_domains),
                )
                return
            selected_domains = [args.domain]

        for d in selected_domains:
            topics = sorted(domain_to_topics[d])
            if args.format == "line":
                content = format_topic_lines_for_domain(
                    domain=d,
                    topics=topics,
                    folder_records=folder_records,
                    active_folders=active_folders,
                    grand_total=grand_total,
                )
                log.info("\n" + content)
            else:
                log.info("\n--- Domain: %s (%d topics) ---", d, len(topics))
                topic_tbl = generate_topic_folder_table_for_domain(
                    domain=d,
                    topics=topics,
                    folder_records=folder_records,
                    active_folders=active_folders,
                    table_fmt=args.table_style,
                )
                log.info(topic_tbl)

    log.info("\n" + "=" * 80)
    log.info("REPORT COMPLETE — Log saved to %s", args.log_file.resolve())
    log.info("=" * 80)


if __name__ == "__main__":
    main()
