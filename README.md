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
| `vkHash_file` | `keccak256(vk.key)` = `dd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f` | That an independent party, given the five files in this repo, can reproduce the exact same `vk.key` this project's on-chain passport attestation is keyed on. **This is what `verify.py` checks, and what all five records in `attestations/` attest to — `004` reports it alongside `vkHash_bytecode` since reproducing the bytecode link required regenerating `vk.key` first, and `005` reports the solo circuit's own `vkHash_file` (`13cff042…4ff2`) rather than this batch one.** |
| `vkHash_bytecode` | `keccak256(stripCborMetadata(eth_getCode(deployedVerifier)))` = `d0cab4041caaf77ea95fe45a29d14950be503ce26eb982af11026634112d8c67` | That the compiled, deployed Solidity verifier contract's runtime bytecode matches what `vk.key` (plus a pinned EZKL + solc toolchain) produces. This is a **separate, additionally-verifiable** link, not implied by a `vk.key` reproduction alone. **This is what `verify_deployment.py` checks.** |

The full chain, one digest per link:

```
model weights --[tier 1]--> vk.key --[tier 2]--> Halo2Verifier.sol --[tier 2]--> deployed bytecode
                (dd03fb0c…675f)                                        (d0cab404…d8c67, on Base Sepolia)
```

