#!/usr/bin/env python3
import argparse
import csv
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path


DATASET_RE = re.compile(
    r"^(?P<pd>[A-Za-z0-9]+)_(?P<era>Run(?P<year>\d{4})(?P<subera>[A-Z]))-(?P<reco>.+)-v(?P<version>\d+)$"
)


def run_cmd(cmd):
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc.stdout


def split_csv_line(line: str):
    return [x.strip() for x in next(csv.reader([line]))]


def normalize_csvish_line(line: str) -> str:
    text = line.strip()
    if not text:
        return ""
    if text.startswith("#"):
        text = text[1:].strip()
    return text


def has_any_lumi(data: dict[str, list[list[int]]]) -> bool:
    for ranges in data.values():
        if ranges:
            return True
    return False


def parse_brilcalc_text(text: str) -> tuple[float, float]:
    lines = text.splitlines()

    # Pass 1:
    # Parse summary block:
    # nfill,nrun,nls,ncms,totdelivered(/fb),totrecorded(/fb)
    for i, raw in enumerate(lines):
        body = normalize_csvish_line(raw)
        if not body or "," not in body:
            continue

        fields = [x.lower() for x in split_csv_line(body)]

        delivered_idx = None
        recorded_idx = None
        for j, field in enumerate(fields):
            if "totdelivered" in field:
                delivered_idx = j
            if "totrecorded" in field:
                recorded_idx = j

        if delivered_idx is None or recorded_idx is None:
            continue

        for raw2 in lines[i + 1:]:
            body2 = normalize_csvish_line(raw2)
            if not body2 or "," not in body2:
                continue

            values = split_csv_line(body2)
            if len(values) <= max(delivered_idx, recorded_idx):
                continue

            try:
                delivered = float(values[delivered_idx])
                recorded = float(values[recorded_idx])
                return delivered, recorded
            except ValueError:
                continue

    # Pass 2:
    # Parse per-LS block and sum delivered/recorded columns:
    # run:fill,ls,time,beamstatus,energy,delivered(/fb),recorded(/fb),avgpu,source
    for i, raw in enumerate(lines):
        body = normalize_csvish_line(raw)
        if not body or "," not in body:
            continue

        fields = [x.lower() for x in split_csv_line(body)]

        delivered_idx = None
        recorded_idx = None
        for j, field in enumerate(fields):
            if "totdelivered" in field or "totrecorded" in field:
                continue
            if field.startswith("delivered(") or field == "delivered":
                delivered_idx = j
            if field.startswith("recorded(") or field == "recorded":
                recorded_idx = j

        if delivered_idx is None or recorded_idx is None:
            continue

        delivered_sum = 0.0
        recorded_sum = 0.0
        found_numeric_row = False

        for raw2 in lines[i + 1:]:
            body2 = normalize_csvish_line(raw2)
            if not body2:
                continue

            if "," not in body2:
                if found_numeric_row:
                    break
                continue

            values = split_csv_line(body2)
            if len(values) <= max(delivered_idx, recorded_idx):
                if found_numeric_row:
                    break
                continue

            try:
                delivered_sum += float(values[delivered_idx])
                recorded_sum += float(values[recorded_idx])
                found_numeric_row = True
            except ValueError:
                if found_numeric_row:
                    break
                continue

        if found_numeric_row:
            return delivered_sum, recorded_sum

    raise RuntimeError("Could not parse delivered/recorded lumi from brilcalc text")


def parse_brilcalc_csv(csv_path: Path) -> tuple[float, float]:
    text = csv_path.read_text() if csv_path.exists() else ""
    return parse_brilcalc_text(text)


def brilcalc_from_json(json_path: Path) -> tuple[float, float]:
    data = load_lumi_json(json_path)
    if not has_any_lumi(data):
        return 0.0, 0.0

    with tempfile.TemporaryDirectory() as tmpdir:
        out_csv = Path(tmpdir) / "brilcalc.csv"

        proc = subprocess.run(
            ["brilcalc", "lumi", "-u", "/fb", "-i", str(json_path), "-o", str(out_csv)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                f"brilcalc failed for {json_path}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )

        file_text = out_csv.read_text() if out_csv.exists() else ""
        parse_text = file_text.strip()

        if not parse_text:
            parse_text = (proc.stdout or "") + "\n" + (proc.stderr or "")

        try:
            return parse_brilcalc_text(parse_text)
        except RuntimeError as e:
            preview = "\n".join(parse_text.splitlines()[:40])
            raise RuntimeError(
                f"{e}\n"
                f"[json] {json_path}\n"
                f"[brilcalc preview]\n{preview}\n"
            ) from None


def load_lumi_json(json_path: Path) -> dict[str, list[list[int]]]:
    with json_path.open() as f:
        data = json.load(f)

    out = {}
    for run, ranges in data.items():
        out[str(run)] = [[int(a), int(b)] for a, b in ranges]
    return out


def merge_ranges(ranges: list[list[int]]) -> list[list[int]]:
    if not ranges:
        return []

    ranges = sorted(ranges, key=lambda x: (x[0], x[1]))
    merged = [ranges[0][:]]

    for start, end in ranges[1:]:
        last = merged[-1]
        if start <= last[1] + 1:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])

    return merged


def union_lumi_json(json_list: list[dict[str, list[list[int]]]]) -> dict[str, list[list[int]]]:
    by_run = defaultdict(list)

    for data in json_list:
        for run, ranges in data.items():
            by_run[str(run)].extend(ranges)

    out = {}
    for run, ranges in sorted(by_run.items(), key=lambda x: int(x[0])):
        out[run] = merge_ranges(ranges)

    return out


