#!/usr/bin/env python3
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.Analysis import flatten_nanoaod


def run_cmd(cmd):
    subprocess.run(cmd, check=True)


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


def stageout_eos(src: Path, dst: Path, endpoint: str):
    run_cmd(["xrdfs", endpoint, "mkdir", "-p", dst.parent.as_posix()])
    run_cmd(["xrdcp", "-f", src.as_posix(), f"{endpoint}//{dst.as_posix()}"])


def stageout_hdfs(src: Path, dst: Path):
    ns_dst = to_hdfs_namespace(dst)
    ns_parent = str(Path(ns_dst).parent)
    run_cmd(["hdfs", "dfs", "-mkdir", "-p", ns_parent])
    run_cmd(["hdfs", "dfs", "-put", "-f", src.as_posix(), ns_dst])


def stageout_local(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_cmd(["cp", "-f", src.as_posix(), dst.as_posix()])


def stageout(src: Path, dst: Path, endpoint: str = "root://eosuser.cern.ch"):
    backend = detect_storage(dst)
    if backend == "eos":
        stageout_eos(src, dst, endpoint)
    elif backend == "hdfs":
        stageout_hdfs(src, dst)
    else:
        stageout_local(src, dst)


def touch_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-i", "--input-path", required=True, type=Path,
                        help="input NanoAOD file")
    parser.add_argument("-c", "--cert-path", required=True, type=Path,
                        help="Golden JSON file")
    parser.add_argument("-o", "--output-path", required=True, type=Path,
                        help="final output path (/eos, /hdfs, or local)")
    parser.add_argument("-n", "--name", default="rpcTnP", type=str,
                        help="branch prefix")
    parser.add_argument("--endpoint", default="root://eosuser.cern.ch", type=str,
                        help="XRootD endpoint for EOS stageout")
    args = parser.parse_args()

    scratch_base = Path(os.environ.get("_CONDOR_SCRATCH_DIR", os.getcwd())).resolve()

    with tempfile.TemporaryDirectory(prefix="rpc_tnp_flatten_", dir=scratch_base) as tmpdir_name:
        tmpdir = Path(tmpdir_name)
        local_output = tmpdir / "output.root"
        local_done = tmpdir / "output.root.done"

        flatten_nanoaod(
            input_path=args.input_path,
            cert_path=args.cert_path,
            output_path=local_output,
            name=args.name,
        )

        if local_output.exists():
            stageout(local_output, args.output_path, endpoint=args.endpoint)

        touch_file(local_done)
        stageout(local_done, Path(str(args.output_path) + ".done"), endpoint=args.endpoint)


if __name__ == "__main__":
    main()