| Link | Reproduced by | Cost | What it does / does not establish |
|---|---|---|---|
| **Tier 1** — published artifacts → `vk.key` | Anyone who runs `compile_circuit`+`setup` from the five files in this repo (`verify.py`). Requires the weights-derived ONNX files. | ~15–100s, ~7–8 GB peak RSS (measured, varies by host) | Establishes that `vk.key` — and therefore the `vkHash_file` this project's passport attestation is keyed on — really does come from this published bundle. Says nothing on its own about what contract is actually deployed on-chain. **Independently confirmed 3 times for the batch circuit** (`001`, `002`, `003`) **and once for the solo circuit** (`005`, 2026-09-13) — see `attestations/`, which also holds tier 2's first independent confirmation (`004`; tier 1 vs. tier 2 scope, and which *circuit* a record covers, are stated per file, not assumed from the directory — see "What tier 2 does..." below). |
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
python3 verify.py               # batch
python3 verify.py --circuit solo   # solo
```

**Python version:** this native path is verified under **Python 3.13.6** —
what actually reproduced both circuits' canonical digests this session. No
other interpreter version has been tested against the native path; treat
3.13.6 as the one confirmed point, not a stated-compatible range. (The
Docker path below pins `python:3.11-slim` in its base image, but that pin
has not been exercised by an actual build+run in this environment — see
"Docker verification status" below before treating 3.11 as confirmed too.)

`verify.py` runs `ezkl.compile_circuit()` then `ezkl.setup()` (no GPU
required). Cost differs substantially by circuit:

| Circuit | Wall-clock | Peak RSS | `pk.key` byproduct |
|---|---|---|---|
| batch (default) | ~15–100s (host-dependent) | ~7–8 GB | ~5.2 GB, written to a temp dir, deleted on exit |
| solo (`--circuit solo`) | ~1.8–14.5s across three measured hosts | ~0.96–1.55 GB across the same three hosts | ~0.66 GB, same temp-dir/delete-on-exit handling |

Solo's numbers are a **measured range across three hosts, not a requirement** —
see "Cost: three measured hosts, one `vk.key`" under "Solo bundle" below for
each host and its own figures. The fast/high-memory end is an Apple Silicon
macOS host; the slow/low-memory end is a 2-core x86 cloud VM. All three land on
the same `vk.key`, byte for byte.

`pk.key` is a byproduct of `setup()` in both cases, not itself part of what's
being verified here.

## Reproduce — Docker (no local toolchain dependency)

```bash
docker build -t mnistmlp-repro .
docker run --rm mnistmlp-repro                              # batch (default, same as before)
docker run --rm mnistmlp-repro --circuit solo                # solo
```

One image covers both circuits — `solo/` is copied into the image alongside
the batch files, and the circuit is chosen at `docker run` time (via
`ENTRYPOINT`/`CMD`, not baked into the image), not by rebuilding. Running
with no arguments keeps the exact default behavior this image has always
had: batch.

The `Dockerfile` pins `ezkl==23.0.5`, `eth-utils==6.0.0`, and
`pycryptodome==3.20.0` (the keccak256 backend `eth-utils` needs) explicitly, so
this path doesn't depend on your local Python/pip resolving the same
versions "by luck." It also pins `--platform=linux/amd64`, because
`ezkl==23.0.5` ships a `manylinux2014_x86_64` wheel on PyPI but no
`linux/aarch64` wheel for this version — on an Apple Silicon Docker host
this runs under emulation (works, just slower to build/pull than native).
The base image is `python:3.11-slim`, pinned by content digest.

**Memory: scoped per circuit, not one blanket number.** The two circuits'
requirements differ by roughly 5×, and applying batch's number to a solo run
wastes most of an ~8 GB container allowance; applying solo's number to a
batch run OOM-kills it.

| Circuit | Container memory |
|---|---|
| batch (default) | at least ~8 GB, extrapolated from the native peak RSS above plus container overhead (Docker Desktop's default resource limits are usually sufficient on modern machines; increase if `setup()` gets OOM-killed) — **not independently measured through Docker itself, see below** |
| solo (`--circuit solo`) | at least ~2 GB, extrapolated from the **highest** native peak RSS measured on any host so far (~1.55 GB) plus container/base-image overhead — the lowest measured host needed only ~957 MB, so ~2 GB is a ceiling to provision against, not a floor solo needs — **not independently measured through Docker itself, see below** |

### Docker verification status

**Not verified by an actual build+run as of this revision.** Docker was not
available in the environment these Dockerfile and README changes were made
in (`docker info` failed, and the local Docker Desktop install was
incomplete — its app bundle pointed at an unmounted volume). The memory
figures above are extrapolated from the native, non-Docker peak-RSS
measurements elsewhere in this README, plus a margin for base-image and
container overhead — **not measured inside a container**, and the wall-clock
cost of `linux/amd64` emulation on non-x86 hosts (mentioned above) is
entirely unmeasured for both circuits.

Before this bundle goes to reviewers, someone with a working Docker install
needs to actually run:

```bash
docker build -t mnistmlp-repro .
docker run --rm mnistmlp-repro                # confirm still reproduces batch's dd03fb0c…675f
docker run --rm mnistmlp-repro --circuit solo # confirm now reproduces solo's 13cff042…4ff2
```

and replace this section with the measured wall-clock and peak container
memory for both. Until that happens, treat the Docker path as
structurally updated (files copied, circuit selectable at `docker run`
time) but **functionally unverified**.

**The two solo reproductions of 2026-09-13 do not close this item.** Both were
native runs — one on Apple Silicon, one on an x86 cloud host under
`unshare -n` — so neither exercised the `Dockerfile`, the pinned
`python:3.11-slim` base image, the `linux/amd64` emulation path, or a
container memory limit. Reproducing `vk.key` natively and reproducing it
through this image are different claims, and only the first now has
third-party evidence. Note also the analogy this section used to draw is now
spent: solo's `vk.key` digest *has* since been reproduced from scratch by a
third party (`attestations/005-nsgoods-2026-09-13.json`); the Docker path is
now the only item here still in the "structurally updated, functionally
unverified" state.

**What would close it, and who can.** One of the `005` reproducers has offered
to run the container on a throwaway host. The item closes when someone
publishes, for **each** circuit: wall-clock, peak **container** memory (not
host RSS), and confirmation that the run printed the circuit's canonical
digest — `dd03fb0c…675f` for batch, `13cff042…4ff2` for solo. Anything less
than both circuits, or a host-RSS figure standing in for a container figure,
leaves it open.

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

## Solo bundle

Everything above covers the K=8 batch circuit. This repo also publishes the
**solo** circuit (`batch_size: 1`, same underlying model) alongside it, in
`solo/`, structured the same way so the tooling and conventions above carry
over directly — the only difference is `--circuit solo` on `verify.py` and a
`solo/` directory prefix on every path.

### Files

| File | Purpose |
|---|---|
| `solo/model_solo.onnx` + `solo/model_solo.onnx.data` | The ONNX model (external-data format) |
| `solo/settings.json` | EZKL circuit settings (`batch_size: 1`) |
| `solo/input.json` | A real sample input actually used to build and witness this circuit |
| `solo/srs.bin` | The structured reference string used for `setup()` — same caveats as the batch `srs.bin`, see "About `srs.bin`" above |

**`model_solo.onnx.data` is byte-identical to the batch bundle's
`model_k8.onnx.data`** — confirmed live for this release, not assumed from
an earlier finding: both hash to
`sha256=b96f93301048ea7af8eeaca094fee834111a4c1a3a639f17fb5f61b0b13a2612`.
If you've already fetched the batch bundle, you already have this file —
the remaining four below are the only new bytes solo actually needs from
you, which is the point of publishing it alongside batch rather than as a
separate download.

Pinned input digests (checked automatically by `verify.py --circuit solo`
before it runs anything):

```
model_solo.onnx       sha256=c3caeb161859f91da3233830c3f43e5ed9f0c47cdc2913d1a48ffe42a3a51e90
model_solo.onnx.data  sha256=b96f93301048ea7af8eeaca094fee834111a4c1a3a639f17fb5f61b0b13a2612
settings.json         sha256=dcae92a6d5fd8435b299b2df1f727a370fbdf9db9461e6d997c7bdd4b94ac6c4
input.json            sha256=892c2f91fcd78b846e83f510b70db8c7e5480e692c989a3ed8c6e81632cd84c3
srs.bin                sha256=e4690b6479fceefdc2486372ceeaf274d7a336f908463caa619b7bc42ebfe9be
```

The same five digests, `sha256sum`-compatible, are committed as
[`solo/MANIFEST.sha256`](solo/MANIFEST.sha256) — same convenience-pointer
status as the root `MANIFEST.sha256` above:

```bash
cd solo && shasum -a 256 -c MANIFEST.sha256
```

`solo/MANIFEST.sha256`'s own bundle digest (`SHA256(solo/MANIFEST.sha256)`):

```
db0d6fe41a387d25f14902e9acada2c00c35c884e353d803aeccdda6ebc85b8f
```

### Target: the solo `vk.key`

| Digest | Value | What it is |
|---|---|---|
| `SHA256(vk.key)` | `32439290a76c2ef71fb6f20ef203b001b54d9835b411554bae827df5364e9523` | Raw artifact hash of the solo Halo2 verifying key file |
| `keccak256(vk.key)` | `13cff0426abe00c941934bdd6bb7757f2e703fb9f6862bf08a783eeca08b4ff2` | The solo circuit's `vkHashFile`, as registered in its on-chain `CircuitRecord` on the public mirror stack (see "The public mirror stack" below) |

Both digests were computed from a fresh, from-scratch reproduction run done
for this release — `ezkl.compile_circuit()` + `ezkl.setup()` against the
four files above, in a clean temp directory — not quoted or carried over
from an earlier document. `verify_onchain_quorum.py`'s live on-chain read
confirms the same `vkHashFile` is what the public mirror's solo
`CircuitRecord` actually carries.

**Both digests have since been reproduced independently**, on 2026-09-13, by a
third party on different hardware —
[`attestations/005-nsgoods-2026-09-13.json`](attestations/005-nsgoods-2026-09-13.json),
signed — and by a second reproducer who reported the same digests unsigned. See
"Cost: three measured hosts, one `vk.key`" below.

### Reproduce

```bash
python3 -m venv venv && source venv/bin/activate
pip install ezkl==23.0.5 eth-utils==6.0.0 pycryptodome==3.20.0
python3 verify.py --circuit solo
```

#### Cost: three measured hosts, one `vk.key`

These are measurements, not requirements. Solo's `vk.key` is **157,511 bytes**
on every one of them, with the same `sha256` and the same `keccak256` — the
length is not separately attested by each reproducer, it follows from the
matching `sha256` over the whole file:

| Host | Interpreter | Wall-clock | Peak RSS | Source |
|---|---|---|---|---|
| Apple Silicon macOS, native | Python 3.13.6 | ≈1.8s | ≈1.55 GB | this repo, re-measured 2026-09-14 (the 2026-09-13 release recorded ≈2.3s / ≈1.5 GB on an Apple Silicon macOS host too) |
| Apple Silicon, native | Python 3.13.6 | ≈3.13s | ≈1.37 GB | independent reproducer, unsigned report |
| 2-core x86 cloud VM, native, network namespace dropped (`unshare -n`) during compute | Python 3.13.15 | ≈14.5s | ≈957 MB | [`005-nsgoods-2026-09-13.json`](attestations/005-nsgoods-2026-09-13.json), signed |

**The spread is the point.** Wall-clock differs by roughly **6×** across these
hosts and peak RSS by about **400 MB** — and the output is byte-identical
anyway. That is determinism *demonstrated across architectures*, not asserted:
if the digest tracked anything host-specific — instruction set, core count,
interpreter patch version, allocator behaviour that peaked at 957 MB on one host
and 1.55 GB on another — these three runs would have diverged. They did not.
This is a stronger statement than two signatures on one architecture would have
been.

It also means **any single memory number here is host-specific.** Provision
against the range, not against one figure; ~957 MB was sufficient on the
smallest host measured.

About 8× smaller `srs.bin` than batch (8,388,868 bytes vs. 67,109,124 bytes)
gives proportionally smaller `setup()` cost, same relationship noted in "Solo
— published, and now independently reproduced" below.

`verify.py` with no argument, or `--circuit batch`, continues to reproduce
the batch bundle exactly as before — `--circuit` is an additive flag, not a
behavior change to the existing default path.

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
| [`004-nsgoods-2026-09-08.json`](attestations/004-nsgoods-2026-09-08.json), [`005-nsgoods-2026-09-13.json`](attestations/005-nsgoods-2026-09-13.json) | No `proof` object — `payload` is a top-level sibling of `signature`/`jcs_sha256`/`jcs_len`/`signed_by`/`scheme` | EIP-191 `personal_sign` over RFC 8785 (JCS) canonical bytes of the `payload` sub-object *only*, Ethereum-address signer |

`005` uses the same construction as `004`, so the count of constructions is
still three even though there are now five files. What changed between them is
the *description*: `004`'s `scheme` string names the whole file and is
imprecise; `005`'s names the `payload` sub-object and is accurate. See "`005`'s
`scheme` string is accurate" below.

All three constructions are hard to get right from the spec alone; all
three are given in full below, plus — for the EIP-191 cases (`003`, `004`,
`005`) only — a separate, required check of whether the signing key was
actually *authorized* to make this kind of statement.

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

#### `005`'s `scheme` string is accurate — the ambiguity in `004` was not repeated

`005` reuses `004`'s envelope exactly (`payload` sibling to `jcs_sha256`,
`jcs_len`, `signature`, `signed_by`, `scheme`), so the construction above
applies unchanged. Its `scheme` string, however, does not repeat `004`'s
imprecision. It reads, in part:

> EIP-191 `personal_sign` over the RFC8785/JCS canonicalization of the payload
> sub-object ONLY (`json.dumps` sort_keys, separators `(',',':')`); signing
> input = `keccak256("\x19Ethereum Signed Message:\n" + str(jcs_len) +
> jcs_bytes)`, decimal-ASCII length; recover == `signed_by`

Every element of that sentence was checked by execution against the committed
file, and every element holds:

- **Canonicalization target.** The `payload` sub-object alone canonicalizes to
  exactly **841 bytes**, matching the declared `jcs_len`; their SHA-256 is
  `ad63a636e8fabe78f06b6fdc879326af011a767df79dadf035c8bedb3af891cf`, matching
  the declared `jcs_sha256`.
- **Prefix and length encoding.** Applying
  `keccak256("\x19Ethereum Signed Message:\n841" + canonical_bytes)` — decimal
  ASCII, as in `003` and `004` — and recovering from `signature` yields
  `0x57fF0F084Cba33e6761503f90eEF0Da9F159350c`, matching `signed_by`.
- **The whole-file reading is excluded by test, not by argument.**
  Canonicalizing the whole envelope recovers
  `0x98A41998098640882e613c986a5D1c259820f67F`; canonicalizing the whole
  envelope with only `signature` removed recovers
  `0x13aC73C10b6a58f207c37508F2d6A81d7d727F46`. Neither is the declared signer.
  `004`'s wording left a reader to *reason* their way out of the circular
  reading; `005`'s wording simply does not create it.
- **The stated canonicalizer is exact here.** `005` names `json.dumps` with
  `sort_keys` and compact separators as its RFC 8785 stand-in. Those two
  disagree in general — on number formatting and on non-ASCII escaping — but
  `005`'s `payload` contains no numbers and only ASCII strings and booleans, so
  the two produce identical bytes for this document. Verified rather than
  assumed: the `ensure_ascii=True` and `ensure_ascii=False` serializations are
  byte-equal here.

**Reported both ways, as asked:** `004`'s scheme string was imprecise and the
correction lives in the signer's manifest (next section); `005`'s is accurate as
written and needs no correction.

**The authority check, same as `003` and `004`:** fetched for this task, with
the manifest's own `generated_at` at fetch time recorded as
`2026-09-13T18:05:09.428930+00:00` (this document is regenerated in place, so a
later fetch may show a different timestamp — everything stated here is stated
about *that* revision).
`signers["0x57fF0F084Cba33e6761503f90eEF0Da9F159350c"]` in
`https://x402.nsgoods.org/proof/index.json` lists `"reproduction-attestations"`
in its scope, and `signer_registry` gives that address `status: "active"` with
`valid_until: null`. The manifest's `reproduction_attestations` array carries a
third entry, naming `attestations/005-nsgoods-2026-09-13.json`, `signed_by`
matching, and `jcs_sha256` matching the value computed independently above.
Authorization was checked against the manifest **separately** from the
signature — a valid signature from an unauthorized key would still not count.

