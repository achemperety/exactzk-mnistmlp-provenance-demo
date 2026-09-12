#!/usr/bin/env python3
"""Reproduce the THIRD link in the provenance chain, independently of this
repo's own claims: read the public mirror deployment on Base Sepolia, and for
EACH of the two circuits registered against this project's model (the batch
circuit `verify.py`/`verify_deployment.py` already cover, and the solo
circuit, which this repo has never shipped artifacts for), reconstruct and
verify every third-party attestation that could apply to it from scratch --
no attestation content is taken from this repo's README or from
`attestations/*.json` as ground truth; everything below is re-derived from
on-chain state and each attester's own published file, fetched live.

This is the same check a client library would run before trusting a
passport ("does this on-chain record actually mean what it claims"), applied
here as a standalone script so a reader isn't asked to trust that this repo
ran it correctly:

  1. Read `escrow.models(modelId)` to get the two verifier addresses
     (`vkSolo`, `vkBatch`) actually registered on-chain.
  2. For each one, read `anchor.getCircuitByVerifier(modelId, verifier)` to
     get that circuit's `CircuitRecord` (`vkHashFile`, `vkHashBytecode`,
     `bundleDigest`).
  3. Confirm `bytecodeBindingVerified`: fetch the verifier's live runtime
     bytecode via `eth_getCode`, strip the trailing Solidity CBOR metadata,
     hash it, and check it equals the record's `vkHashBytecode`. This step
     ALONE proves nothing about third-party reproduction -- see "The
     bytecodeBindingVerified trap" in the README. It is included here
     because a client checks it too, and because the trap only lands if a
     reader sees the number in context.
  4. For every (trusted attester, tag) pair this project recognizes,
     reconstruct the exact `requestHash` the on-chain registry would use and
     check whether it resolves. A resolved hash is a POINTER, not evidence
     (see README) -- it says nothing until the next two steps run.
  5. For every resolved hash, fetch the `responseURI` the registry stored,
     download that file, and verify ITS OWN signature by its own
     construction (three different schemes exist across the four batch
     attestations -- see README, "Verifying a signed attestation's proof").
     A record only counts if the recovered signer matches the credited
     attester.
  6. Check the verified document's own claimed digest against the circuit's
     on-chain `vkHashFile` (and, for the bytecode tag, `vkHashBytecode`
     too) -- a valid signature over the WRONG content should not count.
  7. Print every intermediate value and a final per-circuit summary:
     `tier1Count`, `avgScore`, `bytecodeBindingVerified`, `allowed`.

Run it for both circuits with no arguments:

    python3 verify_onchain_quorum.py

Unlike verify_deployment.py, this script's dependencies are all pure-Python
and pip-installable -- no local `anvil`/Foundry, no compiled toolchain:

    pip install web3==7.16.0 eth-abi eth-account eth-utils ecdsa requests

Also unlike verify_deployment.py, every network call this script makes is
against something genuinely public and requires no credentials of any kind:
a public Base Sepolia RPC (`https://sepolia.base.org`, overridable with
`--rpc-url`), raw GitHub content (wherever each registry record's
`responseURI` actually points -- not hardcoded, read live from the chain),
and one third-party HTTPS endpoint an nsgoods-signed record's authority
check needs (`https://x402.nsgoods.org/proof/index.json` -- run by nsgoods,
not by this project; if that endpoint is ever down or altered, the affected
attestation's authority check fails closed, same as a bad signature). There
is no anvil/solc step here at all -- this script never compiles or deploys
anything; it only reads.

What this script does NOT do: it does not re-derive `vkHashFile` or
`vkHashBytecode` from the published artifacts -- that's `verify.py` and
`verify_deployment.py`'s job, and this script trusts whatever the on-chain
`CircuitRecord` says those digests are, the same way a real client would
(the whole point of tier 1/tier 2 being separately reproducible is that this
script doesn't have to re-run them to check tier 3's bookkeeping). Run
`verify.py` first if you want the full chain from artifacts to attestation
quorum in one sitting.
"""
import argparse
import base64
import hashlib
import json
import sys

import requests
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
from ecdsa.util import sigdecode_string
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi import encode as abi_encode
from web3 import Web3

DEFAULT_RPC = "https://sepolia.base.org"

