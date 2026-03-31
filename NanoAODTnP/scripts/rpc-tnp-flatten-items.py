#!/usr/bin/env python3
import argparse
import fnmatch
import subprocess
from pathlib import Path

ENDPOINT = "root://eosuser.cern.ch"
PATTERN = "output_*.root"


def run_cmd(cmd):
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def eos_exists(path: str) -> bool:
    ret, _, _ = run_cmd(["xrdfs", ENDPOINT, "stat", path])
    return ret == 0


def path_exists(path: str) -> bool:
    p = Path(path)
    if p.as_posix().startswith("/eos/"):
        return eos_exists(p.as_posix())
    return p.exists()


def list_files_recursive(base: Path):
    if base.as_posix().startswith("/eos/"):
        if not eos_exists(base.as_posix()):
            return []

        ret, out, err = run_cmd(["xrdfs", ENDPOINT, "ls", "-R", base.as_posix()])
        if ret != 0:
            raise RuntimeError(
                f"Failed to list EOS path: {base}\nstdout:\n{out}\nstderr:\n{err}"
            )

        files = []
        for line in out.splitlines():
            p = Path(line.strip())
            if fnmatch.fnmatch(p.name, PATTERN):
                files.append(p)
        return sorted(files)

    if not base.exists():
        return []

    return sorted(p for p in base.rglob(PATTERN) if p.is_file())


def empty_path_from_output(path: str) -> str:
    p = Path(path)
    if p.suffix == ".root":
        return p.with_suffix(".empty").as_posix()
    return path + ".empty"


def terminal_exists(output_eos: str) -> bool:
    return path_exists(output_eos) or path_exists(empty_path_from_output(output_eos))


def build_record(input_base: Path, output_base: Path, cert_path: Path, infile: Path):
    rel = infile.relative_to(input_base)
    pd = input_base.parent.name
    dataset_name = input_base.name

    return {
        "input_eos": infile.as_posix(),
        "cert_path": cert_path.as_posix(),
        "output_eos": (output_base / rel).as_posix(),
        "pd": pd,
        "dataset_name": dataset_name,
    }


def write_items(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            cols = [
                rec["input_eos"],
                rec["cert_path"],
                rec["output_eos"],
                rec["pd"],
                rec["dataset_name"],
            ]
            f.write(" ".join(cols) + "\n")


def read_items(path: Path):
    records = []
    with open(path) as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            cols = line.split()
            if len(cols) != 5:
                raise RuntimeError(
                    f"Malformed items file at line {lineno}: expected 5 columns, got {len(cols)}"
                )

            records.append(
                {
                    "input_eos": cols[0],
                    "cert_path": cols[1],
                    "output_eos": cols[2],
                    "pd": cols[3],
                    "dataset_name": cols[4],
                }
            )

    return records


def cmd_make(args):
    files = list_files_recursive(args.input_base)
    if not files:
        raise RuntimeError(f"No input files found under {args.input_base}")

    records = [
        build_record(args.input_base, args.output_base, args.cert_path.resolve(), infile)
        for infile in files
    ]

    if args.max_files > 0:
        records = records[:args.max_files]

    write_items(args.items_file, records)

    print(f"pd={args.input_base.parent.name}")
    print(f"dataset={args.input_base.name}")
    print(f"inputs={len(files)}")
    print(f"selected={len(records)}")
    print(f"items_file={args.items_file}")


def cmd_missing(args):
    records = read_items(args.items_all_file)
    selected = [rec for rec in records if not terminal_exists(rec["output_eos"])]

    write_items(args.items_out_file, selected)

    print(f"total={len(records)}")
    print(f"selected={len(selected)}")
    print(f"items_out_file={args.items_out_file}")


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_make = subparsers.add_parser("make")
    p_make.add_argument("input_base", type=Path)
    p_make.add_argument("output_base", type=Path)
    p_make.add_argument("cert_path", type=Path)
    p_make.add_argument("items_file", type=Path)
    p_make.add_argument("--max-files", type=int, default=0)
    p_make.set_defaults(func=cmd_make)

    p_missing = subparsers.add_parser("missing")
    p_missing.add_argument("items_all_file", type=Path)
    p_missing.add_argument("items_out_file", type=Path)
    p_missing.set_defaults(func=cmd_missing)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()