**References the attestation cites, confirmed to exist.** `005` cites no repo
commit hash. It cites `verify.py --circuit solo`, which exists and accepts that
flag, and the solo `vkHashFile` registered on Base Sepolia (84532), which
`verify_onchain_quorum.py` reads live as
`0x13cff0426abe00c941934bdd6bb7757f2e703fb9f6862bf08a783eeca08b4ff2` — the same
value `005` reports. Its two digests were compared against this repo's own
expected solo values in `verify.py` (`expected_vk_sha256`,
`expected_vk_keccak256`), not against the README prose, and both match.

#### The `scheme`/`signingScheme` wording in 003 and 004 is imprecise — files left unedited

Every digest, address, and signature confirmed in the two sections above is
correct — the step-by-step constructions given there are what this repo
actually executed and verified. Separately, the attester has confirmed that
each file's own one-line description of that construction (`003`'s
`proof.signingScheme` / `proof.canonicalization`, `004`'s `scheme`) is
imprecise about *scope*:

- **`003`**: `proof.canonicalization: "RFC8785"` names the scheme but not
  what it's applied to, and doesn't state that `proof` is excluded — a
  reader could take it to mean the whole document. The accurate scope,
  already derived and executed step by step above: RFC 8785 over the
  document **with the whole `proof` key removed**, not the whole file.
