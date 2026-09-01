# Pinned by content digest (not the mutable "3.11-slim" tag) so the base
# image can't drift out from under this commit if the tag is repointed.
FROM --platform=linux/amd64 python:3.11-slim@sha256:d1053354624536b044162aaab1e418bd000ea35184fb1ae098ab3166b1072e72

# linux/amd64 is required: ezkl==23.0.5 ships a manylinux2014_x86_64 wheel on
# PyPI but no linux/aarch64 wheel for this version, so a native build on an
# Apple Silicon Docker host must force the platform (Docker will emulate).

# Pinned toolchain — see README "Reproduce" for why exact-version pinning matters:
# different ezkl versions can produce different VKs from identical circuit inputs.
RUN pip install --no-cache-dir \
    ezkl==23.0.5 \
    eth-utils==6.0.0 \
    pycryptodome==3.20.0

WORKDIR /repro
COPY model_k8.onnx model_k8.onnx.data settings.json input.json srs.bin verify.py ./

CMD ["python3", "verify.py"]
