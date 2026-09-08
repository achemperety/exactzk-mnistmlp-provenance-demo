#!/usr/bin/env python3
"""Reproduce the SECOND link in the provenance chain: vk.key -> Halo2Verifier.sol
-> deployed bytecode. Complements verify.py, which reproduces the FIRST link
(published artifacts -> vk.key) and does not touch this one.

This script:
  1. Obtains a vk.key (either regenerated from the pinned bundle, same as
     verify.py, or supplied via --vk-path if you already have one you trust).
  2. Runs ezkl.create_evm_verifier() to produce Halo2Verifier.sol from
     {vk.key, settings.json, srs.bin} -- no weights, no ONNX file involved.
  3. Compiles and deploys that Solidity source to a throwaway LOCAL chain
     (spawns its own `anvil` instance) and reads back the runtime bytecode.
  4. Strips the trailing Solidity CBOR metadata from both (a) the just-built
     local bytecode and (b) the live bytecode read from the real deployment
     on Base Sepolia over a public RPC, hashes each, and checks all three
     values -- local, live, and the published expected digest -- agree.

Unlike verify.py, this is NOT weights-required: steps 2-4 only need
{vk.key, settings.json, srs.bin}. Step 1's *default* path (no --vk-path)
regenerates vk.key from the full published bundle for self-contained
convenience, which does require the weights-derived ONNX files and ~7-8 GB
RAM, same as verify.py. If you already have a vk.key you trust (e.g. from a
prior verify.py run, kept instead of letting its tempdir clean it up), pass
--vk-path to skip straight to the weight-free part.

Dependencies beyond verify.py's: a local `anvil` binary on PATH (part of
Foundry, https://getfoundry.sh -- NOT installed by this repo's Dockerfile,
which only installs the Python packages verify.py needs). ezkl's
create_evm_verifier/deploy_evm also need outbound network access the FIRST
time they run, to download and cache the solc version they pick internally
(via svm-rs, cached afterward under ~/Library/Application Support/svm on
macOS or ~/.svm on Linux) -- this project does not pin or control which solc
version that is.

Usage:
    python3 verify_deployment.py                      # regenerate vk.key too
    python3 verify_deployment.py --vk-path ./vk.key    # reuse an existing one
"""
import argparse
import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import ezkl
from eth_utils import keccak

try:
    import asyncio
except ImportError:  # pragma: no cover
    print("asyncio is required (Python 3.7+).", file=sys.stderr)
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))

# --- Tier-1 values (vk.key), reproduced here only for the default
#     self-contained path -- see verify.py, the canonical check for this link.
EXPECTED_VK_SHA256 = "1ed847e127419bc1d7db2a22779f75284975bf1908b33a43486ca9070e4ef627"
EXPECTED_VK_KECCAK256 = "dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f"

# --- Tier-2 values (this script's actual subject) ---
# MEASURED against this exact vk.key + settings.json + srs.bin, this session
# (2026-09-08) and previously in the parent project's docs/53 §2.
EXPECTED_SOL_SHA256 = "a843bcddb0aff97560139d92fd74c9bdfb0719e0a2fb8e17c92187e4e6da8636"
# MEASURED live against Base Sepolia (chainId 84532), this session, and
# independently reproduced by this script's own local-anvil deploy.
EXPECTED_BYTECODE_KECCAK256 = "d0cab4041caaf77ea95fe45a29d14950be503ce26eb982af11026634112d8c67"

# A standalone, byte-identical mirror of the K=8 Halo2Verifier this repo's
# vk.key is attested against -- deployed from an unrelated, faucet-funded key
# solely so this bytecode link is publicly checkable without deanonymizing
# the production deployment (see README, "Two identifiers"). Pure verifier:
# no state writes, no funds, no owner, no admin surface.
DEPLOYED_VERIFIER_ADDRESS = "0x886b1baceB0552B2A4159663879b2841F3d81739"
DEFAULT_BASE_SEPOLIA_RPC = "https://sepolia.base.org"

# Anvil's well-known, publicly documented default test account #0.
# Not a secret -- never fund this key on any real network.
ANVIL_DEFAULT_PRIVATE_KEY = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_cbor_metadata(runtime_code: bytes) -> bytes:
    """Strip the trailing Solidity CBOR metadata blob. The last 2 bytes of
    standard solc output encode the metadata length (big-endian uint16)."""
    if len(runtime_code) < 2:
        return runtime_code
    meta_len = int.from_bytes(runtime_code[-2:], "big")
    if meta_len == 0 or meta_len + 2 > len(runtime_code):
        return runtime_code
    return runtime_code[: -(2 + meta_len)]


