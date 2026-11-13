#!/usr/bin/env bash
set -euo pipefail
jar="${RUNNER_TEMP}/bundletool-all-1.18.1.jar"
curl --fail --silent --show-error --location --retry 3 \
  https://github.com/google/bundletool/releases/download/1.18.1/bundletool-all-1.18.1.jar -o "$jar"
printf '%s  %s\n' 675786493983787ffa11550bdb7c0715679a44e1643f3ff980a529e9c822595c "$jar" | sha256sum -c -
printf 'BUNDLETOOL_JAR=%s\n' "$jar" >> "$GITHUB_ENV"
