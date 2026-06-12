#!/usr/bin/env python3
import argparse
import fnmatch
import re
import subprocess
from pathlib import Path

ENDPOINT = "root://eosuser.cern.ch"
PATTERN = "output_*.root"

def canonical_eos_path(path: str) -> str:
    match = re.match(r"^/eos/home-([^/]+)/([^/]+)(/.*)?$", path)
    if match:
        tail = match.group(3) or ""
        return f"/eos/user/{match.group(1)}/{match.group(2)}{tail}"
    return path


def eos_path(path: str) -> str:
    if path.startswith(ENDPOINT + "//"):
        path = "/" + path.split("//", 2)[2]
    return canonical_eos_path(path)


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
    path = eos_path(path)
    ret, _, _ = run_cmd(["xrdfs", ENDPOINT, "stat", path])
    return ret == 0


def path_exists(path: str) -> bool:
    path = eos_path(path)
    if path.startswith("/eos/"):
        return eos_exists(path)
    p = Path(path)
    return p.exists()


def list_files_recursive(base: Path):
    base_path = eos_path(base.as_posix())
    if base_path.startswith("/eos/"):
        if not eos_exists(base_path):
            return []

        ret, out, err = run_cmd(["xrdfs", ENDPOINT, "ls", "-R", base_path])
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


def output_status(output_eos: str) -> str:
    output_eos = eos_path(output_eos)
    if not path_exists(output_eos):
        return "missing"

    import uproot

    try:
        with uproot.open(output_eos) as root_file:
            required = (
                "profile_rpc_fiducial_matched_delta_p_by_probe_p",
                "profile_rpc_fiducial_matched_cls_by_abs_probe_at_rpc_dxdz_station",
                "profile_rpc_fiducial_matched_cls_by_probe_at_rpc_pt_station",
            )
            return "ok" if all(name in root_file for name in required) else "no_hist"
    except Exception:
        return "broken"


def build_record(input_base: Path, output_base: Path, cert_path: Path, infile: Path):
    rel = infile.relative_to(input_base)
    pd = input_base.parent.name
    dataset_name = input_base.name

    return {
        "input_eos": eos_path(infile.as_posix()),
        "cert_path": eos_path(cert_path.as_posix()),
        "output_eos": eos_path((output_base / rel).as_posix()),
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

    max_files = args.max_files or 0
    if max_files > 0:
        records = records[:max_files]

    write_items(args.items_file, records)

    print(f"pd={args.input_base.parent.name}")
    print(f"dataset={args.input_base.name}")
    print(f"inputs={len(files)}")
    print(f"selected={len(records)}")
    print(f"items_file={args.items_file}")


def cmd_missing(args):
    records = read_items(args.items_all_file)
    selected = []
    counts = {}
    for rec in records:
        status = output_status(rec["output_eos"])
        counts[status] = counts.get(status, 0) + 1
        if status != "ok":
            selected.append(rec)

    write_items(args.items_out_file, selected)

    print(f"total={len(records)}")
    for status in ("ok", "missing", "broken", "no_hist"):
        if counts.get(status, 0):
            print(f"{status}={counts[status]}")
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
    p_make.add_argument("--max-files", type=int)
    p_make.set_defaults(func=cmd_make)

    p_missing = subparsers.add_parser("missing")
    p_missing.add_argument("items_all_file", type=Path)
    p_missing.add_argument("items_out_file", type=Path)
    p_missing.set_defaults(func=cmd_missing)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
