#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

ENDPOINT = "root://eosuser.cern.ch"
INPUT_PATTERN = "output_*.root"
INPUT_SEPARATOR = "|"


@dataclass(frozen=True)
class ItemRecord:
    input_eos: str
    cert_path: str
    output_eos: str
    pd: str
    dataset_name: str

    @classmethod
    def from_line(cls, line: str, lineno: int) -> "ItemRecord":
        cols = line.split()
        if len(cols) != 5:
            raise RuntimeError(
                f"Malformed items file at line {lineno}: expected 5 columns, got {len(cols)}"
            )
        if INPUT_SEPARATOR not in cols[0] and "," in cols[0]:
            cols[0] = cols[0].replace(",", INPUT_SEPARATOR)
        return cls(*cols)

    def to_line(self) -> str:
        return " ".join((self.input_eos, self.cert_path, self.output_eos, self.pd, self.dataset_name))


def canonical_eos_path(path: str) -> str:
    match = re.match(r"^/eos/home-([^/]+)/([^/]+)(/.*)?$", path)
    if not match:
        return path
    tail = match.group(3) or ""
    return f"/eos/user/{match.group(1)}/{match.group(2)}{tail}"


def eos_path(path: str) -> str:
    if path.startswith(ENDPOINT + "//"):
        path = "/" + path.split("//", 2)[2]
    return canonical_eos_path(path)


def is_eos_path(path: str) -> bool:
    return eos_path(path).startswith("/eos/")


