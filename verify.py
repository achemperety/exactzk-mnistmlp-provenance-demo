#!/usr/bin/env python3
"""Reproduce a MnistMLP verifying key from its pinned artifacts and compare
it against the expected digests. Covers both circuits published in this
repo: the K=8 batch circuit (root directory, the original bundle) and the
solo (batch_size=1) circuit (`solo/` directory).

Usage:
    python3 verify.py                  # batch (default, backward-compatible)
    python3 verify.py --circuit batch
    python3 verify.py --circuit solo
    python3 verify.py --no-environment # omit the "environment" record from
                                        # the suggested attestation JSON
"""
import argparse
import hashlib
import json
import sys
import tempfile
import time
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


def collect_environment(ezkl_version: str, t_start: float, setup_wall_s: float) -> dict:
    """Best-effort, cross-platform-comparable record of the environment this
    reproduction ran in: peak RSS (bytes, normalized), OS/arch, container
    detection, and timings. Must never raise and must never affect verify.py's
    own exit code -- any failure here degrades to {"schema": ..., "error": ...}
    and the reproduction proceeds exactly as if this had not been called.

    Memory: resource.getrusage(RUSAGE_SELF).ru_maxrss is peak RSS of THIS
    process since it started. verify.py calls ezkl in-process and spawns no
    subprocesses of its own, so this one figure covers the entire
    reproduction (unlike verify_deployment.py, which also shells out to
    anvil). The unit convention differs by platform -- bytes on Darwin,
    kibibytes on Linux -- so both the raw value and its unit are reported
    alongside the normalized byte count, never the normalized value alone.
    ru_maxrss is resident set size and excludes page cache, so it is not
    directly comparable to a cgroup v2 memory.peak figure (which includes
    page cache, as used by this repo's existing third-party Docker
    attestations, e.g. attestations/006a-nsgoods-2026-09-15.json) -- the gap
    between the two bases widens for circuits that write a large proving key.

    Container detection: only checked on non-Darwin platforms, since none of
    the marker paths exist natively on macOS -- a negative result there would
    be "not checked", not "confirmed not a container", so Darwin reports
    null rather than false.
    """
    schema = "exactzk-env-record-v1"
    try:
        import datetime
        import platform
        import resource

        system = platform.system()

        raw_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if system == "Darwin":
            peak_rss_bytes = raw_rss
            peak_rss_raw_unit = "bytes"
        elif system == "Linux":
            peak_rss_bytes = raw_rss * 1024
            peak_rss_raw_unit = "kibibytes"
        else:
            peak_rss_bytes = None
            peak_rss_raw_unit = "unknown"
        peak_rss_gib = round(peak_rss_bytes / 1024 ** 3, 3) if peak_rss_bytes is not None else None

        if system == "Darwin":
            container_detected, container_basis = None, "not determinable on this platform"
        else:
            container_detected, container_basis = False, (
                "no container indicators found (checked /.dockerenv, "
                "/run/.containerenv, /proc/1/cgroup)"
            )
            if os.path.exists("/.dockerenv"):
                container_detected, container_basis = True, "/.dockerenv present"
            elif os.path.exists("/run/.containerenv"):
                container_detected, container_basis = True, "/run/.containerenv present (podman)"
            else:
                try:
                    with open("/proc/1/cgroup") as f:
                        cgroup_text = f.read()
                    if any(tok in cgroup_text for tok in ("docker", "kubepods", "containerd", "lxc")):
                        container_detected, container_basis = True, "container indicator found in /proc/1/cgroup"
                except OSError:
                    pass

        if peak_rss_raw_unit == "bytes":
            unit_note = "ru_maxrss was used directly as bytes"
        elif peak_rss_raw_unit == "kibibytes":
            unit_note = "ru_maxrss was multiplied by 1024 to normalize to bytes"
        else:
            unit_note = "ru_maxrss's unit convention on this platform is unknown, so it was left unconverted (peak_rss_bytes is null)"

        measurement_basis = (
            f"peak_rss_* is resource.getrusage(RUSAGE_SELF).ru_maxrss of the verify.py "
            f"process itself, sampled once after setup() completes; verify.py spawns no "
            f"subprocesses of its own, so this figure covers the entire reproduction. "
            f"On this platform ({system}), ru_maxrss is reported in {peak_rss_raw_unit}; {unit_note}. "
            f"ru_maxrss measures resident set size and does not include page cache, so it is "
            f"not directly comparable to a cgroup v2 memory.peak figure measured around "
            f"`docker run` (which does include page cache, as reported by this repo's "
            f"existing third-party Docker attestations under attestations/, e.g. 006a); the "
            f"gap between the two bases widens for circuits that write a large proving key, "
            f"since page cache from that write can inflate memory.peak without showing up in RSS."
        )

        return {
            "schema": schema,
            "measured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "os": f"{system} {platform.release()}",
            "arch": platform.machine(),
            "python": platform.python_version(),
            "ezkl_version": ezkl_version,
            "container_detected": container_detected,
            "container_basis": container_basis,
            "peak_rss_bytes": peak_rss_bytes,
            "peak_rss_raw": raw_rss,
            "peak_rss_raw_unit": peak_rss_raw_unit,
            "peak_rss_source": "getrusage.ru_maxrss.RUSAGE_SELF",
            "peak_rss_gib": peak_rss_gib,
            "wall_s": round(time.monotonic() - t_start, 2),
            "setup_wall_s": setup_wall_s,
            "measurement_basis": measurement_basis,
        }
    except Exception as e:
        # Exception CLASS NAME only -- no str(e). A real failure here is
        # typically an OSError whose message embeds an absolute path (e.g.
        # "Permission denied: '/Users/<username>/...'"), and this record can
        # end up signed and published by a third-party reproducer (B3: no
        # paths, usernames, or other host-identifying data). The class name
        # alone (PermissionError, FileNotFoundError, ...) is enough to tell a
        # maintainer where to start asking, without risking exactly the kind
        # of data this function exists to keep out.
        return {"schema": schema, "error_class": type(e).__name__}


def main() -> int:
    t_start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--circuit", choices=sorted(CIRCUITS), default="batch",
                         help="which circuit's bundle to reproduce (default: batch)")
    parser.add_argument("--no-environment", action="store_true",
                         help="omit the 'environment' record (peak RSS, OS/arch, "
                              "container detection, timings) from the suggested "
                              "attestation JSON; included by default")
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

        t_setup_start = time.monotonic()
        print("compile_circuit ...")
        ezkl.compile_circuit(onnx_path, compiled_path, settings_path)

        print("setup (batch: allocates ~7-8 GB RSS and writes a ~5.2 GB pk.key, "
              "roughly 15-100s; solo: allocates ~1.5 GB RSS, roughly 2s "
              "-- depends on host either way) ...")
        ezkl.setup(compiled_path, vk_path, pk_path, srs_path)
        setup_wall_s = round(time.monotonic() - t_setup_start, 2)

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
    if not args.no_environment:
        attestation["environment"] = collect_environment(ezkl.__version__, t_start, setup_wall_s)
    import datetime
    attestation["date"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print("Suggested attestation JSON (see README \"Attestation format\"):")
    print(json.dumps(attestation, indent=2))

    print()
    print("RESULT:", "PASS - reproduced the deployed VK" if ok else "FAIL - digest mismatch")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
