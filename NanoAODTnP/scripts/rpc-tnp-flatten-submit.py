#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

import htcondor2 as htcondor
from htcondor2 import Schedd, Submit


CERT_MAP = {
    "2022": "Cert_Collisions2022_355100_362760_Golden.json",
    "2023": "Cert_Collisions2023_366442_370790_Golden.json",
    "2024": "Cert_Collisions2024_378981_386951_Golden.json",
    "2025": "Cert_Collisions2025_391658_398903_Golden.json",
}


def get_year(path: Path) -> str:
    m = re.search(r"Run(20\d{2})", path.as_posix())
    if not m:
        raise ValueError(f"Cannot determine year from path: {path}")
    return m.group(1)


def output_exists(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-i", "--input-base", type=Path, required=True)
    parser.add_argument("-o", "--output-base", type=Path, required=True,
                        help="Final EOS output base path")
    parser.add_argument("-s", "--script", type=Path, required=True,
                        help="Path to rpc-tnp-flatten.py")
    parser.add_argument("-c", "--cert-dir", type=Path, required=True,
                        help="Directory containing cert JSON files")
    parser.add_argument("-n", "--name", type=str, default="rpcTnP")
    parser.add_argument("--pattern", type=str, default="output_*.root")
    parser.add_argument("--endpoint", type=str, default="root://eosuser.cern.ch")
    parser.add_argument("--submit-dir", type=Path, default=Path("./logs/condor"))
    parser.add_argument("--memory", type=str, default="2GB")
    parser.add_argument("--disk", type=str, default="2GB")
    parser.add_argument("--cpus", type=int, default=1)
    parser.add_argument("--batch-name", type=str, default="rpcTnPFlatten")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--force", action="store_true",
                        help="Submit even if output already exists")
    args = parser.parse_args()

    input_base = args.input_base.resolve()
    output_base = args.output_base
    script = args.script.resolve()
    cert_dir = args.cert_dir.resolve()
    submit_dir = args.submit_dir.resolve()
    log_root = submit_dir

    if not input_base.exists():
        raise FileNotFoundError(f"Input base not found: {input_base}")
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")
    if not cert_dir.exists():
        raise FileNotFoundError(f"Cert dir not found: {cert_dir}")

    submit_dir.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in input_base.rglob(args.pattern) if p.is_file())
    if not files:
        raise RuntimeError(f"No files matched: {input_base}/**/{args.pattern}")

    itemdata = []
    skipped = 0

    python_exec = Path(sys.executable).resolve()

    for f in files:
        rel = f.relative_to(input_base)
        out = output_base / rel

        if not args.force and output_exists(out):
            skipped += 1
            continue

        year = get_year(f)
        cert = cert_dir / CERT_MAP[year]
        if not cert.exists():
            raise FileNotFoundError(f"Cert file not found: {cert}")

        log_dir = log_root / rel.parent
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

    credd = htcondor.Credd()
    credd.add_user_cred(htcondor.CredTypes.Kerberos, None)

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
        "MY.SendCredential": "True",
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
    print(f"Logs: {log_root}")


if __name__ == "__main__":
    main()