def count_lumisections(data: dict[str, list[list[int]]]) -> int:
    total = 0
    for ranges in data.values():
        for start, end in ranges:
            total += end - start + 1
    return total


def write_json(path: Path, data: dict[str, list[list[int]]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, sort_keys=True, indent=2)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_dataset_name(name: str) -> tuple[str, str]:
    m = DATASET_RE.match(name)
    if m is None:
        raise ValueError(f"Unrecognized dataset directory name: {name}")

    d = m.groupdict()
    era = d["era"]
    year = f"Run{d['year']}"
    return era, year


def dataset_row(dataset_dir: Path):
    dataset = dataset_dir.name

    try:
        parse_dataset_name(dataset)
    except ValueError:
        return None

    json_path = dataset_dir / "processedLumis.json"
    json_golden_path = dataset_dir / "processedLumis_Golden.json"

    if not json_path.exists() or not json_golden_path.exists():
        return None

    lumi_json = load_lumi_json(json_path)
    lumi_json_golden = load_lumi_json(json_golden_path)

    delivered_fb, recorded_fb = brilcalc_from_json(json_path)
    delivered_golden_fb, recorded_golden_fb = brilcalc_from_json(json_golden_path)

    return {
        "dataset": dataset,
        "delivered_fb": delivered_fb,
        "delivered_golden_fb": delivered_golden_fb,
        "recorded_fb": recorded_fb,
        "recorded_golden_fb": recorded_golden_fb,
        "run": len(lumi_json),
        "run_golden": len(lumi_json_golden),
        "ls": count_lumisections(lumi_json),
        "ls_golden": count_lumisections(lumi_json_golden),
    }


def summarize_datasets(input_dir: Path) -> list[dict]:
    rows = []

    for dataset_dir in sorted(input_dir.iterdir()):
        if not dataset_dir.is_dir():
            continue

        row = dataset_row(dataset_dir)
        if row is not None:
            rows.append(row)

    return rows


def summarize_group(input_dir: Path, group_key: str, output_dir: Path) -> list[dict]:
    grouped_processed = defaultdict(list)
    grouped_golden = defaultdict(list)

    for dataset_dir in sorted(input_dir.iterdir()):
        if not dataset_dir.is_dir():
            continue

        dataset = dataset_dir.name
        try:
            era, year = parse_dataset_name(dataset)
        except ValueError:
            continue

        group_name = era if group_key == "era" else year

        json_path = dataset_dir / "processedLumis.json"
        json_golden_path = dataset_dir / "processedLumis_Golden.json"

        if not json_path.exists() or not json_golden_path.exists():
            continue

        grouped_processed[group_name].append(load_lumi_json(json_path))
        grouped_golden[group_name].append(load_lumi_json(json_golden_path))

    rows = []

    tmp_dir = output_dir / f"_tmp_union_{group_key}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for group_name in sorted(grouped_processed):
        union_processed = union_lumi_json(grouped_processed[group_name])
        union_golden = union_lumi_json(grouped_golden[group_name])

        json_path = tmp_dir / f"{group_name}.json"
        json_golden_path = tmp_dir / f"{group_name}_golden.json"

        write_json(json_path, union_processed)
        write_json(json_golden_path, union_golden)

        delivered_fb, recorded_fb = brilcalc_from_json(json_path)
        delivered_golden_fb, recorded_golden_fb = brilcalc_from_json(json_golden_path)

        rows.append(
            {
                group_key: group_name,
                "delivered_fb": delivered_fb,
                "delivered_golden_fb": delivered_golden_fb,
                "recorded_fb": recorded_fb,
                "recorded_golden_fb": recorded_golden_fb,
                "run": len(union_processed),
                "run_golden": len(union_golden),
                "ls": count_lumisections(union_processed),
                "ls_golden": count_lumisections(union_golden),
            }
        )

    return rows


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        required=True,
        type=Path,
        help="Directory like logs/lumi/v1",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        type=Path,
        help="Default: <input-dir>/summary",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or (input_dir / "summary")
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_rows = summarize_datasets(input_dir)
    era_rows = summarize_group(input_dir, "era", output_dir)
    year_rows = summarize_group(input_dir, "year", output_dir)

    write_csv(
        output_dir / "lumi_dataset.csv",
        dataset_rows,
        [
            "dataset",
            "delivered_fb",
            "delivered_golden_fb",
            "recorded_fb",
            "recorded_golden_fb",
            "run",
            "run_golden",
            "ls",
            "ls_golden",
        ],
    )

    write_csv(
        output_dir / "lumi_era.csv",
        era_rows,
        [
            "era",
            "delivered_fb",
            "delivered_golden_fb",
            "recorded_fb",
            "recorded_golden_fb",
            "run",
            "run_golden",
            "ls",
            "ls_golden",
        ],
    )

    write_csv(
        output_dir / "lumi_year.csv",
        year_rows,
        [
            "year",
            "delivered_fb",
            "delivered_golden_fb",
            "recorded_fb",
            "recorded_golden_fb",
            "run",
            "run_golden",
            "ls",
            "ls_golden",
        ],
    )

    print(f"[INFO] wrote {output_dir / 'lumi_dataset.csv'}")
    print(f"[INFO] wrote {output_dir / 'lumi_era.csv'}")
    print(f"[INFO] wrote {output_dir / 'lumi_year.csv'}")


if __name__ == "__main__":
    main()