# --- Public mirror stack addresses (Base Sepolia, chainId 84532) ---
# Deployed from a key with no relationship to this project's operational
# deployer -- see README, "The public mirror stack" -- solely so this check
# is runnable by anyone against public chain state. These are the ONLY
# addresses this script needs; nothing about the operational deployment
# (which exists, and is not published) appears here.
ESCROW = "0x27e4DfA9e435a463A947e4eD8f74d8aB86F2F4CF"
ANCHOR_V2 = "0xD0B577776A239E3eE3b39373f2380E366c3a987f"
REGISTRY_V2 = "0x5421E241668AA5e2Bc6Da2c5642Fa9bFc8A5d996"
MODEL_ID = "0x06ef1c26ba4f218306433064fb65a8d0fbaffab707fb224505f0e256e23f2e8d"

# --- Trusted attester set this deployment recognizes ---
# For the two did:key (JsonWebSignature2020) reproducers, the address below
# is NOT a wallet they ever signed with -- it is derived, by this project,
# from the secp256k1 public key embedded in their did:key identifier (see
# didKeySecp256k1ToAddress below), purely so the on-chain requestHash
# preimage has an address-shaped slot to put an attester identity in. The
# actual authenticity check for those two is the JWS verification in step 5,
# against the did:key material itself, not against this derived address.
# For nsgoods, the address below IS the address they sign EIP-191 messages
# with directly.
ATTESTER_MAHA = Web3.to_checksum_address("0x74780848E8b8c89Cf00a3294df6051ed2Ab019A9")
ATTESTER_BITSANITY = Web3.to_checksum_address("0x5b953A66Eb0826c13Ca2aF80E0C36557cC6a1a96")
ATTESTER_NSGOODS = Web3.to_checksum_address("0x57fF0F084Cba33e6761503f90eEF0Da9F159350c")
TRUSTED_ATTESTERS = [
    ("maha", ATTESTER_MAHA),
    ("bitsanity", ATTESTER_BITSANITY),
    ("nsgoods", ATTESTER_NSGOODS),
]

TAG_REPRO = "pp-repro-v2"
TAG_BYTECODE = "pp-bytecode-v1"
PASSPORT_DOMAIN = Web3.keccak(text="zkml-passport-v1")

NSGOODS_MANIFEST_URL = "https://x402.nsgoods.org/proof/index.json"
NSGOODS_REQUIRED_SCOPE = "reproduction-attestations"

# Same interim policy constants the client library this deployment was built
# against uses: at least one verified tier-1 reproduction, averaging at
# least 51/100 on-chain score, or the passport is refused.
MIN_TIER1_ATTESTATIONS = 1
MIN_SCORE = 51

ESCROW_ABI = [{
    "type": "function", "name": "models", "stateMutability": "view",
    "inputs": [{"name": "modelId", "type": "bytes32"}],
    "outputs": [
        {"name": "vkSolo", "type": "address"},
        {"name": "vkBatch", "type": "address"},
        {"name": "numOutputs", "type": "uint16"},
        {"name": "hDummy", "type": "uint256"},
        {"name": "registered", "type": "bool"},
    ],
}]

CIRCUIT_RECORD_COMPONENTS = [
    {"name": "circuitLabel", "type": "string"},
    {"name": "verifierAddr", "type": "address"},
    {"name": "vkHashFile", "type": "bytes32"},
    {"name": "vkHashBytecode", "type": "bytes32"},
    {"name": "bundleDigest", "type": "bytes32"},
    {"name": "sameWeightsSibling", "type": "bytes32"},
]
ANCHOR_ABI = [{
    "type": "function", "name": "getCircuitByVerifier", "stateMutability": "view",
    "inputs": [{"name": "modelId", "type": "bytes32"}, {"name": "verifierAddr", "type": "address"}],
    "outputs": [
        {"name": "rec", "type": "tuple", "components": CIRCUIT_RECORD_COMPONENTS},
        {"name": "found", "type": "bool"},
    ],
}]

