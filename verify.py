#!/usr/bin/env python3
"""Reproduce a MnistMLP verifying key from its pinned artifacts and compare
it against the expected digests. Covers both circuits published in this
repo: the K=8 batch circuit (root directory, the original bundle) and the
solo (batch_size=1) circuit (`solo/` directory).

Usage:
    python3 verify.py                  # batch (default, backward-compatible)
    python3 verify.py --circuit batch
    python3 verify.py --circuit solo
"""
import argparse
import hashlib
import json
import sys
import tempfile
import os

import ezkl
from eth_utils import keccak

HERE = os.path.dirname(os.path.abspath(__file__))

CIRCUITS = {
    "batch": {
        "dir": HERE,
        "onnx": "model_k8.onnx",
        "onnx_data": "model_k8.onnx.data",
        "settings": "settings.json",
        "input": "input.json",
        "srs": "srs.bin",
        "pinned_sha256": {
            "model_k8.onnx": "5e02c0f09825aaa62d79ba93e86d7baa933150650a02c3d9307bb9afddd43c0a",
            "model_k8.onnx.data": "b96f93301048ea7af8eeaca094fee834111a4c1a3a639f17fb5f61b0b13a2612",
            "settings.json": "a1d03ec48a1751397f55d6ad5888509146ba09f91764ccae5b09afd448402f4c",
            "input.json": "be04b0e63b1ab3ed5b4d030a9d41f5ee1d79033d60a5740dd49d478560c98f7c",
            "srs.bin": "d1a1655b4366a766d1578beb257849a92bf91cb1358c1a2c37ab180c5d3a204d",
        },
        "expected_vk_sha256": "1ed847e127419bc1d7db2a22779f75284975bf1908b33a43486ca9070e4ef627",
        "expected_vk_keccak256": "dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f",
    },
    "solo": {
        "dir": os.path.join(HERE, "solo"),
        "onnx": "model_solo.onnx",
        "onnx_data": "model_solo.onnx.data",
        "settings": "settings.json",
        "input": "input.json",
        "srs": "srs.bin",
        "pinned_sha256": {
            "model_solo.onnx": "c3caeb161859f91da3233830c3f43e5ed9f0c47cdc2913d1a48ffe42a3a51e90",
            "model_solo.onnx.data": "b96f93301048ea7af8eeaca094fee834111a4c1a3a639f17fb5f61b0b13a2612",
            "settings.json": "dcae92a6d5fd8435b299b2df1f727a370fbdf9db9461e6d997c7bdd4b94ac6c4",
            "input.json": "892c2f91fcd78b846e83f510b70db8c7e5480e692c989a3ed8c6e81632cd84c3",
            "srs.bin": "e4690b6479fceefdc2486372ceeaf274d7a336f908463caa619b7bc42ebfe9be",
        },
        "expected_vk_sha256": "32439290a76c2ef71fb6f20ef203b001b54d9835b411554bae827df5364e9523",
        "expected_vk_keccak256": "13cff0426abe00c941934bdd6bb7757f2e703fb9f6862bf08a783eeca08b4ff2",
    },
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--circuit", choices=sorted(CIRCUITS), default="batch",
                         help="which circuit's bundle to reproduce (default: batch)")
    args = parser.parse_args()
    cfg = CIRCUITS[args.circuit]

    onnx_path = os.path.join(cfg["dir"], cfg["onnx"])
    onnx_data_path = os.path.join(cfg["dir"], cfg["onnx_data"])
    settings_path = os.path.join(cfg["dir"], cfg["settings"])
    input_path = os.path.join(cfg["dir"], cfg["input"])
    srs_path = os.path.join(cfg["dir"], cfg["srs"])

    print(f"circuit: {args.circuit}")
    print(f"ezkl version: {ezkl.__version__}")

    # Pinned-input sanity check before running anything.
    pinned = {
        onnx_path: cfg["pinned_sha256"][cfg["onnx"]],
        onnx_data_path: cfg["pinned_sha256"][cfg["onnx_data"]],
        settings_path: cfg["pinned_sha256"][cfg["settings"]],
        input_path: cfg["pinned_sha256"][cfg["input"]],
        srs_path: cfg["pinned_sha256"][cfg["srs"]],
    }
    for path, expected in pinned.items():
        got = sha256_file(path)
        status = "OK" if got == expected else "MISMATCH"
        print(f"  {os.path.basename(path):20s} sha256={got}  [{status}]")
        if got != expected:
            print(f"    expected sha256={expected}")
            print("Input files do not match the pinned digests. Aborting.")
            return 1

    with tempfile.TemporaryDirectory() as tmp:
        compiled_path = os.path.join(tmp, "model.compiled")
        vk_path = os.path.join(tmp, "vk.key")
        pk_path = os.path.join(tmp, "pk.key")

        print("compile_circuit ...")
        ezkl.compile_circuit(onnx_path, compiled_path, settings_path)

        print("setup (batch: allocates ~7-8 GB RSS and writes a ~5.2 GB pk.key, "
              "roughly 15-100s; solo: allocates ~1.5 GB RSS, roughly 2s "
              "-- depends on host either way) ...")
        ezkl.setup(compiled_path, vk_path, pk_path, srs_path)

        vk_bytes = open(vk_path, "rb").read()
        vk_sha256 = hashlib.sha256(vk_bytes).hexdigest()
        vk_keccak256 = keccak(vk_bytes).hex()

    print()
    print(f"computed vk.key SHA256    = {vk_sha256}")
    print(f"expected vk.key SHA256    = {cfg['expected_vk_sha256']}")
    sha_match = vk_sha256 == cfg["expected_vk_sha256"]
    print(f"  MATCH: {sha_match}")
    print()
    print(f"computed vk.key keccak256 = {vk_keccak256}")
    print(f"expected vk.key keccak256 = {cfg['expected_vk_keccak256']}  (on-chain vkHash, Base Sepolia)")
    keccak_match = vk_keccak256 == cfg["expected_vk_keccak256"]
    print(f"  MATCH: {keccak_match}")
    print()

    ok = sha_match and keccak_match

    attestation = {
        "reproducer": os.environ.get("REPRODUCER_ID", "<fill in: name/org/identity>"),
        "date": None,
        "circuit": args.circuit,
        "ezkl_version": ezkl.__version__,
        "verification_scope": "full",
        "computed_vk_digest": {
            "sha256": vk_sha256,
            "keccak256": vk_keccak256,
        },
        "matches_expected_digest": ok,
        "notes": "",
    }
    import datetime
    attestation["date"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print("Suggested attestation JSON (see README \"Attestation format\"):")
    print(json.dumps(attestation, indent=2))

    print()
    print("RESULT:", "PASS - reproduced the deployed VK" if ok else "FAIL - digest mismatch")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