- **`004`**: `scheme` reads "...over the RFC8785/JCS canonicalization of
  `attestations/004-nsgoods-2026-09-08.json`" — read literally, the whole
  file. As derived above, that reading is circular (the file contains the
  signature it would be canonicalizing) and cannot be what's actually
  signed. The accurate scope, already derived and executed step by step
  above: RFC 8785 over the **`payload` sub-object only**, not the whole
  file.

This correction comes from the signer, not from a re-reading of the files on
this end: `https://x402.nsgoods.org/proof/index.json`'s
`reproduction_attestations` entries for `003` and `004` now state each
scope explicitly and unambiguously — "...with proof key removed" for `003`,
"...over payload sub-object only" for `004` — alongside the same
`jcs_sha256` values independently confirmed above. The signer's manifest now
carries the accurate semantics; the attestation files' own summary sentence
does not.

**`003` and `004` themselves are deliberately left unedited.** Both are
published, signed artifacts that exist byte-for-byte both in this repo and
at the signer's own URLs above; editing this repo's copy would make the two
diverge while this README elsewhere states they are kept identical. The
signer made the same call himself a week earlier — pinning the accurate
semantics in his manifest rather than re-signing either file. A reader who
follows the step-by-step construction given in full in the sections above —
not the files' own summary sentence — lands on the correct bytes either way,
which is exactly why every digest and signature above verifies despite the
imprecise wording.

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