def eth_get_code(rpc_url: str, address: str) -> bytes:
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": "eth_getCode", "params": [address, "latest"], "id": 1}
    ).encode()
    req = urllib.request.Request(
        rpc_url,
        data=payload,
        # Some public RPC gateways reject requests carrying urllib's default
        # User-Agent (blanket bot-filtering); curl's UA string is not blocked.
        headers={"Content-Type": "application/json", "User-Agent": "curl/8.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
            body = json.loads(resp.read())
    except urllib.error.URLError as e:
        if not (isinstance(e.reason, ssl.SSLCertVerificationError) or "CERTIFICATE" in str(e.reason)):
            raise
        try:
            import certifi

            with urllib.request.urlopen(
                req, timeout=30, context=ssl.create_default_context(cafile=certifi.where())
            ) as resp:
                body = json.loads(resp.read())
        except Exception:
            print(
                f"SSL certificate verification failed talking to {rpc_url}, and the "
                "certifi fallback didn't fix it either.\n"
                "On macOS with a python.org install, this usually means the bundled "
                "root certificates were never installed -- run "
                "'/Applications/Python 3.x/Install Certificates.command', or "
                "'pip install certifi' and set SSL_CERT_FILE to certifi.where().",
                file=sys.stderr,
            )
            raise
    if "error" in body:
        raise RuntimeError(f"eth_getCode against {rpc_url} failed: {body['error']}")
    return bytes.fromhex(body["result"][2:])


def wait_for_rpc(rpc_url: str, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    payload = json.dumps({"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}).encode()
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                rpc_url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "curl/8.0"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                json.loads(resp.read())
            return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"local anvil chain at {rpc_url} never became ready")


class LocalAnvil:
    """Spawns a throwaway local anvil chain for the duration of this script,
    the same "never a project script, never testnet" pattern docs/53 §2 used
    to take these measurements."""

    def __init__(self, port: int):
        self.port = port
        self.rpc_url = f"http://127.0.0.1:{port}"
        self.proc = None
        self.log_path = None

    def __enter__(self):
        fd, self.log_path = tempfile.mkstemp(prefix="anvil-log-")
        os.close(fd)
        try:
            self.proc = subprocess.Popen(
                ["anvil", "--port", str(self.port)],
                stdout=open(self.log_path, "w"),
                stderr=subprocess.STDOUT,
            )
        except FileNotFoundError:
            print(
                "`anvil` was not found on PATH. This script needs a local Foundry "
                "install (https://getfoundry.sh) to spin up a throwaway local chain "
                "-- it is a separate dependency from verify.py's, and is NOT "
                "installed by this repo's Dockerfile.",
                file=sys.stderr,
            )
            raise
        wait_for_rpc(self.rpc_url)
        return self

    def __exit__(self, *exc):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.log_path and os.path.exists(self.log_path):
            os.unlink(self.log_path)


async def build_and_deploy(vk_path: str, settings_path: str, srs_path: str, tmp: str, anvil_rpc: str):
    sol_path = os.path.join(tmp, "Halo2Verifier.sol")
    abi_path = os.path.join(tmp, "Halo2Verifier.abi")
    addr_path = os.path.join(tmp, "verifier_addr.txt")

    t0 = time.time()
    await ezkl.create_evm_verifier(vk_path, settings_path, sol_path, abi_path, srs_path)
    t1 = time.time()
    sol_sha256 = sha256_file(sol_path)
    print(f"create_evm_verifier: {t1 - t0:.3f}s")
    print(f"  Halo2Verifier.sol SHA256 = {sol_sha256}")
    print(f"  expected                 = {EXPECTED_SOL_SHA256}")
    sol_match = sol_sha256 == EXPECTED_SOL_SHA256
    print(f"  MATCH: {sol_match}")

    t2 = time.time()
    await ezkl.deploy_evm(addr_path, anvil_rpc, sol_path, private_key=ANVIL_DEFAULT_PRIVATE_KEY)
    t3 = time.time()
    local_addr = open(addr_path).read().strip()
    print(f"deploy_evm (local anvil): {t3 - t2:.3f}s -> {local_addr}")

    return local_addr, sol_match, sol_sha256


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vk-path", default=None, help="reuse an existing vk.key instead of regenerating one")
    parser.add_argument("--rpc-url", default=DEFAULT_BASE_SEPOLIA_RPC, help="public Base Sepolia RPC endpoint")
    parser.add_argument(
        "--verifier-address", default=DEPLOYED_VERIFIER_ADDRESS, help="deployed verifier contract to check against"
    )
    parser.add_argument("--anvil-port", type=int, default=8559, help="port for the throwaway local anvil chain")
    args = parser.parse_args()

    onnx_path = os.path.join(HERE, "model_k8.onnx")
    onnx_data_path = os.path.join(HERE, "model_k8.onnx.data")
    settings_path = os.path.join(HERE, "settings.json")
    input_path = os.path.join(HERE, "input.json")
    srs_path = os.path.join(HERE, "srs.bin")

    print(f"ezkl version: {ezkl.__version__}")

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

    ok = True

    with tempfile.TemporaryDirectory() as tmp:
        if args.vk_path:
            vk_path = args.vk_path
            print(f"Using supplied vk.key: {vk_path}")
        else:
            compiled_path = os.path.join(tmp, "model.compiled")
            vk_path = os.path.join(tmp, "vk.key")
            pk_path = os.path.join(tmp, "pk.key")
            print("No --vk-path given: regenerating vk.key from the published bundle first "
                  "(this is tier 1, same as verify.py -- needs the weights-derived ONNX "
                  "files and ~7-8 GB RSS; tier 2 below does not).")
            print("compile_circuit ...")
            ezkl.compile_circuit(onnx_path, compiled_path, settings_path)
            print("setup ...")
            ezkl.setup(compiled_path, vk_path, pk_path, srs_path)

        vk_sha256 = sha256_file(vk_path)
        vk_keccak256 = keccak(open(vk_path, "rb").read()).hex()
        print(f"vk.key SHA256    = {vk_sha256}  (expected {EXPECTED_VK_SHA256})")
        print(f"vk.key keccak256 = {vk_keccak256}  (expected {EXPECTED_VK_KECCAK256})")
        vk_ok = vk_sha256 == EXPECTED_VK_SHA256 and vk_keccak256 == EXPECTED_VK_KECCAK256
        print(f"  MATCH: {vk_ok}")
        if not vk_ok:
            print("vk.key does not match the expected digests -- refusing to continue "
                  "(tier 2 would just be reproducing the binding for the wrong VK).")
            return 1
        print()

        try:
            with LocalAnvil(args.anvil_port) as anvil:
                local_addr, sol_ok, sol_sha256 = asyncio.run(
                    build_and_deploy(vk_path, settings_path, srs_path, tmp, anvil.rpc_url)
                )
                ok = ok and sol_ok

                local_code = eth_get_code(anvil.rpc_url, local_addr)
                local_stripped = strip_cbor_metadata(local_code)
                local_hash = keccak(local_stripped).hex()
        except FileNotFoundError:
            return 1

    print()
    print(f"local deployment runtime bytecode length = {len(local_code)} bytes")
    print(f"local deployment stripped keccak256       = {local_hash}")
    print(f"expected                                  = {EXPECTED_BYTECODE_KECCAK256}")
    local_match = local_hash == EXPECTED_BYTECODE_KECCAK256
    print(f"  MATCH: {local_match}")
    ok = ok and local_match
    print()

    print(f"Fetching live eth_getCode({args.verifier_address}) from {args.rpc_url} ...")
    live_code = eth_get_code(args.rpc_url, args.verifier_address)
    live_stripped = strip_cbor_metadata(live_code)
    live_hash = keccak(live_stripped).hex()
    print(f"live deployed runtime bytecode length = {len(live_code)} bytes")
    print(f"live deployed stripped keccak256       = {live_hash}")
    print(f"expected                               = {EXPECTED_BYTECODE_KECCAK256}")
    live_match = live_hash == EXPECTED_BYTECODE_KECCAK256
    print(f"  MATCH vs. expected: {live_match}")
    print(f"  MATCH vs. this script's own local deploy: {live_hash == local_hash}")
    ok = ok and live_match and (live_hash == local_hash)

    print()
    print("Summary of every hash checked:")
    print(f"  vk.key            sha256    = {vk_sha256}")
    print(f"  vk.key            keccak256 = {vk_keccak256}")
    print(f"  Halo2Verifier.sol sha256    = {sol_sha256}")
    print(f"  local deploy      stripped keccak256 = {local_hash}")
    print(f"  live Base Sepolia stripped keccak256 = {live_hash}")

    print()
    print("RESULT:", "PASS - deployed bytecode matches the attested vk.key binding" if ok else "FAIL - mismatch somewhere in the chain")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
