#!/usr/bin/env python3
"""Reproduce the MnistMLP (K=8 batch) verifying key from the four pinned
artifacts in this directory and compare it against the expected digests.

Usage: python3 verify.py
"""
import hashlib
import json
import sys
import tempfile
import os

import ezkl
from eth_utils import keccak

EXPECTED_VK_SHA256 = "1ed847e127419bc1d7db2a22779f75284975bf1908b33a43486ca9070e4ef627"
EXPECTED_VK_KECCAK256 = "dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f"

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    onnx_path = os.path.join(HERE, "model_k8.onnx")
    onnx_data_path = os.path.join(HERE, "model_k8.onnx.data")
    settings_path = os.path.join(HERE, "settings.json")
    input_path = os.path.join(HERE, "input.json")
    srs_path = os.path.join(HERE, "srs.bin")

    print(f"ezkl version: {ezkl.__version__}")

    # Pinned-input sanity check before running anything.
    pinned = {
        onnx_path: "5e02c0f09825aaa62d79ba93e86d7baa933150650a02c3d9307bb9afddd43c0a",
        onnx_data_path: "b96f93301048ea7af8eeaca094fee834111a4c1a3a639f17fb5f61b0b13a2612",
        settings_path: "a1d03ec48a1751397f55d6ad5888509146ba09f91764ccae5b09afd448402f4c",
        input_path: "be04b0e63b1ab3ed5b4d030a9d41f5ee1d79033d60a5740dd49d478560c98f7c",
        srs_path: "d1a1655b4366a766d1578beb257849a92bf91cb1358c1a2c37ab180c5d3a204d",
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

        print("setup (this allocates ~7-8 GB RSS and writes a ~5.2 GB pk.key; "
              "takes roughly 15-100s depending on host) ...")
        ezkl.setup(compiled_path, vk_path, pk_path, srs_path)

        vk_bytes = open(vk_path, "rb").read()
        vk_sha256 = hashlib.sha256(vk_bytes).hexdigest()
        vk_keccak256 = keccak(vk_bytes).hex()

    print()
    print(f"computed vk.key SHA256    = {vk_sha256}")
    print(f"expected vk.key SHA256    = {EXPECTED_VK_SHA256}")
    sha_match = vk_sha256 == EXPECTED_VK_SHA256
    print(f"  MATCH: {sha_match}")
    print()
    print(f"computed vk.key keccak256 = {vk_keccak256}")
    print(f"expected vk.key keccak256 = {EXPECTED_VK_KECCAK256}  (on-chain vkHash, Base Sepolia)")
    keccak_match = vk_keccak256 == EXPECTED_VK_KECCAK256
    print(f"  MATCH: {keccak_match}")
    print()

    ok = sha_match and keccak_match

    attestation = {
        "reproducer": os.environ.get("REPRODUCER_ID", "<fill in: name/org/identity>"),
        "date": None,
        "ezkl_version": ezkl.__version__,
        "computed_vk_digest": vk_sha256,
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
