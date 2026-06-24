# FAQ

Answers to common questions, mostly for the
[Basic Manual](manual/from-archipelago-fork.md) path where you create the release
and attach the wheel by hand.

---

## How do I publish so Oliver sees both assets?

Oliver reacts to the moment a release is **published**. If you create a published
release first and upload the `.whl` afterwards, Oliver may look before the wheel is
attached and bail. So attach the assets **while the release is still a draft**,
then flip it to published.

In the GitHub UI: **Draft a new release → Save draft → upload the `.apworld` and
the `.whl` → Publish release**.

With the `gh` CLI, create the release as a draft with both assets, then publish:

```bash
# Create a draft and upload both assets in one step
gh release create <tag> \
  build/apworlds/<apworld>.apworld \
  worlds_<apworld>-<version>-py3-none-any.whl \
  --draft --title "<apworld> <version>"

# Flip the draft to published — this is the event Oliver acts on
gh release edit <tag> --draft=false
```

The tag can be anything; Oliver identifies your world from the attached
`<apworld>.apworld` asset, not from the tag.

---

## Can I skip Oliver and open the Index PR myself?

Yes. Oliver is a convenience — it records the wheel's location and SHA256 pin for
you. You can do the same by hand:

1. **Get the wheel's download URL.** After publishing, the asset has a public
   `browser_download_url` of the form
   `https://github.com/<you>/<repo>/releases/download/<tag>/worlds_<apworld>-<version>-py3-none-any.whl`.
   (`gh release view <tag> --json assets` lists it.)
2. **Compute the wheel's SHA256.**

    ```bash
    sha256sum worlds_<apworld>-<version>-py3-none-any.whl   # Linux
    shasum -a 256 worlds_<apworld>-<version>-py3-none-any.whl   # macOS
    ```

    On Windows PowerShell: `Get-FileHash worlds_<apworld>-<version>-py3-none-any.whl -Algorithm SHA256`.
3. **Build the `module_location`** by appending the hash as a PEP 503
   direct-reference fragment:

    ```
    https://github.com/<you>/<repo>/releases/download/<tag>/worlds_<apworld>-<version>-py3-none-any.whl#sha256=<hex>
    ```

4. **Add the manifest.** Create or edit `worlds/<apworld>.json` in the Index with
   your `game`, `world_version`, and the `module_location` above. See the
   [archipelago.json reference](reference/archipelago-json.md) for the fields.
5. **Open a PR** on `MultiworldGG-Index` with that change. Karen runs the same
   review checks she runs on Oliver's PRs, and a human CODEOWNER merges.

The `#sha256=<hex>` pin is what makes this safe: pip verifies the downloaded bytes
against it before executing any code. [More on why.](why-oliver.md)

---

## Do I have to use the `<apworld>-<version>` tag format?

Only on the automated paths, where the workflow parses the apworld and version
from the tag. On the [Basic Manual](manual/from-archipelago-fork.md) path you can
tag the release however you like — Oliver reads the world name from the attached
`<apworld>.apworld` asset.
