#!/usr/bin/env python3
"""Regression check for `doc_field()`/`doc_field_any()` in
verify_onchain_quorum.py — the shape-agnostic accessor `content_check_repro`
and `content_check_bytecode` read every attestation field through — plus
those two content checks themselves against the real attestation files.

Why this exists: the first version of `doc_field()` (written to fix a filing
bug where the pp-repro-v2 check only ever looked at the document root) read
`payload` first and fell back to the document root whenever the payload read
came back empty — not only when `doc["payload"]` itself was absent. In the
EIP-191 envelope shape (004, 005), only `payload` is covered by the
signature; the document root sits outside the signed material entirely. That
meant a validly-signed envelope document could omit a required field from
`payload` and carry an attacker-controlled copy of that same field at the
unsigned root, and the old accessor would silently return the unsigned root
value as if it were verified content. A reviewer asked whether a regression
case existed for exactly that condition. It didn't, so this script is that
case, plus the rest of the matrix the same review asked for: both document
shapes, a missing field, a malformed field, both locations present and
agreeing, both present and disagreeing, and a document shape the reader
doesn't recognize at all — for every tag this project checks, plus all five
real attestation files, so the shapes actually in production are covered by
something that runs, not just assumed to still work because they worked once.

This protects against the fallback being reintroduced silently. Someone
simplifying `doc_field()` back down to "payload, else root" in six months
would break nothing visible in a normal run against real records (none of
the five currently conflict) — this script is what would catch it. Two
cases cover the forged-root condition, deliberately kept separate because
they test different things: CASE_ROOT_ONLY_FORGERY_REJECTED_SHAPE_ONLY
constructs a document that merely carries the right keys (`payload`,
`signature`, `signed_by`) with the field absent from payload and present at
root, checking field-selection behaviour in isolation.
CASE_ROOT_ONLY_FORGERY_REJECTED_GENUINE_SIGNATURE goes further: it generates
a throwaway keypair, signs a payload that genuinely lacks the field with the
same EIP-191 construction the real attestations use, confirms that signature
genuinely verifies, and only then checks that the content check still
refuses the forged root value — proving the property that actually matters,
that a valid signature over incomplete content can't become a passing
content check.

No test framework and no test-directory convention — this repo has neither,
and none is introduced here. This script imports verify_onchain_quorum.py
directly (by file path, so it runs from any working directory) and uses only
the Python standard library, `eth_account` (already a hard dependency of
verify_onchain_quorum.py, used here only to generate and sign with a
throwaway keypair — never a key with any real-world meaning), and this
repo's own `attestations/*.json` files; no dependency beyond what
verify_onchain_quorum.py itself already needs (nothing extra to install for
this script specifically). Every synthetic fixture is a Python literal
inlined below, not a loose file, so the script cannot silently pass because
a fixture went missing.

Usage:
    python3 verify_doc_field_regressions.py

Exit code 0 if every case passes; 1 if any fails (each failure is printed,
naming the case).
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ATTESTATIONS_DIR = os.path.join(HERE, "attestations")


def _load_verify_onchain_quorum():
    spec = importlib.util.spec_from_file_location(
        "verify_onchain_quorum", os.path.join(HERE, "verify_onchain_quorum.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


voq = _load_verify_onchain_quorum()

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f"\n         -> {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


def load_real(name):
    with open(os.path.join(ATTESTATIONS_DIR, name)) as f:
        return json.load(f)


REPRO_PATHS = [["reproducedDigests", "keccak256"], ["computed_vk_digest", "keccak256"]]
BYTECODE_FILE_PATH = ["vkHash_file"]
BYTECODE_BC_PATH = ["vkHash_bytecode"]


def main() -> int:
    # ------------------------------------------------------------------
    # pp-bytecode-v1-shaped field (single field name: vkHash_file)
    # ------------------------------------------------------------------
    print("=== vkHash_file: both shapes valid ===")
    status, value, _ = voq.doc_field({"vkHash_file": "AAA"}, BYTECODE_FILE_PATH)
    check("flat shape, field present -> ok", status == "ok" and value == "AAA")

    status, value, _ = voq.doc_field(
        {"payload": {"vkHash_file": "BBB"}, "signature": "0xdead", "signed_by": "0xbeef"}, BYTECODE_FILE_PATH
    )
    check("envelope shape, field in payload -> ok", status == "ok" and value == "BBB")

    print("\n=== vkHash_file: field missing ===")
    status, _, _ = voq.doc_field({}, BYTECODE_FILE_PATH)
    check("flat shape, field absent -> missing", status == "missing")

    status, _, _ = voq.doc_field({"payload": {}}, BYTECODE_FILE_PATH)
    check("envelope shape, field absent from payload and root -> missing", status == "missing")

    print("\n=== vkHash_file: field malformed ===")
    status, _, _ = voq.doc_field({"vkHash_file": ""}, BYTECODE_FILE_PATH)
    check("flat shape, empty string -> malformed", status == "malformed")

    status, _, _ = voq.doc_field({"vkHash_file": 123}, BYTECODE_FILE_PATH)
    check("flat shape, wrong type (int) -> malformed", status == "malformed")

    status, _, _ = voq.doc_field({"payload": {"vkHash_file": {"nested": True}}}, BYTECODE_FILE_PATH)
    check("envelope shape, payload value is a dict, not a string -> malformed", status == "malformed")

    print("\n=== vkHash_file: both locations present and AGREEING -> still a conflict ===")
    status, _, _ = voq.doc_field({"payload": {"vkHash_file": "SAME"}, "vkHash_file": "SAME"}, BYTECODE_FILE_PATH)
    check("envelope shape, payload and root equal -> conflict (root is unsigned regardless of agreement)", status == "conflict")

    print("\n=== vkHash_file: both locations present and DISAGREEING ===")
    status, _, _ = voq.doc_field(
        {"payload": {"vkHash_file": "SIGNED_VALUE"}, "vkHash_file": "ATTACKER_VALUE"}, BYTECODE_FILE_PATH
    )
    check("envelope shape, payload != root -> conflict", status == "conflict")

    print("\n=== vkHash_file: a shape the reader does not recognize ===")
    status, _, _ = voq.doc_field(None, BYTECODE_FILE_PATH)
    check("document is None -> unrecognized_shape", status == "unrecognized_shape")

    status, _, _ = voq.doc_field("not-a-dict", BYTECODE_FILE_PATH)
    check("document is a string, not a dict -> unrecognized_shape", status == "unrecognized_shape")

    status, _, _ = voq.doc_field({"payload": "not-a-dict"}, BYTECODE_FILE_PATH)
    check("payload key present but not a dict -> unrecognized_shape", status == "unrecognized_shape")

    status, _, _ = voq.doc_field({"payload": None}, BYTECODE_FILE_PATH)
    check("payload key present but None -> unrecognized_shape", status == "unrecognized_shape")

    # ------------------------------------------------------------------
    # KEPT CASE, requested explicitly by a reviewer: a signature-SHAPED
    # envelope document (carries signature/signed_by keys, so it has the
    # right fields for a real record) with the required field absent from
    # its payload and present, instead, at the unsigned root. This
    # establishes field-selection behaviour on its own -- it does not check
    # that the signature is cryptographically real, only that the reader
    # doesn't fall back to the root when it sees those keys. It must be
    # refused as unverifiable, not silently resolved from the root.
    #
    # A second reviewer correctly pointed out that this alone doesn't prove
    # the full path: it doesn't show a genuinely valid signature over
    # genuinely incomplete content still failing the content check. See
    # CASE_ROOT_ONLY_FORGERY_REJECTED_GENUINE_SIGNATURE below for that --
    # both cases are kept, because they test different things: this one
    # tests field selection given the right shape; that one tests the
    # signature-verification-to-content-check path end to end.
    # ------------------------------------------------------------------
    print("\n=== CASE_ROOT_ONLY_FORGERY_REJECTED_SHAPE_ONLY: signature-shaped envelope, field absent from payload, present (unsigned) at root ===")
    forged_root_doc = {
        "payload": {},  # the field this check needs is NOT here
        "signature": "0xforgedsignatureplaceholder",
        "signed_by": "0xattester",
        "vkHash_file": "ROOT_ONLY_UNSIGNED_VALUE",  # outside the signed payload entirely
    }
    status, value, detail = voq.doc_field(forged_root_doc, BYTECODE_FILE_PATH)
    check(
        "CASE_ROOT_ONLY_FORGERY_REJECTED_SHAPE_ONLY: root-only value in a signature-shaped envelope doc is refused, not accepted",
        status == "missing" and value is None,
        f"got status={status!r} value={value!r} detail={detail!r} (a FAIL here means the root fallback has been reintroduced)",
    )

    # Same forged-root shape, applied through doc_field_any (the pp-repro-v2
    # path with two candidate field names) — the guard must hold there too,
    # not just for a single-field-name lookup.
    forged_root_doc_repro = {
        "payload": {},
        "signature": "0xforgedsignatureplaceholder",
        "signed_by": "0xattester",
        "computed_vk_digest": {"keccak256": "ROOT_ONLY_UNSIGNED_DIGEST"},
    }
    status, value, detail = voq.doc_field_any(forged_root_doc_repro, REPRO_PATHS)
    check(
        "CASE_ROOT_ONLY_FORGERY_REJECTED_SHAPE_ONLY (pp-repro-v2, via doc_field_any): root-only digest in a signature-shaped envelope doc is refused",
        status == "missing" and value is None,
        f"got status={status!r} value={value!r} detail={detail!r}",
    )

    # ------------------------------------------------------------------
    # CASE_ROOT_ONLY_FORGERY_REJECTED_GENUINE_SIGNATURE: the full path, not
    # just the shape. Generates a throwaway keypair, builds a payload that
    # genuinely lacks the target field, canonicalizes and signs that payload
    # with the SAME EIP-191 construction the real attestations use
    # (`canonicalize()` + `encode_defunct` + personal_sign, exactly what
    # `verify_eip191_envelope()` checks against), and sets `signed_by` to the
    # address that signature actually recovers to. A forged value for the
    # target field is then placed at the document root -- outside the signed
    # payload, so the signature says nothing about it.
    #
    # This is not a synthetic shape anymore: `voq.verify_attestation_document`
    # (the exact dispatcher the live script calls) genuinely verifies this
    # signature, over genuinely incomplete content, recovering the throwaway
    # address. The property under test is that a real, valid signature over
    # incomplete content must not become a passing content check merely
    # because the missing piece can be found somewhere else in the document.
    # ------------------------------------------------------------------
    print("\n=== CASE_ROOT_ONLY_FORGERY_REJECTED_GENUINE_SIGNATURE: cryptographically valid EIP-191 signature over a payload genuinely missing the field, forged value at the unsigned root ===")
    throwaway = voq.Account.create()
    genuine_payload = {
        "reproducer": "verify_doc_field_regressions.py fixture",
        "note": "vkHash_file is intentionally absent from this payload - it is signed as-is",
    }
    payload_bytes = voq.canonicalize(genuine_payload)
    signed_message = voq.Account.sign_message(voq.encode_defunct(primitive=payload_bytes), private_key=throwaway.key)
    signature_hex = signed_message.signature.hex()
    if not signature_hex.startswith("0x"):
        signature_hex = "0x" + signature_hex

    genuinely_signed_forged_root_doc = {
        "payload": genuine_payload,
        "signature": signature_hex,
        "signed_by": throwaway.address,
        "vkHash_file": "ROOT_ONLY_UNSIGNED_VALUE_UNDER_GENUINE_SIGNATURE",  # attacker-controlled, outside the signed payload
    }

    recovered, sig_err = voq.verify_attestation_document(genuinely_signed_forged_root_doc)
    check(
        "GENUINE_SIGNATURE precondition: the signature over the incomplete payload genuinely verifies, recovering the throwaway address",
        sig_err is None and recovered is not None and recovered.lower() == throwaway.address.lower(),
        f"got recovered={recovered!r} err={sig_err!r} (if this fails, the case below proves nothing - the signature itself isn't valid)",
    )

    status, value, detail = voq.doc_field(genuinely_signed_forged_root_doc, BYTECODE_FILE_PATH)
    check(
        "CASE_ROOT_ONLY_FORGERY_REJECTED_GENUINE_SIGNATURE: content check still refuses despite a genuinely valid signature, because the field is absent from the signed payload",
        status == "missing" and value is None,
        f"got status={status!r} value={value!r} detail={detail!r} (a FAIL here means a valid signature over incomplete content became a passing content check)",
    )

    # ------------------------------------------------------------------
    # pp-repro-v2's two field-name variants, via doc_field_any
    # ------------------------------------------------------------------
    print("\n=== pp-repro-v2 (doc_field_any, two field names): both shapes valid, both variants ===")
    status, value, _ = voq.doc_field_any({"reproducedDigests": {"keccak256": "AAA"}}, REPRO_PATHS)
    check("flat / reproducedDigests -> ok", status == "ok" and value == "AAA")

    status, value, _ = voq.doc_field_any({"computed_vk_digest": {"keccak256": "BBB"}}, REPRO_PATHS)
    check("flat / computed_vk_digest -> ok", status == "ok" and value == "BBB")

    status, value, _ = voq.doc_field_any(
        {"payload": {"computed_vk_digest": {"keccak256": "CCC"}}, "signature": "0xdead", "signed_by": "0xbeef"},
        REPRO_PATHS,
    )
    check("envelope / payload.computed_vk_digest (the 005 shape) -> ok", status == "ok" and value == "CCC")

    status, value, _ = voq.doc_field_any(
        {"payload": {"reproducedDigests": {"keccak256": "DDD"}}, "signature": "0xdead", "signed_by": "0xbeef"},
        REPRO_PATHS,
    )
    check("envelope / payload.reproducedDigests (hypothetical, same shape family) -> ok", status == "ok" and value == "DDD")

    print("\n=== pp-repro-v2: field missing (neither variant present) ===")
    status, _, _ = voq.doc_field_any({}, REPRO_PATHS)
    check("flat, neither variant present -> missing", status == "missing")

    status, _, _ = voq.doc_field_any({"payload": {}}, REPRO_PATHS)
    check("envelope, neither variant present -> missing", status == "missing")

    print("\n=== pp-repro-v2: field malformed ===")
    status, _, _ = voq.doc_field_any({"computed_vk_digest": {"keccak256": 42}}, REPRO_PATHS)
    check("flat, wrong type -> malformed", status == "malformed")

    print("\n=== pp-repro-v2: both locations present and AGREEING -> still conflict, no silent retry of the other field name ===")
    status, _, _ = voq.doc_field_any(
        {"payload": {"computed_vk_digest": {"keccak256": "SAME"}}, "computed_vk_digest": {"keccak256": "SAME"}},
        REPRO_PATHS,
    )
    check("envelope, payload and root equal under computed_vk_digest -> conflict", status == "conflict")

    print("\n=== pp-repro-v2: both locations present and DISAGREEING ===")
    status, _, _ = voq.doc_field_any(
        {"payload": {"computed_vk_digest": {"keccak256": "REAL"}}, "computed_vk_digest": {"keccak256": "FORGED"}},
        REPRO_PATHS,
    )
    check("envelope, payload != root under computed_vk_digest -> conflict", status == "conflict")

    print("\n=== pp-repro-v2: a shape the reader does not recognize ===")
    status, _, _ = voq.doc_field_any(None, REPRO_PATHS)
    check("document is None -> unrecognized_shape", status == "unrecognized_shape")

    status, _, _ = voq.doc_field_any({"payload": 7}, REPRO_PATHS)
    check("payload present but not a dict -> unrecognized_shape", status == "unrecognized_shape")

    # ------------------------------------------------------------------
    # Real attestation files: doc_field()/doc_field_any() level, so the
    # shapes actually in production are exercised, not just assumed.
    # ------------------------------------------------------------------
    print("\n=== real attestation files: doc_field level ===")
    EXPECTED_VK = "dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f"
    EXPECTED_BC = "d0cab4041caaf77ea95fe45a29d14950be503ce26eb982af11026634112d8c67"
    EXPECTED_005 = "13cff0426abe00c941934bdd6bb7757f2e703fb9f6862bf08a783eeca08b4ff2"

    status, value, _ = voq.doc_field_any(load_real("001-maha-strategies-2026-08-31.json"), REPRO_PATHS)
    check("001 (flat, reproducedDigests)", status == "ok" and value == EXPECTED_VK)

    status, value, _ = voq.doc_field_any(load_real("002-bitsanity-2026-09-04.json"), REPRO_PATHS)
    check("002 (flat, reproducedDigests)", status == "ok" and value == EXPECTED_VK)

    status, value, _ = voq.doc_field_any(load_real("003-nsgoods-2026-09-07.json"), REPRO_PATHS)
    check("003 (flat, computed_vk_digest)", status == "ok" and value == EXPECTED_VK)

    doc004 = load_real("004-nsgoods-2026-09-08.json")
    status, value, _ = voq.doc_field(doc004, BYTECODE_FILE_PATH)
    check("004 (envelope) vkHash_file", status == "ok" and value == EXPECTED_VK)
    status, value, _ = voq.doc_field(doc004, BYTECODE_BC_PATH)
    check("004 (envelope) vkHash_bytecode", status == "ok" and value == EXPECTED_BC)

    # 005: pp-repro-v2 in envelope shape — the record whose filing exposed
    # the original bug this accessor exists to fix.
    doc005 = load_real("005-nsgoods-2026-09-13.json")
    status, value, _ = voq.doc_field_any(doc005, REPRO_PATHS)
    check("005 (envelope, pp-repro-v2 — the record that exposed the original bug)", status == "ok" and value == EXPECTED_005)

    # ------------------------------------------------------------------
    # Real attestation files: content_check_repro / content_check_bytecode
    # level — the actual functions verify_onchain_quorum.py's main() calls,
    # not just the accessor underneath them.
    # ------------------------------------------------------------------
    print("\n=== real attestation files: content_check_repro / content_check_bytecode level ===")
    vk_file_bytes = bytes.fromhex(EXPECTED_VK)
    vk_bc_bytes = bytes.fromhex(EXPECTED_BC)
    vk_005_bytes = bytes.fromhex(EXPECTED_005)

    ok, detail = voq.content_check_repro(load_real("001-maha-strategies-2026-08-31.json"), vk_file_bytes)
    check("content_check_repro(001, batch vkHashFile)", ok, str(detail))

    ok, detail = voq.content_check_repro(load_real("003-nsgoods-2026-09-07.json"), vk_file_bytes)
    check("content_check_repro(003, batch vkHashFile)", ok, str(detail))

    ok, detail = voq.content_check_bytecode(doc004, vk_file_bytes, vk_bc_bytes)
    check("content_check_bytecode(004, batch vkHashFile, batch vkHashBytecode)", ok, str(detail))

    ok, detail = voq.content_check_repro(doc005, vk_005_bytes)
    check("content_check_repro(005, solo vkHashFile) — the case that originally failed", ok, str(detail))

    print("\n" + ("ALL DOC_FIELD REGRESSION CHECKS PASSED" if not FAILURES else f"{len(FAILURES)} CHECK(S) FAILED:"))
    for f in FAILURES:
        print(f"  - {f}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