**Batch circuit, tier 1:** 3 of the target 3-5 independent reproductions
confirmed — Stage 1 minimum threshold met, all 3 cryptographically signed and
independently verified (`001`, `002`, `003`).

**Batch circuit, tier 2:** a first independent deployed-bytecode reproduction
confirmed and signed (`004`, 2026-09-08).

**Solo circuit, tier 1:** first independent reproduction confirmed and signed
(`005`, 2026-09-13), plus a second, unsigned reproduction reported the same
digests on different hardware. Solo's bundle was published on 2026-09-13 with
zero third-party reproductions; both arrived within a day of it. Its tier 2
remains at zero.

See "Two identifiers" above for what tier 1 and tier 2 each establish and why
they're counted separately, and "Solo — published, and now independently
reproduced" below for what the two solo runs jointly demonstrate about
determinism across architectures. See `attestations/` for all records; each file
states its own circuit and tier, which is not inferable from the directory.

The five files are digest-pinned in
[`attestations/MANIFEST.sha256`](attestations/MANIFEST.sha256) — same
convenience-pointer status as the two bundle manifests above (`shasum -a 256 -c`
detects accidental corruption, not a determined edit; the signatures inside the
files are the real integrity mechanism). That manifest's own bundle digest
(`SHA256(attestations/MANIFEST.sha256)`):

```
4ca9c1cd4a9387aae42a0d38d53ea6d7cebfd2961ef64733a75b1bfe322aa60e
```

## The public mirror stack — a quorum check anyone can run against public chain state

Everything above (`verify.py`, `verify_deployment.py`, the five files under
`attestations/`) establishes reproducibility. It does not, by itself, let a
reader confirm that the on-chain passport attestation this project actually
uses reflects those five records rather than something else — that requires
reading live contract state and treating it with the same skepticism a
client would, not taking this README's word for it. A second, fully
self-consistent contract stack now exists on Base Sepolia for exactly that:
deployed from a key with no relationship to this project's operational
deployment, carrying byte-identical bytecode and the same `vk.key` for both
circuits, so the four **batch** attestations resolve against it the same way
they resolve against the deployment this project actually uses. The fifth
record, `005`, covers solo and has not been filed on-chain at all — see "A
signed file and an on-chain record are different things" below.

**Two circuits are registered against this project's one model, and the
check gives them opposite answers on the same deployment, with the same
client logic:**

| | Batch (`batchK8`) | Solo |
|---|---|---|
| Verifier | `0x886b1baceB0552B2A4159663879b2841F3d81739` (same address as "Two identifiers" above) | `0x6D282dB5FE9833A6b5f995C5645188f2e4286e43` |
| `vkHashFile` | `0xdd03fb0c69e96cc02cbcc6bed8ef51665f934c01cddaf2a855bd1c7fce94675f` | `0x13cff0426abe00c941934bdd6bb7757f2e703fb9f6862bf08a783eeca08b4ff2` |
| `tier1Count` | **3** (`001`, `002`, `003` — all `pp-repro-v2`) | **0** — see "A signed file and an on-chain record are different things" directly below |
| `avgScore` | 100 | 0 |
| `bytecodeBindingVerified` | true | true — **see the trap below before reading this as partial credit** |
| Tier-2 (`pp-bytecode-v1`) | 1 (`004`, nsgoods) | 0 |
| `allowed` (quorum policy: ≥1 verified tier-1 record, avg score ≥51) | **true** | **false** |

Values above are from a live run on **2026-09-14**, after `005` was verified and
committed. The batch row restates what "Independent Reproductions" above already
says, now confirmed against a second, independently-deployed stack rather than
only the deployment this repo's own scripts point at.

#### A signed file and an on-chain record are different things

The solo row says `tier1Count = 0`, and that is still the correct output as of
this run — but the sentence this README previously attached to it, "nobody has
ever reproduced the solo circuit's `vk.key`," is **no longer true and has been
removed.** Someone has: `attestations/005-nsgoods-2026-09-13.json`, signed,
verified by execution on this side, digests matching `verify.py`'s expected solo
values exactly.

