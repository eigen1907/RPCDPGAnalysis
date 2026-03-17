#!/usr/bin/env python3
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.Analysis import flatten_nanoaod


def stageout(src: Path, dst: Path, endpoint: str = "root://eosuser.cern.ch"):
    subprocess.run(["xrdfs", endpoint, "mkdir", "-p", dst.parent.as_posix()], check=True)
    subprocess.run(["xrdcp", "-f", src.as_posix(), f"{endpoint}//{dst.as_posix()}"], check=True)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-i", "--input-path", required=True, type=Path,
                        help="input NanoAOD file")
    parser.add_argument("-c", "--cert-path", required=True, type=Path,
                        help="Golden JSON file")
    parser.add_argument("-o", "--output-path", required=True, type=Path,
                        help="final EOS output path")
    parser.add_argument("-n", "--name", default="rpcTnP", type=str,
                        help="branch prefix")
    parser.add_argument("--endpoint", default="root://eosuser.cern.ch", type=str,
                        help="XRootD endpoint for stageout")
    args = parser.parse_args()

    scratch_base = Path(os.environ.get("_CONDOR_SCRATCH_DIR", os.getcwd())).resolve()

    with tempfile.TemporaryDirectory(prefix="rpc_tnp_flatten_", dir=scratch_base) as tmpdir_name:
        tmpdir = Path(tmpdir_name)
        local_output = tmpdir / "output.root"

        flatten_nanoaod(
            input_path=args.input_path,
            cert_path=args.cert_path,
            output_path=local_output,
            name=args.name,
        )

        if not local_output.exists():
            raise RuntimeError(f"Local output was not created: {local_output}")

        stageout(local_output, args.output_path, endpoint=args.endpoint)


if __name__ == "__main__":
    main()