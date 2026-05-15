# Compatibility branches

This page explains how to test your world against multiple MultiworldGG
versions — for example, if you want to confirm you haven't broken
`0.5.x` users before releasing a version that targets `0.6.x`.

---

## Why you might need this

`archipelago.json` has two version guard fields:

- `minimum_ap_version` — MultiworldGG refuses to load your world below this
  version.
- `maximum_ap_version` — MultiworldGG refuses to load your world above this
  version (rarely needed).

These guards protect users at runtime but they don't help you during
development. If you make a change that accidentally breaks an older MultiworldGG
version, you'll only find out when a player reports it.

Compatibility CI jobs catch this before release.

---

## How the wheel build works without a MultiworldGG checkout

`build.yml@v3` (the wheel build) is pure setuptools — it does not need a
MultiworldGG checkout. It builds the wheel entirely from your
`worlds/<apworld>/` source tree. This means the wheel build itself is always
compatibility-neutral; the compat question is "does the wheel's code run
correctly when loaded by MultiworldGG version X?"

The answer is tested in a separate CI job that pip-installs your wheel into a
MultiworldGG checkout at the desired ref.

---

## Sample compatibility test job

Add this to your workflow file alongside `publish-wheel`:

```yaml
  test-compat:
    needs: publish-wheel
    runs-on: ubuntu-latest
    strategy:
      matrix:
        mwgg-ref: ["v0.5.1", "v0.6.0", "main"]
    steps:
      - uses: actions/checkout@v6
        with:
          repository: MultiworldGG/MultiworldGG
          ref: ${{ matrix.mwgg-ref }}
          path: mwgg

      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"

      - name: Install MultiworldGG deps
        run: pip install -r mwgg/requirements.txt

      - name: Install world wheel
        run: |
          pip install \
            "https://github.com/${{ github.repository }}/releases/download/${{ github.event.release.tag_name }}/<dist>-<version>-py3-none-any.whl"

      - name: Smoke-import world
        run: |
          cd mwgg
          python -c "import worlds.<apworld>; print('ok')"
```

Replace `<dist>`, `<version>`, and `<apworld>` with your values. The wheel URL
is the same URL that Oliver records in the Index manifest.

---

## Using `workflow_dispatch` for manual compat checks

You can trigger compat checks on demand without cutting a release by adding a
`workflow_dispatch` input:

```yaml
on:
  workflow_dispatch:
    inputs:
      mwgg-ref:
        description: "MultiworldGG ref to test against (tag, branch, or SHA)"
        required: true
        default: "main"
      world-version:
        description: "Release tag of the wheel to test (e.g. clique-1.2.0)"
        required: true
```

Then reference `${{ inputs.mwgg-ref }}` and `${{ inputs.world-version }}` in
the test steps.

---

## Runtime guards vs. CI compat jobs

These two mechanisms are complementary, not alternatives:

| Mechanism | When it fires | What it catches |
|---|---|---|
| `minimum_ap_version` in `archipelago.json` | At MultiworldGG load time, on the user's machine | User running a version that's too old for this world |
| CI compat job | During CI on your release branch | Your code breaking on an older MultiworldGG version |

Use `minimum_ap_version` to declare the oldest MultiworldGG your world
supports. Use CI compat jobs to verify that claim automatically.