What `tier1Count = 0` reports is a narrower and still-accurate fact: **no
tier-1 record for solo has been filed on-chain.** The script resolves a
`requestHash` per (attester, tag, circuit) triple against the validation
registry; for solo, all three attesters come back `not_resolved_onchain` under
both tags. Nothing has been written to the registry for solo, so there is
nothing for the script to fetch, verify, or count. Filing is a separate act from
signing, performed by a different party (the registrar), and it has not
happened yet for `005`.

So the two statements that are both true right now:

- **Off-chain:** solo has one signed, independently verified tier-1
  reproduction, and one further unsigned one. The evidence exists and anyone can
  check it from `attestations/` plus the signer's own published copy.
- **On-chain:** solo has zero tier-1 records, `avgScore` 0, and `allowed` is
  `false`. A client running the quorum policy against the mirror today would
  still decline solo.

Neither figure is a stand-in for the other, and this README will not report the
signed file as though it moved the on-chain number. The solo row will change
when, and only when, a record is actually filed.

A page that reported only the batch row — or that quietly upgraded the solo row
because a signature now exists off-chain — would be exactly the kind of partial
claim this repo exists to correct.

### The `bytecodeBindingVerified` trap

`bytecodeBindingVerified` reads `true` for **both** circuits. Reading that
field on its own, a natural conclusion is that solo has *some* attestation
coverage — bytecode binding, even if nothing else. That conclusion is wrong,
and the reason is structural, not incidental: `bytecodeBindingVerified`
means only that the verifier's live deployed bytecode matches the
`vkHashBytecode` value written into that circuit's on-chain `CircuitRecord`
at `addCircuit` time. The party who writes that record is the registrar —
the same mirror key that deployed the whole stack — and a registrar can
satisfy this check for any circuit, attested or not, simply by deploying the
verifier it claims and registering the bytecode hash that verifier actually
produces. It requires no third party, no signature, no independent
observation. It is a self-consistency check on the registrar's own
bookkeeping, not a claim from anyone the registrar doesn't control.

`tier1Count` and the tier-2 attestation count are the numbers that actually
carry third-party weight, precisely because they can only reach a nonzero
value if someone *other than the registrar* signed a statement, published
it, and had that statement resolve against a `requestHash` the registrar
didn't get to choose the meaning of. `bytecodeBindingVerified=true` next to
`tier1Count=0` is not "partially attested" — it is "unattested, and the
registrar's own bookkeeping happens to be internally consistent," which is
true of every circuit a competent registrar deploys, attested or not.

### Running the check yourself

[`verify_onchain_quorum.py`](verify_onchain_quorum.py) performs the check
above end to end, for both circuits, against the public mirror stack over a
public RPC:

```bash
pip install web3==7.16.0 eth-abi eth-account eth-utils ecdsa requests
python3 verify_onchain_quorum.py
```

For each circuit it: reads `escrow.models()` and
`anchor.getCircuitByVerifier()` to get the on-chain `CircuitRecord`;
recomputes `bytecodeBindingVerified` from a live `eth_getCode` read (never
trusting the field name — it recomputes the hash itself); for every trusted
attester × tag pair, reconstructs the expected `requestHash` and checks
whether the registry actually resolves it; for every hash that resolves,
fetches the `responseURI` the registry stored and downloads that file;
verifies that file's own signature by its own construction (three different
schemes across the four batch records — see "Verifying a signed
attestation's proof" above); checks the verified document's claimed digest
against the circuit's on-chain values; and only then counts it. It prints
every intermediate value — every `requestHash`, every resolution outcome,
every recovered signer address, every content check — not just a final
pass/fail.

Unlike `verify_deployment.py`, every dependency here is pure-Python and
pip-installable — no local `anvil`/Foundry toolchain, nothing to compile.
Unlike `verify_deployment.py`'s `--vk-path` default, this script also needs
no weights, no ONNX file, and no `srs.bin` at all: it never runs
`compile_circuit`/`setup`, so its host-memory footprint is the ordinary
footprint of a script making HTTP requests, not the ~7–8 GB tier 1 needs.
Every network call it makes is against something genuinely public and needs
no credentials: the Base Sepolia public RPC, wherever each registry
record's `responseURI` actually points (read live from the chain, not
hardcoded — currently raw GitHub content for all four batch records), and
one endpoint run by nsgoods themselves
(`https://x402.nsgoods.org/proof/index.json`) that the two nsgoods-signed
records' authority check needs — if that endpoint is ever down or altered,
the affected record's authority check fails closed, the same way a bad
signature would, rather than silently passing.

### What this establishes, and what it does not

The chain this whole repo is about is **artifacts → `vk.key` → compiled
verifier → deployed bytecode**. Every reproduction in this README — `001`
through `004`, and everything `verify_onchain_quorum.py` checks — establishes
*correspondence along that chain*: that the bytes at each link really do
derive from the bytes at the link before it, independently confirmed by
parties who didn't have to trust this repo's own tooling to reach that
conclusion. It establishes nothing about whether the model weights
themselves are what anyone claims they are — model weights are the input to
the *first* link, upstream of everything this bundle can check, and no
outside party can verify that upstream fact for a closed-weight model from
artifacts alone. "This `vk.key` really does come from this ONNX file" and
"this ONNX file really is the model its owner says it is" are different
claims; this repo, and the quorum check above, only ever make the first one.