REGISTRY_ABI = [{
    "type": "function", "name": "getValidationStatus", "stateMutability": "view",
    "inputs": [{"name": "requestHash", "type": "bytes32"}],
    "outputs": [
        {"name": "validatorAddress", "type": "address"},
        {"name": "agentId", "type": "uint256"},
        {"name": "response", "type": "uint8"},
        {"name": "responseHash", "type": "bytes32"},
        {"name": "tag", "type": "string"},
        {"name": "lastUpdate", "type": "uint256"},
    ],
}, {
    # Not part of the ratified ERC-8004 interface (see README) -- a
    # one-line getter this project's own mock registry added over data it
    # already writes on validationResponse(), so a client doesn't have to
    # chunk-scan event logs back to genesis on a long-lived public chain.
    "type": "function", "name": "getResponseURI", "stateMutability": "view",
    "inputs": [{"name": "requestHash", "type": "bytes32"}],
    "outputs": [{"name": "", "type": "string"}],
}]

# --- Canonicalization (RFC 8785/JCS-equivalent for these ASCII-only,
# float-free documents -- see README, "No verification script..." for why
# this reduction is valid here and not in general) ---


def canonicalize(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


# --- did:key (secp256k1) -> Ethereum address, ported from this project's
# TypeScript client (attestationVerify.ts) ---

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_decode(s: str) -> bytes:
    num = 0
    for c in s:
        idx = BASE58_ALPHABET.find(c)
        if idx < 0:
            raise ValueError(f"invalid base58 character: {c}")
        num = num * 58 + idx
    h = hex(num)[2:]
    if len(h) % 2:
        h = "0" + h
    body = bytes.fromhex(h) if h != "0" else b""
    n_pad = 0
    for c in s:
        if c == BASE58_ALPHABET[0]:
            n_pad += 1
        else:
            break
    return b"\x00" * n_pad + body


def did_key_secp256k1_to_pubkey_and_address(did: str):
    mb = did.replace("did:key:", "")
    if not mb.startswith("z"):
        raise ValueError(f"unsupported did:key multibase prefix: {did}")
    raw = base58_decode(mb[1:])
    if len(raw) < 2 or raw[0] != 0xE7 or raw[1] != 0x01:
        raise ValueError(f"did:key is not a secp256k1-pub multicodec (0xe701): {did}")
    compressed = raw[2:]
    vk = VerifyingKey.from_string(compressed, curve=SECP256k1)
    uncompressed_no_prefix = vk.to_string()  # 64 bytes, x||y, no 0x04 prefix
    address = Web3.to_checksum_address("0x" + Web3.keccak(uncompressed_no_prefix).hex()[-40:])
    return vk, address


# --- Signature verification, one function per proof shape (see README,
# "Verifying a signed attestation's proof" for the full derivation of each) ---


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_jws_es256k(doc: dict):
    """JsonWebSignature2020 (001, 002): ES256K JWS, detached (b64:false)
    RFC7797 payload. Returns the address derived from the did:key on success."""
    proof = doc.get("proof") or {}
    jws = proof.get("jws")
    verification_method = proof.get("verificationMethod")
    if not jws or not verification_method:
        return None, "missing proof.jws or proof.verificationMethod"
    parts = jws.split(".")
    if len(parts) != 3 or parts[1] != "":
        return None, "jws is not a detached (b64:false) compact serialization"
    header_b64, _, sig_b64 = parts

    doc_wo_proof = {k: v for k, v in doc.items() if k != "proof"}
    payload_bytes = canonicalize(doc_wo_proof)
    signing_input = (header_b64 + ".").encode() + payload_bytes
    digest = hashlib.sha256(signing_input).digest()

    try:
        sig = b64url_decode(sig_b64)
    except Exception as e:
        return None, f"could not base64url-decode jws signature: {e}"
    if len(sig) != 64:
        return None, f"unexpected ES256K signature length: {len(sig)} (expected 64)"

    did = verification_method.split("#")[0]
    try:
        vk, address = did_key_secp256k1_to_pubkey_and_address(did)
    except Exception as e:
        return None, f"could not resolve did:key: {e}"

    try:
        ok = vk.verify_digest(sig, digest, sigdecode=sigdecode_string)
    except BadSignatureError:
        ok = False
    if not ok:
        return None, "ES256K signature does not verify against the did:key public key"
    return address, None


def verify_eip191_embedded(doc: dict):
    """EthereumEip191Signature, embedded proof (003): personal_sign over JCS
    with the whole `proof` key removed."""
    proof = doc.get("proof") or {}
    signature = proof.get("signature")
    signer_address = proof.get("signerAddress")
    if not signature or not signer_address:
        return None, "missing proof.signature or proof.signerAddress"
    doc_wo_proof = {k: v for k, v in doc.items() if k != "proof"}
    bytes_ = canonicalize(doc_wo_proof)
    try:
        recovered = Account.recover_message(encode_defunct(primitive=bytes_), signature=signature)
    except Exception as e:
        return None, f"signature recovery failed: {e}"
    if recovered.lower() != signer_address.lower():
        return None, f"recovered address {recovered} does not match proof.signerAddress {signer_address}"
    return recovered, None


def verify_eip191_envelope(doc: dict):
    """EIP-191 payload envelope (004): no `proof` key -- personal_sign over
    JCS of the `payload` sub-object alone."""
    payload = doc.get("payload")
    signature = doc.get("signature")
    signed_by = doc.get("signed_by")
    if not payload or not signature or not signed_by:
        return None, "missing payload, signature, or signed_by"
    bytes_ = canonicalize(payload)
    try:
        recovered = Account.recover_message(encode_defunct(primitive=bytes_), signature=signature)
    except Exception as e:
        return None, f"signature recovery failed: {e}"
    if recovered.lower() != signed_by.lower():
        return None, f"recovered address {recovered} does not match signed_by {signed_by}"
    return recovered, None


def verify_attestation_document(doc: dict):
    proof = doc.get("proof")
    if proof and proof.get("type") == "JsonWebSignature2020":
        return verify_jws_es256k(doc)
    if proof and proof.get("type") == "EthereumEip191Signature":
        return verify_eip191_embedded(doc)
    if not proof and doc.get("payload") and doc.get("signature") and doc.get("signed_by"):
        return verify_eip191_envelope(doc)
    return None, "unrecognized attestation document shape"


def check_manifest_scope(manifest_url: str, signer_address: str, required_scope: str):
    try:
        r = requests.get(manifest_url, timeout=15)
        r.raise_for_status()
        manifest = r.json()
    except Exception as e:
        return False, f"manifest fetch failed: {e}"
    signers = manifest.get("signers") or manifest.get("signer_registry")
    if not signers:
        return False, "manifest has no 'signers' map"
    entry = None
    for addr, scopes in signers.items():
        if addr.lower() == signer_address.lower():
            entry = scopes
            break
    if entry is None:
        return False, f"signer {signer_address} not present in manifest"
    if required_scope not in entry:
        return False, f"signer {signer_address} manifest scopes {entry} do not include {required_scope}"
    return True, None


# --- Bytecode canonicalization (same rule verify_deployment.py uses) ---


def strip_cbor_metadata(runtime_code: bytes) -> bytes:
    if len(runtime_code) < 2:
        return runtime_code
    meta_len = int.from_bytes(runtime_code[-2:], "big")
    if meta_len == 0 or meta_len + 2 > len(runtime_code):
        return runtime_code
    return runtime_code[: -(2 + meta_len)]


def req_hash(chain_id: int, slot_a: bytes, slot_b: bytes, tag: str, attester: str) -> bytes:
    tag_hash = Web3.keccak(text=tag)
    packed = abi_encode(
        ["bytes32", "uint256", "bytes32", "bytes32", "bytes32", "address"],
        [PASSPORT_DOMAIN, chain_id, slot_a, slot_b, tag_hash, Web3.to_checksum_address(attester)],
    )
    return Web3.keccak(packed)


def reconstruct_and_verify(registry, chain_id, slot_a, slot_b, tag, candidates, content_check):
    """One (tag, slotA, slotB) pair, tried against every trusted attester.
    Mirrors the client library's reconstructAndVerify: reconstruct ->
    resolve on-chain -> fetch responseURI -> fetch file -> verify its own
    signature -> check recovered address matches the candidate -> check
    claimed content -> only then counts as verified."""
    results = []
    for label, candidate in candidates:
        rh = req_hash(chain_id, slot_a, slot_b, tag, candidate)
        status = registry.functions.getValidationStatus(rh).call()
        response, last_update = status[2], status[5]
        row = {"attester": label, "candidate": candidate, "requestHash": "0x" + rh.hex(), "verified": False}
        if last_update == 0:
            row["failureMode"] = "not_resolved_onchain"
            results.append(row)
            continue
        row["resolvedOnChain"] = True
        row["onChainScore"] = response

        uri = registry.functions.getResponseURI(rh).call()
        if not uri:
            row["failureMode"] = "uri_unreachable"
            results.append(row)
            continue
        row["evidenceURI"] = uri

        try:
            r = requests.get(uri, timeout=20)
            r.raise_for_status()
            doc = r.json()
        except Exception as e:
            row["failureMode"] = "uri_unreachable"
            row["detail"] = str(e)
            results.append(row)
            continue

        recovered, err = verify_attestation_document(doc)
        if err:
            row["failureMode"] = "signature_mismatch"
            row["detail"] = err
            results.append(row)
            continue
        row["recoveredAddress"] = recovered
        if recovered.lower() != candidate.lower():
            row["failureMode"] = "signature_mismatch"
            row["detail"] = f"document signature recovers to {recovered}, not the credited attester {candidate}"
            results.append(row)
            continue

        ok, detail = content_check(doc)
        if not ok:
            row["failureMode"] = "content_mismatch"
            row["detail"] = detail
            results.append(row)
            continue

        # nsgoods (EIP-191) records carry a signer-authority manifest; the
        # two did:key records (001/002) have no such concept and are
        # authorized by trustedAttesters membership alone (see README).
        if candidate.lower() == ATTESTER_NSGOODS.lower():
            in_scope, scope_err = check_manifest_scope(NSGOODS_MANIFEST_URL, candidate, NSGOODS_REQUIRED_SCOPE)
            if not in_scope:
                row["failureMode"] = "signer_outside_scope"
                row["detail"] = scope_err
                results.append(row)
                continue

        row["verified"] = True
        results.append(row)
    return results


def check_circuit(w3, escrow, anchor, registry, chain_id, circuit_label, verifier_addr):
    print(f"\n{'=' * 70}\nCircuit: {circuit_label}  (verifier {verifier_addr})\n{'=' * 70}")

    rec, found = anchor.functions.getCircuitByVerifier(bytes.fromhex(MODEL_ID[2:]), verifier_addr).call()
    if not found:
        print("  no CircuitRecord found for this verifier -- aborting this circuit")
        return None
    vk_hash_file, vk_hash_bytecode, bundle_digest = rec[2], rec[3], rec[4]
    print(f"  vkHashFile      = 0x{vk_hash_file.hex()}")
    print(f"  vkHashBytecode  = 0x{vk_hash_bytecode.hex()}")
    print(f"  bundleDigest    = 0x{bundle_digest.hex()}")

    code = w3.eth.get_code(verifier_addr)
    stripped = strip_cbor_metadata(code)
    live_hash = Web3.keccak(stripped)
    bytecode_binding_verified = live_hash == vk_hash_bytecode
    print(f"  live bytecode   = {len(code)} bytes, stripped keccak256 = 0x{live_hash.hex()}")
    print(f"  bytecodeBindingVerified = {bytecode_binding_verified}")
    print(
        "    NOTE: this only confirms live bytecode matches what the registrar wrote to\n"
        "    this CircuitRecord -- the registrar (mirror key) can satisfy this trivially\n"
        "    for ANY circuit, attested or not. It carries no third-party weight by itself."
    )

    print(f"\n  -- pp-repro-v2 (tier 1: vk.key reproduction) --")
    tier1_results = reconstruct_and_verify(
        registry, chain_id, vk_hash_file, bundle_digest, TAG_REPRO, TRUSTED_ATTESTERS,
        content_check=lambda doc: content_check_repro(doc, vk_hash_file),
    )
    for row in tier1_results:
        status = "verified" if row["verified"] else f"NOT verified ({row.get('failureMode')})"
        print(f"    {row['attester']:10s} requestHash={row['requestHash']} {status}")

    print(f"\n  -- pp-bytecode-v1 (tier 2: bytecode binding attestation) --")
    tier2_results = reconstruct_and_verify(
        registry, chain_id, vk_hash_file, vk_hash_bytecode, TAG_BYTECODE, TRUSTED_ATTESTERS,
        content_check=lambda doc: content_check_bytecode(doc, vk_hash_file, vk_hash_bytecode),
    )
    for row in tier2_results:
        status = "verified" if row["verified"] else f"NOT verified ({row.get('failureMode')})"
        print(f"    {row['attester']:10s} requestHash={row['requestHash']} {status}")

    verified_tier1 = [r for r in tier1_results if r["verified"]]
    tier1_count = len(verified_tier1)
    avg_score = (sum(r["onChainScore"] for r in verified_tier1) // tier1_count) if tier1_count else 0
    allowed = tier1_count >= MIN_TIER1_ATTESTATIONS and avg_score >= MIN_SCORE

    print(f"\n  tier1Count = {tier1_count}")
    print(f"  avgScore   = {avg_score}")
    print(f"  allowed    = {allowed}  (MIN_TIER1_ATTESTATIONS={MIN_TIER1_ATTESTATIONS}, MIN_SCORE={MIN_SCORE})")

    return {
        "circuit": circuit_label,
        "tier1Count": tier1_count,
        "avgScore": avg_score,
        "bytecodeBindingVerified": bytecode_binding_verified,
        "allowed": allowed,
    }


def content_check_repro(doc, expected_vk_hash_file):
    claimed = None
    if isinstance(doc.get("reproducedDigests"), dict):
        claimed = doc["reproducedDigests"].get("keccak256")
    elif isinstance(doc.get("computed_vk_digest"), dict):
        claimed = doc["computed_vk_digest"].get("keccak256")
    if not claimed:
        return False, "document has neither reproducedDigests.keccak256 nor computed_vk_digest.keccak256"
    ok = claimed.lower().replace("0x", "") == expected_vk_hash_file.hex().lower()
    return ok, None if ok else f"document claims vk digest {claimed}, expected 0x{expected_vk_hash_file.hex()}"


def content_check_bytecode(doc, expected_vk_hash_file, expected_vk_hash_bytecode):
    payload = doc.get("payload", doc)
    claimed_file = payload.get("vkHash_file")
    claimed_bytecode = payload.get("vkHash_bytecode")
    file_ok = bool(claimed_file) and claimed_file.lower().replace("0x", "") == expected_vk_hash_file.hex().lower()
    bc_ok = bool(claimed_bytecode) and claimed_bytecode.lower().replace("0x", "") == expected_vk_hash_bytecode.hex().lower()
    if not (file_ok and bc_ok):
        return False, f"document claims vkHash_file={claimed_file} vkHash_bytecode={claimed_bytecode}"
    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC, help="public Base Sepolia RPC endpoint")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(args.rpc_url, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        print(f"Cannot connect to {args.rpc_url}", file=sys.stderr)
        return 1
    chain_id = w3.eth.chain_id
    print(f"Connected to chainId={chain_id} via {args.rpc_url}")

    escrow = w3.eth.contract(address=Web3.to_checksum_address(ESCROW), abi=ESCROW_ABI)
    anchor = w3.eth.contract(address=Web3.to_checksum_address(ANCHOR_V2), abi=ANCHOR_ABI)
    registry = w3.eth.contract(address=Web3.to_checksum_address(REGISTRY_V2), abi=REGISTRY_ABI)

    model_id_bytes = bytes.fromhex(MODEL_ID[2:])
    vk_solo, vk_batch, num_outputs, h_dummy, registered = escrow.functions.models(model_id_bytes).call()
    print(f"escrow.models(modelId): vkSolo={vk_solo} vkBatch={vk_batch} registered={registered}")
    if not registered:
        print("Model is not registered on this stack -- aborting.", file=sys.stderr)
        return 1

    results = []
    results.append(check_circuit(w3, escrow, anchor, registry, chain_id, "solo", vk_solo))
    results.append(check_circuit(w3, escrow, anchor, registry, chain_id, "batchK8", vk_batch))

    print(f"\n{'=' * 70}\nSummary\n{'=' * 70}")
    print(f"{'circuit':10s} {'tier1Count':11s} {'avgScore':9s} {'bytecodeBindingVerified':24s} {'allowed':8s}")
    for r in results:
        if r is None:
            continue
        print(f"{r['circuit']:10s} {r['tier1Count']:<11d} {r['avgScore']:<9d} {str(r['bytecodeBindingVerified']):<24s} {str(r['allowed']):<8s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
