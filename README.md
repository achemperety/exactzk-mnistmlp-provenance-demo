# exactzk-mnistmlp-provenance-demo

Standalone reproduction bundle for one circuit from a larger zkML-gated
payment escrow design: an MnistMLP classifier (52,650 params, K=8 batched
inference lanes) compiled with [EZKL](https://github.com/zkonduit/ezkl) into
a Halo2 verifying key that is deployed and attested on Base Sepolia. MNIST is
a public, well-known dataset — this bundle carries no model IP beyond what
that implies. Context on the larger design:
[Atomic ZK-proof-gated settlement for x402 agent payments](https://ethresear.ch/t/atomic-zk-proof-gated-settlement-for-x402-agent-payments-a-measured-reference-design/25660).

This repo answers one narrow question: **given only the four files below,
can an independent party rebuild the exact same verifying key that is live
on-chain?** Yes — verified below, twice (native + Docker).

## Files

| File | Purpose |
|---|---|
| `model_k8.onnx` + `model_k8.onnx.data` | The ONNX model (external-data format) |
| `settings.json` | EZKL circuit settings (already calibrated + scale-pinned — see "Calibration" below) |
| `input.json` | A real sample input actually used to build and witness this circuit |
| `srs.bin` | The structured reference string used for `setup()` — **see "About srs.bin" below, this is a test SRS, not a production trusted setup** |

Pinned input digests (checked automatically by `verify.py` before it runs anything):

```
model_k8.onnx        sha256=5e02c0f09825aaa62d79ba93e86d7baa933150650a02c3d9307bb9afddd43c0a
model_k8.onnx.data   sha256=b96f93301048ea7af8eeaca094fee834111a4c1a3a639f17fb5f61b0b13a2612
settings.json        sha256=a1d03ec48a1751397f55d6ad5888509146ba09f91764ccae5b09afd448402f4c
input.json           sha256=be04b0e63b1ab3ed5b4d030a9d41f5ee1d79033d60a5740dd49d478560c98f7c
srs.bin              sha256=d1a1655b4366a766d1578beb257849a92bf91cb1358c1a2c37ab180c5d3a204d
```

The same five digests, in standard `sha256sum`-compatible format, are also
committed as [`MANIFEST.sha256`](MANIFEST.sha256) — a convenience pointer,
not a separate verification mechanism (`verify.py`'s per-file checks above
remain the actual source of truth). You can check the working tree against
it directly:

```bash
shasum -a 256 -c MANIFEST.sha256
```

`MANIFEST.sha256` itself has this "bundle digest" (`SHA256(MANIFEST.sha256)`):

```
dfe064d623512a83f72c16e121a7c2e44e92d453fce49afe819ee363990f11da
```

## Identity, locator, and resolution — kept separate on purpose

Worth being explicit about three things this bundle conflates implicitly if
you don't read `verify.py` closely:

- **Committed identity.** The SHA256 hashes pinned above (and in
  `verify.py`) *are* the dependency identity for each of the five input
  files. That digest is the authority — not this repo, not GitHub, not any
  particular file host.
- **Locator.** This GitHub repo is *one place* to currently fetch bytes
  matching that identity — a convenience locator, not the identity itself.
  If this repo ever becomes unavailable, any source producing bytes that
  hash-match the committed digests above is equally valid; nothing about
  the identity depends on GitHub specifically.
- **Resolution.** The pinned-digest check already at the top of
  `verify.py` *is* the resolution step: fetch bytes from wherever, hash
  them, compare against the committed digest, and only then use them. That
  mechanism doesn't need to change to support fetching from a different
  locator — it already treats "bytes matching this hash" as sufficient
  regardless of source.

**Fail-closed condition:** if bytes matching a committed identity above
cannot currently be resolved from *any* source, the attestation becomes
currently unestablishable for a new reproducer — full stop, not a partial
result. That is distinct from, and does not retroactively invalidate, an
earlier confirmed reproduction (e.g. a prior partial reproduction someone
already completed and reported). Historical confirmation and current
recomputability are separate facts about different points in time; this
README does not collapse them into one status line, and neither should you
when citing this bundle.

## Target: the deployed VK

| Digest | Value | What it is |
|---|---|---|
| `SHA256(vk.key)` | `1ed847e127419bc1d7db2a22779f75284975bf1908b33a43486ca9070e4ef627` | Raw artifact hash of the Halo2 verifying key file |
| `keccak256(vk.key)` | `dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f` | The `vkHash` actually submitted on-chain (Base Sepolia, chainId 84532) via this project's ERC-8004-style passport attestation |

`verify.py` reproduces `vk.key` from scratch and checks it against **both** values.

## Exact EZKL version

**`ezkl==23.0.5`** (Python package, from PyPI). This is the exact version
that produced the deployed VK above, confirmed via `ezkl.__version__` in the
environment that ran `compile_circuit` + `setup` for this artifact set.
Different EZKL versions can produce different VKs from identical
model/settings/SRS inputs, so this pin is load-bearing, not decorative — use
it, don't just use "latest."

## Reproduce — exact commands

```bash
python3 -m venv venv && source venv/bin/activate
pip install ezkl==23.0.5 eth-utils==6.0.0 pycryptodome==3.20.0
python3 verify.py
```

`verify.py` runs `ezkl.compile_circuit()` then `ezkl.setup()` (no
GPU required; expect ~15–100s and a peak RSS of roughly 7–8 GB depending on
host — this matches the memory profile already documented for this circuit
in the parent project). It writes a ~5.2 GB `pk.key` to a temp directory
(deleted on exit) as a byproduct of `setup()` — that's normal, `pk.key` is
not itself part of what's being verified here.

## Reproduce — Docker (no local toolchain dependency)

```bash
docker build -t mnistmlp-repro .
docker run --rm mnistmlp-repro
```

The `Dockerfile` pins `ezkl==23.0.5`, `eth-utils==6.0.0`, and
`pycryptodome==3.20.0` (the keccak256 backend `eth-utils` needs) explicitly, so
this path doesn't depend on your local Python/pip resolving the same
versions "by luck." It also pins `--platform=linux/amd64`, because
`ezkl==23.0.5` ships a `manylinux2014_x86_64` wheel on PyPI but no
`linux/aarch64` wheel for this version — on an Apple Silicon Docker host
this runs under emulation (works, just slower to build/pull than native).
Allow the container at least ~8 GB of memory (Docker Desktop's default
resource limits are usually sufficient on modern machines; increase if
`setup()` gets OOM-killed).

## Calibration inputs

EZKL's settings-generation step for this circuit
(`ezkl.calibrate_settings(input_json, onnx_path, settings_path,
target="resources")`) was run against **the same input tensor that ships
here as `input.json`** — there is no separate calibration dataset. The
committed `settings.json` already reflects that calibration (plus a
subsequent scale-pinning step), so reproducers don't need to re-run
calibration at all: `verify.py` consumes `settings.json` directly and never
calls `calibrate_settings`. Stating this explicitly so it isn't left
ambiguous: **`input.json` covers the calibration-input requirement — no
additional file or seed is needed.**

## About `srs.bin`

This is a **locally-generated, cryptographically insecure test SRS**
(`ezkl.gen_srs()`), not output from a real trusted-setup ceremony. It is
included here — rather than regenerated — because `ezkl.gen_srs()` is
**non-deterministic** (it samples fresh toxic waste per SRS): regenerating
it locally produces a different SRS, and therefore a different VK, than the
one deployed on-chain. Shipping this exact file is the only way this bundle
round-trips to the deployed VK.

**This is a known, temporary state of the underlying project, not a
security claim about it.** A production/mainnet deployment of the design
this circuit belongs to requires a universal SRS from a real trusted-setup
ceremony (e.g. Perpetual Powers of Tau), not this file. Do not reuse
`srs.bin` for anything where soundness matters.

## Attestation format

If you reproduce this and want to let us know, here's the shape we'd
appreciate back — plain JSON, no signature required for this bounded test:

```json
{
  "reproducer": "<name/org/identity>",
  "date": "<ISO8601>",
  "ezkl_version": "<version used>",
  "verification_scope": "partial" | "full",
  "computed_vk_digest": {
    "sha256": "<hex, or null if scope is partial and VK step wasn't reached>",
    "keccak256": "<hex, or null if scope is partial and VK step wasn't reached>"
  },
  "matches_expected_digest": true | false | null,
  "notes": "<optional>"
}
```

`verification_scope` records what was actually established at attestation
time: `"partial"` means only the pinned artifact hashes were checked (the
resolution step in the [section above](#identity-locator-and-resolution--kept-separate-on-purpose));
`"full"` means VK reproduction was completed and compared against the
expected digest. This is a **historical fact about that reproduction run**,
not a live status — once recorded, it must never be silently upgraded (e.g.
`"partial"` → `"full"`) or downgraded later, including in response to
changes in current dependency resolvability. That's a separate concern,
already covered above: an attestation's scope describes what its reproducer
did at the time, independent of whether the same steps are resolvable today.

`verify.py` prints a suggested attestation at the end of a successful or
failed run, with `computed_vk_digest` already in the `{sha256, keccak256}`
object shape above — copy it as-is, or adapt it.

### Verifying a signed attestation's `proof.jws`

Confirmed attestations under `attestations/` (see
[`001-maha-strategies-2026-08-31.json`](attestations/001-maha-strategies-2026-08-31.json)
for an example) carry a `JsonWebSignature2020` proof over the attestation
document, canonicalized per RFC 8785 (JCS) with a detached, unencoded
payload (`b64: false` in the JWS header). Reconstructing the exact bytes
that `proof.jws` signs is not obvious from the JWS spec alone and is easy
to get wrong. The construction, step by step:

1. Take the full attestation JSON document (the top-level object, including
   `type`, `domain`, `reproducer`, `proof`, etc.).
2. Delete the **entire `proof` key** from that document — not just its
   `jws` field, and not `jws` set to `null` or `""`. The whole `proof`
   object (`type`, `created`, `verificationMethod`, `proofPurpose`,
   `canonicalization`, `domain`, and `jws` together) must be absent from
   the document you canonicalize.
3. Canonicalize the resulting document with RFC 8785 (JSON Canonicalization
   Scheme).
4. That canonical JSON, as raw bytes, is the JWS payload. Because the JWS
   header sets `b64: false` with `"crit": ["b64"]`, the signing input is
   `<base64url(header)> + "." + <payload bytes>` — the payload is **not**
   base64url-encoded before signing, per RFC 7797.
5. Verify `proof.jws` against that signing input using the public key
   resolved from `proof.verificationMethod` (a `did:key` DID here).

Only this exact construction — full `proof` key removed, RFC 8785
canonicalization, raw (non-base64url) detached payload — produces a valid
signature check. Plausible-looking variants (stripping only `jws` while
leaving the rest of `proof` in place, or zeroing out `jws` instead of
deleting the key) all canonicalize to different bytes and will fail
verification even though the signature itself is valid.

## Independent Reproductions

3 of the target 3-5 independent reproductions confirmed — Stage 1 minimum threshold met, all 3 cryptographically signed and independently verified. See `attestations/` for records.

## Scope

This bundle only proves circuit-provenance reproducibility (same
inputs → same VK). It is not the full escrow contract, not the proving
pipeline benchmarks, and not the passport/attestation contract code — those
live in the private project this was extracted from.