Kept separate for the same reason: a proof-gated settlement (the design this
circuit belongs to) makes payment and provable output availability *one*
atomic state transition — the buyer cannot end up paying without the
provable output existing, and vice versa, because both happen in the same
transaction. Whether the buyer actually receives a *usable* output before
that settlement is a different property, established (in the larger design)
by optimistic delivery ahead of settlement, not by the proof-gate itself.
Neither property substitutes for the other, and nothing in this repo or in
the quorum check above establishes the optimistic-delivery half — that
mechanism lives in the private project this bundle was extracted from.

### The public mirror stack itself

The addresses below are a **public mirror** of this project's contracts —
deployed from a key generated solely for this purpose, which has never sent
or received a transaction involving any address in this project's
operational deployment. This project's operational deployment exists,
predates the mirror, and is **not published here** — deliberately, not as an
oversight or a lesser-status omission. `PassportAnchorV2.escrow` is a public
immutable, and `addCircuit` requires the registered verifier to match the
escrow's own verifier; calling the operational anchor's own public getters
would hand any reader the operational escrow, registry, and verifier
addresses, and from a contract address alone its creation transaction
reveals the deploying key, whose transaction history reveals every other
contract that key has ever touched. A contract's public state cannot be
caveated into staying private after the fact — the only fix is a second
stack signed by a key that has never touched the operational one, not a
disclaimer added to the first.

This works because the four attestations are signed over digests of
`vk.key` and of deployed bytecode, never over a specific deployment address
— any instance carrying byte-identical bytecode and the same `vk.key`
satisfies them equally, which is exactly what makes the mirror a legitimate
target for the same check rather than a weaker substitute for one.

| Contract | Address |
|---|---|
| `PassportAnchorV2` (anchor) | `0xD0B577776A239E3eE3b39373f2380E366c3a987f` |
| `MockValidationRegistry` (registry) | `0x5421E241668AA5e2Bc6Da2c5642Fa9bFc8A5d996` |
| `ZkInferenceEscrowV2` (escrow) | `0x27e4DfA9e435a463A947e4eD8f74d8aB86F2F4CF` |
| Solo `Halo2Verifier` | `0x6D282dB5FE9833A6b5f995C5645188f2e4286e43` |
| Batch `Halo2Verifier` | `0x886b1baceB0552B2A4159663879b2841F3d81739` (same address published in "Two identifiers" above) |
| `modelId` | `0x06ef1c26ba4f218306433064fb65a8d0fbaffab707fb224505f0e256e23f2e8d` |

All on Base Sepolia, chainId `84532`. Only the addresses `verify_onchain_quorum.py`
actually needs are published here — nothing from the operational deployment
appears anywhere in this repo.

### Solo — published, and now independently reproduced

If you've already run the batch reproduction bundle (`verify.py`), solo is
close to free by comparison. The batch `srs.bin` in this repo is
67,109,124 bytes; the solo circuit's own `srs.bin` is 8,388,868 bytes —
about 8× smaller, with proportionally smaller `setup()` memory and time
(measured across three hosts: ≈1.8–14.5s wall-clock, ≈0.96–1.55 GB peak RSS —
see "Cost: three measured hosts, one `vk.key`" above). Solo's artifacts are
published in `solo/` — see "Solo bundle" above for the files, digests, and
`verify.py --circuit solo`.

**It took less than a day.** The bundle was published on 2026-09-13 with zero
third-party reproductions of any kind. Two arrived within a day, on different
architectures, by different paths:

- an Apple Silicon host, Python 3.13.6, ≈3.13s and ≈1.37 GB peak RSS — reported
  unsigned;
- a 2-core x86 cloud VM, Python 3.13.15, which dropped its network namespace
  (`unshare -n`) for the compute and derived the digest **three ways** — the
  reproducer's own driver, a manual re-hash, and this repo's
  `verify.py --circuit solo`, the last of these only after their own driver had
  already produced the value — ≈14.5s and ≈957 MB peak RSS, signed as
  [`attestations/005-nsgoods-2026-09-13.json`](attestations/005-nsgoods-2026-09-13.json).

The ordering in the second one matters: the independent driver produced
`13cff042…4ff2` *before* this repo's script was ever run, so the agreement is
not an artifact of running the maintainer's code and trusting its output. The
network namespace was dropped during compute, so nothing was fetched mid-run.

**What the pair establishes that a count of signatures would not.** Both runs,
and this repo's own, land on a `vk.key` of exactly **157,511 bytes** with
identical `sha256` and `keccak256`, while wall-clock differs by roughly **6×**
and peak RSS by about **400 MB**. Two signatures from one architecture would
have established that two parties ran the same steps. Two reproductions across
two architectures, two interpreter patch versions, and a 400 MB spread in memory
pressure establish something harder: that the digest does not depend on the
machine. That is determinism demonstrated, not asserted — and it is why the
memory figure quoted anywhere in this README is presented as a measured range
with its hosts named rather than as a requirement.

