#!/usr/bin/env python3
import argparse
import re
import sys
import subprocess
from pathlib import Path

import htcondor2 as htcondor
from htcondor2 import Schedd, Submit


CERT_MAP = {
    "2022": "Cert_Collisions2022_355100_362760_Golden.json",
    "2023": "Cert_Collisions2023_366442_370790_Golden.json",
    "2024": "Cert_Collisions2024_378981_386951_Golden.json",
    "2025": "Cert_Collisions2025_391658_398903_Golden.json",
}


def run_cmd(cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return proc.returncode, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")


def detect_storage(path: Path) -> str:
    p = path.as_posix()
    if p.startswith("/eos/"):
        return "eos"
    if p.startswith("/hdfs/"):
        return "hdfs"
    return "local"


def to_hdfs_namespace(path: Path) -> str:
    p = path.as_posix()
    return p[5:] if p.startswith("/hdfs/") else p


def get_year(path: Path) -> str:
    m = re.search(r"Run(20\d{2})", path.as_posix())
    if not m:
        raise ValueError(f"Cannot determine year from path: {path}")
    return m.group(1)


def list_files_recursive(base: Path, pattern: str):
    backend = detect_storage(base)

    if backend != "hdfs":
        return sorted(p for p in base.rglob(pattern) if p.is_file())

    ns = to_hdfs_namespace(base)
    ret, out, err = run_cmd(["hdfs", "dfs", "-ls", "-R", ns])
    if ret != 0:
        raise RuntimeError(f"hdfs dfs -ls failed for {ns}\n{err}")

    regex = re.compile("^" + pattern.replace(".", r"\.").replace("*", ".*") + "$")
    files = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Found "):
            continue
        parts = line.split()
        if not parts:
            continue
        path_str = parts[-1]
        if regex.match(Path(path_str).name):
            files.append(Path("/hdfs") / path_str.lstrip("/"))
    return sorted(files)


def path_exists_and_nonempty(path: Path) -> bool:
    backend = detect_storage(path)

    if backend != "hdfs":
        return path.is_file() and path.stat().st_size >= 0

    ns = to_hdfs_namespace(path)
    ret, _, _ = run_cmd(["hdfs", "dfs", "-test", "-e", ns])
    return ret == 0


def done_exists(output_path: Path) -> bool:
    return path_exists_and_nonempty(Path(str(output_path) + ".done"))


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-i", "--input-base", type=Path, required=True)
    parser.add_argument("-o", "--output-base", type=Path, required=True)
    parser.add_argument("-s", "--script", type=Path, required=True)
    parser.add_argument("-c", "--cert-dir", type=Path, required=True)
    parser.add_argument("-n", "--name", type=str, default="rpcTnP")
    parser.add_argument("--pattern", type=str, default="output_*.root")
    parser.add_argument("--endpoint", type=str, default="root://eosuser.cern.ch")
    parser.add_argument("--submit-dir", type=Path, default=Path("./logs/condor"))
    parser.add_argument("--memory", type=str, default="2GB")
    parser.add_argument("--disk", type=str, default="2GB")
    parser.add_argument("--cpus", type=int, default=1)
    parser.add_argument("--batch-name", type=str, default="rpcTnPFlatten")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_base = args.input_base
    output_base = args.output_base
    script = args.script.resolve()
    cert_dir = args.cert_dir.resolve()
    submit_dir = args.submit_dir.resolve()

    if detect_storage(input_base) == "local" and not input_base.exists():
        raise FileNotFoundError(f"Input base not found: {input_base}")
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")
    if not cert_dir.exists():
        raise FileNotFoundError(f"Cert dir not found: {cert_dir}")

    submit_dir.mkdir(parents=True, exist_ok=True)

    files = list_files_recursive(input_base, args.pattern)
    if not files:
        raise RuntimeError(f"No files matched: {input_base}/**/{args.pattern}")

    itemdata = []
    skipped = 0
    python_exec = Path(sys.executable).resolve()

    for f in files:
        rel = f.relative_to(input_base)
        out = output_base / rel

        if not args.force and done_exists(out):
            skipped += 1
            continue

        year = get_year(f)
        cert = cert_dir / CERT_MAP[year]
        if not cert.exists():
            raise FileNotFoundError(f"Cert file not found: {cert}")

        log_dir = submit_dir / rel.parent
        log_dir.mkdir(parents=True, exist_ok=True)

        itemdata.append({
            "input_file": str(f),
            "cert_file": str(cert),
            "cert_name": cert.name,
            "script_file": str(script),
            "script_name": script.name,
            "output_file": str(out),
            "log_dir": str(log_dir),
            "stem": f.stem,
            "name": args.name,
            "endpoint": args.endpoint,
        })

    print(f"found   : {len(files)}")
    print(f"skip    : {skipped}")
    print(f"submit  : {len(itemdata)}")

    if not itemdata:
        print("Nothing to submit")
        return

    submit = Submit({
        "universe": "vanilla",
        "getenv": "True",
        "executable": str(python_exec),
        "transfer_executable": "False",
        "arguments": (
            "$(script_name) "
            "-i $(input_file) "
            "-c $(cert_name) "
            "-o $(output_file) "
            "-n $(name) "
            "--endpoint $(endpoint)"
        ),
        "should_transfer_files": "YES",
        "when_to_transfer_output": "ON_SUCCESS",
        "success_exit_code": "0",
        "transfer_input_files": "$(script_file),$(cert_file)",
        "request_cpus": str(args.cpus),
        "request_memory": str(args.memory),
        "request_disk": str(args.disk),
        "max_retries": str(args.max_retries),
        "JobBatchName": args.batch_name,
        "output": "$(log_dir)/$(stem).$(ClusterId).$(ProcId).out",
        "error": "$(log_dir)/$(stem).$(ClusterId).$(ProcId).err",
        "log": "$(log_dir)/$(stem).$(ClusterId).log",
    })

    result = Schedd().submit(submit, itemdata=iter(itemdata))
    cluster_id = (
        result.cluster()
        if callable(getattr(result, "cluster", None))
        else getattr(result, "cluster", None)
    )

    print(f"Submitted cluster_id={cluster_id}")
    print(f"Logs: {submit_dir}")


if __name__ == "__main__":
    main()