# Contributing

Issues and pull requests are welcome in English or Chinese.

For a bug report, include the revision, OS and tool versions, exact command,
expected result, and actual output. For device behavior, include the device,
Android version, and steps you ran. Remove credentials and private artifacts
from shared reports.

Keep each pull request focused. Explain the behavior changed and the checks
you ran. Update the English and Chinese guides when their instructions change.
Label generated fixtures, local checks, and real-device results separately.

## Local checks

From the repository root, use Python 3.11 or newer:

```sh
python -B -m unittest discover -s tools/adb-upgrade/tests -v
```

For WebRTC tooling changes, use Node.js 22 or newer:

```sh
cd tools/webrtc-preview
npm ci
npm test
```

Android builds, signed AAB fixtures, bundletool setup, and Flutter checks need
additional tools. Follow the commands and versions in
[Android delivery CI](.github/workflows/ci.yml) for the area you change.
Passing local tests does not establish camera, BLE, or device acceptance;
record those results only after running the linked device guides.