**Tier 2 for solo remains at zero,** and nothing above changes that. So does the
on-chain count: `005` is a signed file, not a filed record — see "A signed file
and an on-chain record are different things" above for why
`verify_onchain_quorum.py` still reports `tier1Count = 0` for solo, and what
would change it.

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

## What changed — 2026-09-13

The solo circuit's reproduction bundle is now published, alongside the
existing batch one, in `solo/` — see "Solo bundle" above. It was rebuilt
from scratch for this release from the parent project's own
`run_t3_k5_nonces` artifacts (`ezkl.compile_circuit()` + `ezkl.setup()` in a
clean temp directory) and its `vk.key` digests were computed from that
reproduction, not quoted — both match what the public mirror stack has
carried as the solo circuit's `vkHashFile` since that stack existed.

`verify.py` is now parameterized (`--circuit {batch,solo}`, default
`batch`) instead of duplicated per circuit; its existing no-argument
behavior is unchanged. `verify_onchain_quorum.py` needed no code changes —
it already checks both circuits generically from on-chain state, for every
prior release — this release only re-ran it live to confirm the solo path
resolves genuinely rather than defaulting to zero (see "Solo — published, and
now independently reproduced" above).

Also added: a note correcting the `scheme`/`signingScheme` wording in
`attestations/003` and `attestations/004` (see "Verifying a signed
attestation's proof" above). The attestation files themselves are
unedited — the correction lives in the signer's own manifest and is now
cross-referenced here.

## What changed — 2026-09-14

**The solo circuit is no longer unreproduced.** Within a day of its bundle being
published, two independent tier-1 reproductions arrived. The signed one is now
committed as `attestations/005-nsgoods-2026-09-13.json`, byte-identical to the
bytes published at
`https://x402.nsgoods.org/proof/reproductions/005-nsgoods-2026-09-13.json`,
since its own signature covers exactly those bytes.

**What was checked before accepting it.** Both digests against `verify.py`'s own
expected solo values (not against README prose) — match. The signature, by
canonicalizing the `payload` sub-object per RFC 8785, applying the EIP-191
prefix with the decimal-ASCII length, and recovering the signer — recovers
`0x57fF0F084Cba33e6761503f90eEF0Da9F159350c`, matching `signed_by`; two
whole-file readings were tested and recover different addresses. The signer's
authorization, separately, against the published manifest (`generated_at` at
fetch time: `2026-09-13T18:05:09.428930+00:00`). The references `005` cites — it
names no commit hash; `verify.py --circuit solo` exists, and the solo
`vkHashFile` it cites is what a live on-chain read returns. Details in "`005`'s
`scheme` string is accurate" above.

**`005`'s `scheme` string is accurate, unlike `004`'s.** `004`'s named the whole
file as the canonicalization target, a reading that is circular and was
corrected in the signer's manifest rather than by re-signing. `005` names the
`payload` sub-object explicitly, states the length encoding, and is correct as
written. Reported here both ways, as it should be.

**Cross-host determinism, which is the stronger result.** The two reproductions
ran on different architectures by different paths and produced a byte-identical
157,511-byte `vk.key`: Apple Silicon / Python 3.13.6 at ≈3.13s and ≈1.37 GB
peak, and a 2-core x86 cloud VM / Python 3.13.15 at ≈14.5s and ≈957 MB peak,
network namespace dropped during compute, digest derived three ways with this
repo's `verify.py` touched last. Roughly 6× apart in wall-clock and about 400 MB
apart in peak memory, identical in output. Every solo memory and timing figure
in this README is now presented as a measured range with its hosts named, since
the previous single figure was host-specific — see "Cost: three measured hosts,
one `vk.key`" above.

**The on-chain count did not move, and is not reported as though it did.** A
live run of `verify_onchain_quorum.py` on 2026-09-14 still returns
`tier1Count = 0`, `avgScore = 0`, `allowed = false` for solo: all three
attesters resolve `not_resolved_onchain` under both tags. `005` is a signed
file; filing a record on-chain is a separate act by the registrar and has not
happened. Batch is unchanged at `tier1Count = 3`, `avgScore = 100`,
`allowed = true`, with one tier-2 record.

**`attestations/` now has an integrity file — a new one.** No manifest covered
that directory before this change, unlike the batch and solo bundles;
`attestations/MANIFEST.sha256` was created here rather than updated, pinning all
five records. Like the other two manifests it is a convenience pointer, not the
integrity mechanism — the signatures inside the files are that.

**The Docker path stays open.** Both reproductions were native, so neither
exercised the container. See "Docker verification status" above for what would
close it: wall-clock and peak *container* memory for each circuit, plus
confirmation that each run lands on its canonical digest. One of the `005`
reproducers has offered to run it on a throwaway host.

## Scope

This bundle only proves circuit-provenance reproducibility (same
inputs → same VK). It is not the full escrow contract, not the proving
pipeline benchmarks, and not the passport/attestation contract code — those
live in the private project this was extracted from.
