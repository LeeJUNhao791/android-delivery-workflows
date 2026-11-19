# APK 16 KB Action consumer example

The [consumer workflow](../../.github/workflows/apk-16kb-action.yml) calls the
Android SDK Toolkit Action by a fixed commit SHA from this separate repository.
It runs on Ubuntu and Windows using synthetic APK/AAR archives. The fixtures
exercise the static checker and do not represent installable Android apps.

| Input | Expected step outcome | Checker result |
| --- | --- | --- |
| Aligned, compressed ARM64 ELF | success | `pass`, exit 0 |
| Misaligned ELF with AAR list | failure | `fail`, exit 1 |
| Invalid APK | failure | `invalid`, exit 2 |
| APK with no native libraries | success | `not_applicable`, exit 3 |

The failing case must show `single_candidate` for `libunique.so`,
`multiple_candidates` for `libshared.so`, and `unknown` for `libchanged.so`.
Only expected failure steps use `continue-on-error`. The next step asserts
their actual outcomes and all JSON outputs, so a broken or always-passing
Action fails the consumer workflow. JSON reports are retained as artifacts
and the Action writes a table for each invocation to the job summary.

After building your APK, use the same action reference and supply its path.
The optional AAR manifest should describe the runtime classpath Gradle
actually resolved for that variant. See the
[toolkit inputs and manifest format](https://github.com/LeeJUNhao791/android-sdk-toolkit#use-the-github-action).

```yaml
- uses: LeeJUNhao791/android-sdk-toolkit@f0e53894757a9c339f762f1f09a297b5718c4c1d
  with:
    apk: app/build/outputs/apk/release/app-release.apk
    aar-manifest: build/resolved-aars.json
```

An omitted AAR list requests alignment checks only. Candidate matching compares
library bytes within the supplied list, and can report several candidates or
an unknown origin. Runtime compatibility requires device testing.
