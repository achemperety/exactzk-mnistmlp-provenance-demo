# exactzk-mnistmlp-provenance-demo

Standalone reproduction bundle for one circuit from a larger zkML-gated
payment escrow design: an MnistMLP classifier (52,650 params, K=8 batched
inference lanes) compiled with [EZKL](https://github.com/zkonduit/ezkl) into
a Halo2 verifying key (`vk.key`) that this project's passport attestation on
Base Sepolia references, and whose binding to the deployed verifier contract
is separately established (see "Two identifiers" below). MNIST is a public,
well-known dataset — this bundle carries no model IP beyond what that
implies. Context on the larger design:
[Atomic ZK-proof-gated settlement for x402 agent payments](https://ethresear.ch/t/atomic-zk-proof-gated-settlement-for-x402-agent-payments-a-measured-reference-design/25660).

This repo answers one narrow question: **given only the five files below,
can an independent party rebuild the exact same verifying key this project's
on-chain passport attestation references?** Yes — verified below, twice
(native + Docker). (This establishes the `vk.key` reproduction link only —
see "Two identifiers" below for what it does and doesn't say about the
deployed contract.)

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

## Target: the attested VK

| Digest | Value | What it is |
|---|---|---|
| `SHA256(vk.key)` | `1ed847e127419bc1d7db2a22779f75284975bf1908b33a43486ca9070e4ef627` | Raw artifact hash of the Halo2 verifying key file |
| `keccak256(vk.key)` | `dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f` | The `vkHash` actually submitted on-chain (Base Sepolia, chainId 84532) via this project's ERC-8004-style passport attestation |

`verify.py` reproduces `vk.key` from scratch and checks it against **both**
values (see "Two identifiers" for its relationship to the deployed verifier
contract).

## Two identifiers, and what each one actually establishes

This project tracks two distinct hashes of what is loosely called "the VK,"
and conflating them previously produced imprecise claims in this README (see
"What changed" below). Neither one is "the real" identifier — they answer
different questions:

| Identifier | Formula | What it establishes |
|---|---|---|
| `vkHash_file` | `keccak256(vk.key)` = `dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f` | That an independent party, given the five files in this repo, can reproduce the exact same `vk.key` this project's on-chain passport attestation is keyed on. **This is what `verify.py` checks, and what all four records in `attestations/` attest to — `004` reports it alongside `vkHash_bytecode` since reproducing the bytecode link required regenerating `vk.key` first.** |
| `vkHash_bytecode` | `keccak256(stripCborMetadata(eth_getCode(deployedVerifier)))` = `d0cab4041caaf77ea95fe45a29d14950be503ce26eb982af11026634112d8c67` | That the compiled, deployed Solidity verifier contract's runtime bytecode matches what `vk.key` (plus a pinned EZKL + solc toolchain) produces. This is a **separate, additionally-verifiable** link, not implied by a `vk.key` reproduction alone. **This is what `verify_deployment.py` checks.** |

The full chain, one digest per link:

```
model weights --[tier 1]--> vk.key --[tier 2]--> Halo2Verifier.sol --[tier 2]--> deployed bytecode
                (dd03fb0c…675f)                                        (d0cab404…d8c67, on Base Sepolia)
```

| Link | Reproduced by | Cost | What it does / does not establish |
|---|---|---|---|
| **Tier 1** — published artifacts → `vk.key` | Anyone who runs `compile_circuit`+`setup` from the five files in this repo (`verify.py`). Requires the weights-derived ONNX files. | ~15–100s, ~7–8 GB peak RSS (measured, varies by host) | Establishes that `vk.key` — and therefore the `vkHash_file` this project's passport attestation is keyed on — really does come from this published bundle. Says nothing on its own about what contract is actually deployed on-chain. **Independently confirmed 3 times** (`001`, `002`, `003`) — see `attestations/`, which also now holds tier 2's first independent confirmation (`004`; tier 1 vs. tier 2 scope is stated per file, not assumed from the directory — see "What tier 2 does..." below). |
| **Tier 2** — `vk.key` → `Halo2Verifier.sol` → deployed bytecode | Anyone with `vk.key` + `settings.json` + `srs.bin` — **no weights, no ONNX file, ever** (`verify_deployment.py`). | **MEASURED, this session, Apple Silicon macOS host, native (no Docker):** `create_evm_verifier()` 0.230s + `deploy_evm()` (solc compile + broadcast + mine, local Anvil) 0.079s ≈ **0.31s total**. The parent project's own measurement of this same step, on the same Apple Silicon M4 Pro, came in at ~0.28s — the ~10% spread between the two runs is ordinary run-to-run variance on one machine, not independent cross-host confirmation. A **cross-host reproduction** (not a timing benchmark — `004`'s notes report no seconds figure) now exists: `attestations/004-nsgoods-2026-09-08.json`, a disposable 8-core/16GB host with a fresh EZKL install, independent of the machine this 0.31s/0.28s comparison was measured on. No cross-host **timing** measurement has been published yet. Three fixed input files, exactly (`inspect.signature(ezkl.create_evm_verifier)` takes no ONNX or weights path). | Establishes that the runtime bytecode actually deployed at a given address is what `vk.key` compiles and deploys to, under EZKL `23.0.5`'s codegen and whatever solc version it selects internally (not independently pinned by this project). Says nothing about whether `vk.key` itself was honestly derived from real weights — that's tier 1's job. |

**Tier 2 now has one third-party attestation; tier 1 still has more.**
`attestations/001`–`003` are tier-1 attestations — a reproducer ran
`compile_circuit`+`setup` and confirmed `vkHash_file`. Until 2026-09-08, no
one but this repo's own maintainer had independently run tier 2 and signed a
record saying so; `attestations/004-nsgoods-2026-09-08.json` changes that.
nsgoods regenerated `vk.key` offline in a network-isolated container
(`--network none`) — rebuilding the chain from the published bundle rather
than taking `vk.key` on trust — then ran their own `create_evm_verifier` +
local `anvil`-deploy pipeline (their own driver, not this repo's
`verify_deployment.py`) and compared the resulting stripped bytecode hash
against live `eth_getCode` at
`0x886b1baceB0552B2A4159663879b2841F3d81739` on Base Sepolia. Their reported
digests (`vkHash_file`, `vkHash_bytecode`, `halo2verifier_sol_sha256`) match
this repo's expected values, and their notes describe reaching that result
before ever touching this repo's own checking script — so the agreement is
independent corroboration, not an artifact of running the maintainer's code
and trusting its output. Tier 1 still has more independent corroboration
(three records) than tier 2 (one record); that gap is real, just narrower
than before. `verify_deployment.py` remains available for anyone who wants
to check the second link themselves rather than rely on `004` — see
"Verifying a signed attestation's proof" below for how `004`'s signature was
checked.

The verifier contract you can check this against is a pure verifier — no
state writes, no funds, no owner, no admin surface — at
`0x886b1baceB0552B2A4159663879b2841F3d81739` on Base Sepolia (chainId 84532).

**What that address is, precisely:** a standalone instance of this exact
contract, deployed solely so that the `vk.key` → deployed-bytecode link
above is publicly checkable by anyone. It was deployed from a key with no
relationship to any other address in this project, funded from a public
faucet on Ethereum Sepolia and bridged to Base Sepolia via the canonical
bridge, used for this one deployment transaction and nothing else, and never
funded from or in contact with any other address belonging to this project.
Its bytecode is byte-identical to the verifier actually deployed in
production — same `vkHash_bytecode`, same `d0cab404…d8c67` — but it is
**not** that production deployment. (The passport attestation itself is
keyed on `vkHash_file`, not on any verifier address; the production
verifier's address lives in the parent project's escrow model record, not
in the attestation.) The
production verifier's address is deliberately not published here: from a
contract address alone, anyone can read its creation transaction, recover
the deploying key, and from that key's nonce sequence recover every other
contract address it deployed, which would deanonymize the rest of this
project's operational contract set. Publishing a bytecode-identical mirror
from an unrelated key gives you the same verification power (you are
checking the same bytecode) without that side effect. If you're trying to
verify that *the production system* runs this bytecode, this address
doesn't show you that directly — it shows that this bytecode, from this
published `vk.key`, produces `d0cab404…d8c67` when deployed, which you can
then compare against `eth_getCode` of whatever address the production
system actually uses, if and when that address is disclosed to you through
some other channel.

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

## Reproduce — the second link (`verify_deployment.py`)

`verify.py` above only reproduces the first link (published artifacts →
`vk.key`). To also check the second link (`vk.key` → deployed bytecode),
run:

```bash
python3 -m venv venv && source venv/bin/activate
pip install ezkl==23.0.5 eth-utils==6.0.0 pycryptodome==3.20.0
python3 verify_deployment.py
```

This is **not as turnkey as `verify.py`** — read its docstring before
running it. It needs everything `verify.py` needs, **plus**:

- A local [Foundry](https://getfoundry.sh) install (specifically the `anvil`
  binary on `PATH`), to spin up a throwaway local chain to deploy the
  verifier to. **This repo's Dockerfile does not install Foundry** — the
  Docker path above covers `verify.py` only, not `verify_deployment.py`, so
  running the latter in Docker means building your own image with Foundry
  added.
- Outbound network access the first time it runs, for two reasons: EZKL's
  `deploy_evm()` downloads and caches whatever solc version it selects
  internally (this project does not pin or control that version), and the
  script's final check reads live `eth_getCode` from a public Base Sepolia
  RPC (`https://sepolia.base.org` by default, overridable with `--rpc-url`).

By default it also regenerates `vk.key` from scratch first (same
`compile_circuit`+`setup` step as `verify.py`, same ~15–100s/~7–8 GB RSS
cost) so the whole run is self-contained from the published bundle alone.
If you already have a `vk.key` you trust — e.g. kept from a prior
`verify.py` run — pass `--vk-path` to skip straight to the weight-free part
(create the Solidity verifier, compile, deploy locally, compare bytecode).
That skipped step is the only place weights are involved anywhere in this
script; everything after it is weight-free per the "Two identifiers" table
above.

It prints every intermediate hash (`vk.key`'s two digests, the generated
`Halo2Verifier.sol`'s SHA256, the local deployment's stripped bytecode
keccak256, and the live Base Sepolia deployment's stripped bytecode
keccak256) and exits non-zero on any mismatch.

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

### Verifying a signed attestation's proof

Confirmed attestations under `attestations/` use **one of three** proof
constructions, not one:

| File | Construction | Scheme |
|---|---|---|
| [`001-maha-strategies-2026-08-31.json`](attestations/001-maha-strategies-2026-08-31.json), [`002-bitsanity-2026-09-04.json`](attestations/002-bitsanity-2026-09-04.json) | `proof.type: JsonWebSignature2020` | JWS over RFC 8785 (JCS) canonical bytes, `did:key` signer |
| [`003-nsgoods-2026-09-07.json`](attestations/003-nsgoods-2026-09-07.json) | `proof.type: EthereumEip191Signature`, embedded `proof` object | EIP-191 `personal_sign` over RFC 8785 (JCS) canonical bytes with the whole `proof` key removed, Ethereum-address signer |
| [`004-nsgoods-2026-09-08.json`](attestations/004-nsgoods-2026-09-08.json) | No `proof` object — `payload` is a top-level sibling of `signature`/`jcs_sha256`/`jcs_len`/`signed_by`/`scheme` | EIP-191 `personal_sign` over RFC 8785 (JCS) canonical bytes of the `payload` sub-object *only*, Ethereum-address signer |

All three constructions are hard to get right from the spec alone; all
three are given in full below, plus — for the EIP-191 cases (`003`, `004`)
only — a separate, required check of whether the signing key was actually
*authorized* to make this kind of statement.

#### `JsonWebSignature2020` (001, 002)

These carry a `JsonWebSignature2020` proof over the attestation document,
canonicalized per RFC 8785 (JCS) with a detached, unencoded payload
(`b64: false` in the JWS header). Reconstructing the exact bytes that
`proof.jws` signs is not obvious from the JWS spec alone and is easy to get
wrong. The construction, step by step:

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

#### `EthereumEip191Signature` (003)

003's `proof` object carries `type` (`EthereumEip191Signature`),
`canonicalization` (`RFC8785`), `signingScheme` (a human-readable
description of the construction below), `signerAddress`, a
`signerAuthorityManifest` URL, and `signature` — no `jws` field at all. A
reader following the JWS steps above against this file finds no `jws` to
verify. Use this construction instead:

1. Take the full attestation JSON document (the top-level object).
2. Delete the **entire `proof` key** — same rule as the JWS case: not just
   `proof.signature`, the whole object.
3. Canonicalize the resulting document with RFC 8785 (JCS). For this
   document — plain strings, booleans, and one nested object, no
   floating-point numbers — this is byte-identical to
   `json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`,
   which is how the signer's own manifest describes its other
   JCS-canonicalized bodies. Verified directly for this file: canonicalizing
   003 with `proof` removed this way produces exactly 592 bytes whose
   SHA-256 is `ad92f9c0a8bf92132b39a740a3a4a557a39e7c08041545f1aeb897f46d2d0051`
   — which matches the `jcs_sha256` published for this attestation in the
   signer's manifest (`reproduction_attestations[0].jcs_sha256`, see below).
   That length also matches the literal `"592"` embedded in
   `proof.signingScheme` in the attestation itself, step 4.
4. Apply the EIP-191 `personal_sign` prefix to those canonical bytes and
   hash: `keccak256("\x19Ethereum Signed Message:\n" + str(len(canonical_bytes)) + canonical_bytes)`
   — the length is the **decimal ASCII digit string of the byte count**
   (`"592"`, three characters), concatenated as bytes, not a binary-encoded
   integer. This matches `proof.signingScheme` in the attestation verbatim.
5. Recover the signer address from `proof.signature` against that prefixed
   hash (standard secp256k1 recovery, e.g. `eth_account.Account.recover_message`
   with `encode_defunct(primitive=canonical_bytes)` in Python, which performs
   steps 4–5 for you).
6. Compare the recovered address, case-insensitively, against
   `proof.signerAddress`.

As with the JWS case, near-miss variants silently produce different bytes
and a failed (or worse, no-signal) verification: removing only
`proof.signature` instead of the whole `proof` key canonicalizes to a
different document (922 bytes, `sha256=0dbc24919ae0ddaf21781626d9fef676f7002a4fac437c69259dfc4cc022a7bc`
for 003 today) and will not recover the right address; canonicalizing the
document with `proof` still fully attached is circular and equally wrong
(1069 bytes here). Only "whole `proof` key removed, then RFC 8785" is
correct — the same rule as the JWS case, just feeding a different
signature scheme afterward.

**Executed and confirmed for this task** (2026-09-09, against the
committed `attestations/003-nsgoods-2026-09-07.json`): the above procedure,
run end to end, recovers `0x57fF0F084Cba33e6761503f90eEF0Da9F159350c` from
`proof.signature`, which matches `proof.signerAddress` exactly. The
signature is valid.

#### The authority check is a separate step

A valid signature only establishes that a key signed the document — it
does **not**, by itself, establish that the key was *authorized* to make a
reproduction-attestation claim. A reader who stops at "signature verifies"
has verified less than they think. The second, required step:

1. Resolve `proof.signerAuthorityManifest`
   (`https://x402.nsgoods.org/proof/index.json` for 003).
2. Find the signer entry for `proof.signerAddress` in the manifest's
   `signers` (or `signer_registry`) map.
3. Check that its authorized scope list includes the scope that covers
   reproduction attestations.

Fetched directly for this task (manifest `generated_at` timestamp at fetch
time: `2026-09-08T18:10:09.537465+00:00` — this document is regenerated in
place, so re-fetching later may show a different timestamp even if the
signer entry is unchanged): `signers["0x57fF0F084Cba33e6761503f90eEF0Da9F159350c"]`
lists `["sanctions", "screen-multi", "preflight", "settle", "watchdog",
"reproduction-attestations"]` — `reproduction-attestations` is present, so
this key was authorized for this attestation. The same manifest also
publishes, as of that fetch, a `reproduction_attestations` array with an
entry naming this exact repository, `attestations/003-nsgoods-2026-09-07.json`,
`signed_by` matching `proof.signerAddress`, and the `jcs_sha256` quoted in
step 3 above — an independent, signer-published record of the same
attestation this file carries.

The manifest's own `signer_policy` states its rotation convention
plainly: signers "do not rotate silently; a rotation adds the new address
alongside the old with a validity boundary before the old key stops
signing," and an **unannounced key change is to be treated as compromise —
fail closed, same as a signature mismatch.** A reader relying on a
`signerAddress` should pin it from the manifest rather than trust it on
first sight, per that same policy.

#### EIP-191 payload envelope (004)

`004`'s shape differs from both prior constructions in one structural way:
there is no `proof` object at all. The top-level document is a flat
envelope:

- `payload` — the actual attestation content (`reproducer`, `date`,
  `ezkl_version`, `verification_scope`, `tag`, `vkHash_file`,
  `vkHash_bytecode`, `halo2verifier_sol_sha256`, `checked_against`,
  `matches_expected`, `notes`), nested one level under the `payload` key.
- `jcs_sha256`, `jcs_len` — the canonical-byte digest and length of
  `payload` *alone*, published so a verifier can sanity-check their own
  canonicalization before touching the signature at all.
- `signature`, `signed_by` — the EIP-191 signature and the address it
  claims to recover to.
- `scheme` — a human-readable description of the construction.

`scheme` reads: "...over the RFC8785/JCS canonicalization of
`attestations/004-nsgoods-2026-09-08.json`" — read literally, that names
the *whole file* as the canonicalization target. That reading cannot be
what's actually signed: the file contains `signature` itself, so
canonicalizing "the whole file" to check a signature embedded in that same
file is circular by construction — there is no consistent set of bytes that
is simultaneously "the file" and "what the file's signature covers" without
first deciding what to exclude, which the sentence never says. The only
non-circular reading is that `scheme` is naming the *attestation this file
represents* colloquially by its filename, and the actual signing input is
the `payload` sub-object — which sits beside the signature rather than
containing it, so (unlike `003`) there is no key to delete from a larger
document first: `payload` is taken as-is.

Executed and confirmed for this task (2026-09-09), against the committed
`attestations/004-nsgoods-2026-09-08.json`: canonicalizing only the
`payload` sub-object with RFC 8785 (JCS) produces exactly **1160 bytes**,
matching the document's own declared `jcs_len` exactly; the SHA-256 of
those bytes is `eb3ed181802b2e69532e5393e097177f57f11253c8b77d61aef9797c7c310e54`,
matching the declared `jcs_sha256` exactly. Applying the EIP-191
`personal_sign` prefix to those 1160 bytes
(`keccak256("\x19Ethereum Signed Message:\n1160" + canonical_bytes)`,
decimal ASCII length as in `003`, not a binary-encoded integer) and
recovering the signer from `signature` yields
`0x57fF0F084Cba33e6761503f90eEF0Da9F159350c`, which matches `signed_by`
exactly. The signature is valid.

Three near-miss readings were checked and none recover the right address:
canonicalizing the whole envelope with only `signature` removed (still
includes `jcs_sha256`, `jcs_len`, `signed_by`, `scheme` as siblings —
fields *about* the signature, not part of what it covers, since they're
outside `payload`) recovers a different address entirely; signing the hex
`jcs_sha256` string as ASCII text instead of the raw canonical bytes it's a
digest of recovers a different address; and signing the raw 32-byte SHA-256
digest bytes of `payload`'s canonicalization, instead of those canonical
bytes themselves, also recovers a different address. Only "canonicalize
`payload` alone, apply EIP-191 directly to those bytes" is correct.

**The authority check, same as `003`:** fetched for this task (manifest
`generated_at` at fetch time: `2026-09-08T20:21:26.254895+00:00` — again,
this document is regenerated in place, so a later fetch may show a
different timestamp): `signers["0x57fF0F084Cba33e6761503f90eEF0Da9F159350c"]`
in `https://x402.nsgoods.org/proof/index.json` still lists
`"reproduction-attestations"` in its scope, so the same key remains
authorized. The manifest's `reproduction_attestations` array carries a
second entry (alongside `003`'s) naming
`attestations/004-nsgoods-2026-09-08.json`, `signed_by` matching
`signed_by` above, and `jcs_sha256` matching the value confirmed by
independent computation above — the signer's own published record agrees
with what this repo can verify unilaterally.

#### No verification script in this repo covers any of the three proof constructions

None of `verify.py` or `verify_deployment.py` reads `attestations/*.json`
or checks a `proof`/envelope of any kind — `verify.py` only *prints a
suggested* (unsigned) attestation for a fresh run, and
`verify_deployment.py` covers the separate tier-2 bytecode link, not
attestation signatures. So there is no existing script that "errors on 003
or 004" — there is no code path that touches any of the three proof
constructions today; all three are currently manual-only. Extending
`verify.py` (or a new `verify_attestations.py`) to check all three would
need: a JCS/RFC 8785 canonicalizer (a plain
`json.dumps(sort_keys=True, separators=(",", ":"))` suffices for the
float-free documents in this repo, but a real RFC 8785 implementation would
be needed for exact correctness in general), an ES256K JWS verifier keyed
off a resolved `did:key` for the 001/002 scheme, `eth_account`'s
`recover_message` for the 003 and 004 schemes (with different bytes fed in
for each, per above), and — to make the authority check automatic rather
than manual — an HTTP fetch of each attestation's authority manifest plus a
scope-membership check before treating a valid signature as sufficient. Not
built as part of this task, per scope.

## Independent Reproductions

3 of the target 3-5 independent tier-1 reproductions confirmed — Stage 1
minimum threshold met, all 3 cryptographically signed and independently
verified (`001`, `002`, `003`). A first independent tier-2
(deployed-bytecode) reproduction has also been confirmed and signed (`004`,
2026-09-08) — see "Two identifiers" above for what tier 1 and tier 2 each
establish, and why they're counted separately. See `attestations/` for all
records.

## What changed — 2026-09-08

The deployed verifier contract had, for a period, been generated from an
earlier `vk.key` state than the canonical one this repo publishes and
`verify.py` reproduces — a stale deployment, not a stale published artifact.
Found and fixed on 2026-09-08: the verifier was regenerated and redeployed
from the canonical `vk.key` (**re-measured this session**, its stripped
bytecode hash — `d0cab4041caaf77ea95fe45a29d14950be503ce26eb982af11026634112d8c67`
— now matches live `eth_getCode` at the deployed address exactly, confirmed
three independent ways: this repo's own local-anvil reproduction via
`verify_deployment.py`, a direct `eth_getCode` read against Base Sepolia,
and the previously-published expected value). A fail-closed freshness guard
now runs before any (re)deployment is treated as canonical, specifically to
prevent this class of drift from recurring silently.

**The three existing attestations in `attestations/` are unaffected by this
finding.** They attest to reproducing `vk.key` from the published bundle
(`vkHash_file`) — a claim about the *first* link in the chain, which was
true when they were signed and remains true today; none of them made a
claim about the deployed bytecode (`vkHash_bytecode`, the *second* link),
so none of them needed correcting. This release's actual contribution is
publishing that second link's definition, measured cost, and a script
(`verify_deployment.py`) that lets anyone check it themselves — see "Two
identifiers" above. That check did not exist, for anyone, before this
release; it is not that it existed and failed.

## What changed — 2026-09-09

The first independent tier-2 reproduction was added:
`attestations/004-nsgoods-2026-09-08.json`, signed by nsgoods under tag
`pp-bytecode-v1`.

**Why this carries more weight than a second same-host run would.** The
reproducer's own independent driver produced identical values before ever
running this repo's `verify_deployment.py`, so the agreement is not an
artifact of running this repo's own script and trusting its output.
`vk.key` was regenerated offline, in a network-isolated container, first —
the chain was rebuilt from the published bundle rather than taken on trust.
And it ran on a separate host with a fresh EZKL install, making it the
first cross-host confirmation of the bytecode link.

**What it does not establish.** No cross-host *timing* figure exists —
`004`'s notes report no seconds measurement, and none was invented for it.
Every timing number elsewhere in this README remains same-host.

**What was checked on this side before accepting it.** The signature was
verified by execution against five candidate byte sequences; only one
recovers the declared signer, resolving an ambiguity in the attestation's
own `scheme` string. The signer's authorization was confirmed separately
against the published authority manifest. The repo commit the attestation
cites was confirmed to exist (it is `HEAD`). `004` is also a third
signature construction, distinct from the two already documented — see
"Verifying a signed attestation's proof" above.

## Scope

This bundle only proves circuit-provenance reproducibility (same
inputs → same VK). It is not the full escrow contract, not the proving
pipeline benchmarks, and not the passport/attestation contract code — those
live in the private project this was extracted from.