def run_cmd(cmd: Sequence[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def natural_path_key(path: Path):
    return [int(part) if part.isdigit() else part for part in re.split(r"([0-9]+)", path.as_posix())]


def local_root_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted((p for p in base.rglob(INPUT_PATTERN) if p.is_file()), key=natural_path_key)


def eos_exists(path: str) -> bool:
    path = eos_path(path)
    ret, _, _ = run_cmd(["xrdfs", ENDPOINT, "stat", path])
    return ret == 0 or Path(path).exists()


def path_exists(path: str) -> bool:
    path = eos_path(path)
    return eos_exists(path) if path.startswith("/eos/") else Path(path).exists()


def parse_xrdfs_listing(stdout: str) -> list[Path]:
    files = []
    for line in stdout.splitlines():
        path = Path(line.strip())
        if fnmatch.fnmatch(path.name, INPUT_PATTERN):
            files.append(path)
    return sorted(files, key=natural_path_key)


def eos_root_files(base_path: str) -> list[Path]:
    if not eos_exists(base_path):
        return []

    ret, out, err = run_cmd(["xrdfs", ENDPOINT, "ls", "-R", base_path])
    if ret == 0:
        return parse_xrdfs_listing(out)

    local_files = local_root_files(Path(base_path))
    if Path(base_path).exists():
        return local_files

    raise RuntimeError(
        f"Failed to list EOS path: {base_path}\nstdout:\n{out}\nstderr:\n{err}"
    )


def list_root_files(base: Path) -> list[Path]:
    base_path = eos_path(base.as_posix())
    if is_eos_path(base_path):
        return eos_root_files(base_path)
    return local_root_files(Path(base_path))


def chunked_files(files: Sequence[Path], chunk_size: int) -> Iterable[tuple[int, Sequence[Path]]]:
    for start in range(0, len(files), chunk_size):
        yield start, files[start:start + chunk_size]


def output_base_for_record(record: ItemRecord) -> str:
    output_eos = eos_path(record.output_eos)
    marker = f"/{record.pd}/{record.dataset_name}/"
    marker_index = output_eos.rfind(marker)
    if marker_index >= 0:
        return output_eos[: marker_index + len(marker) - 1]
    return Path(output_eos).parent.as_posix()


def list_existing_outputs(records: Sequence[ItemRecord]) -> set[str]:
    existing = set()
    bases = sorted({output_base_for_record(record) for record in records})
    for base in bases:
        existing.update(eos_path(path.as_posix()) for path in list_root_files(Path(base)))
    return existing


def output_status(record: ItemRecord, existing_paths: Optional[set[str]] = None) -> str:
    output_eos = eos_path(record.output_eos)
    exists = path_exists(output_eos) if existing_paths is None else output_eos in existing_paths
    return "ok" if exists else "missing"


def make_record(
    input_base: Path,
    output_base: Path,
    cert_path: Path,
    files: Sequence[Path],
    start_index: int,
) -> ItemRecord:
    pd = input_base.parent.name
    dataset_name = input_base.name
    end_index = start_index + len(files) - 1

    return ItemRecord(
        input_eos=INPUT_SEPARATOR.join(eos_path(path.as_posix()) for path in files),
        cert_path=eos_path(cert_path.as_posix()),
        output_eos=eos_path((output_base / f"output_{start_index}_{end_index}.root").as_posix()),
        pd=pd,
        dataset_name=dataset_name,
    )


def make_records(
    input_base: Path,
    output_base: Path,
    cert_path: Path,
    files: Sequence[Path],
    files_per_job: int,
) -> list[ItemRecord]:
    return [
        make_record(input_base, output_base, cert_path, group, start)
        for start, group in chunked_files(files, files_per_job)
    ]


def write_items(path: Path, records: Sequence[ItemRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        for record in records:
            stream.write(record.to_line() + "\n")


def read_items(path: Path) -> list[ItemRecord]:
    records = []
    with path.open() as stream:
        for lineno, line in enumerate(stream, start=1):
            line = line.strip()
            if line:
                records.append(ItemRecord.from_line(line, lineno))
    return records


def selected_inputs(files: Sequence[Path], max_files: Optional[int]) -> Sequence[Path]:
    if max_files is None or max_files <= 0:
        return files
    return files[:max_files]


def cmd_make(args: argparse.Namespace) -> None:
    files = list_root_files(args.input_base)
    if not files:
        raise RuntimeError(f"No input files found under {args.input_base}")
    if args.files_per_job <= 0:
        raise RuntimeError(f"--files-per-job must be positive, got {args.files_per_job}")

    selected = selected_inputs(files, args.max_files)
    records = make_records(
        args.input_base,
        args.output_base,
        args.cert_path.resolve(),
        selected,
        args.files_per_job,
    )
    write_items(args.items_file, records)

    print(f"pd={args.input_base.parent.name}")
    print(f"dataset={args.input_base.name}")
    print(f"inputs={len(files)}")
    print(f"selected_inputs={len(selected)}")
    print(f"files_per_job={args.files_per_job}")
    print(f"items={len(records)}")
    print(f"items_file={args.items_file}")


def cmd_missing(args: argparse.Namespace) -> None:
    records = read_items(args.items_all_file)
    existing_paths = list_existing_outputs(records)
    counts: dict[str, int] = {}
    selected = []

    for record in records:
        status = output_status(record, existing_paths)
        counts[status] = counts.get(status, 0) + 1
        if status != "ok":
            selected.append(record)

    write_items(args.items_out_file, selected)

    print(f"total={len(records)}")
    for status in ("ok", "missing"):
        if counts.get(status, 0):
            print(f"{status}={counts[status]}")
    print(f"selected={len(selected)}")
    print(f"items_out_file={args.items_out_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_make = subparsers.add_parser("make")
    p_make.add_argument("input_base", type=Path)
    p_make.add_argument("output_base", type=Path)
    p_make.add_argument("cert_path", type=Path)
    p_make.add_argument("items_file", type=Path)
    p_make.add_argument("--max-files", type=int)
    p_make.add_argument("--files-per-job", type=int, default=1)
    p_make.set_defaults(func=cmd_make)

    p_missing = subparsers.add_parser("missing")
    p_missing.add_argument("items_all_file", type=Path)
    p_missing.add_argument("items_out_file", type=Path)
    p_missing.set_defaults(func=cmd_missing)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
