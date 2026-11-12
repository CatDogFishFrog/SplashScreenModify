# CI and releases

Everything is defined in `.github/workflows/ci.yml`.

## What runs when

| Event                          | What happens                                                                                   |
|--------------------------------|------------------------------------------------------------------------------------------------|
| Push to any branch, pull request from a fork | Tests on Windows with Python 3.12 and 3.14, then the PyInstaller build, a smoke test of the exe and the artifact upload |
| Push of a `v*` tag             | The same, then a GitHub release with the exe, its SHA-256 file and generated notes              |

The smoke test starts the built exe with empty input and checks that it prints its version, lists the modules and
exits cleanly. It catches a broken bundle that the unit tests cannot see.

## Latest build without logging in

Every successful run uploads the `SplashScreenModify` artifact. [nightly.link](https://nightly.link/) turns it
into a stable public link:

```
https://nightly.link/CatDogFishFrog/SplashScreenModify/workflows/ci/main/SplashScreenModify.zip
```

Replace `main` with another branch name to get that branch's build. The link always serves the newest run that
**succeeded**, so a commit with failing tests never replaces the previous build. GitHub keeps artifacts for 90 days.

nightly.link finds the artifact by the workflow file name and the artifact name, so keep `ci.yml` and
`SplashScreenModify` as they are. Installing the [nightly.link GitHub app](https://github.com/apps/nightly-link)
on the repository is optional; it only keeps the downloads out of the shared API rate limit.

The newest release is always available at
`https://github.com/CatDogFishFrog/SplashScreenModify/releases/latest/download/SplashScreenModify.exe`.

## Making a release

1. Tag the commit on `main` and push the tag:
   ```
   git tag v1.2.0
   git push origin v1.2.0
   ```
   CI takes the version number from the tag, injects it into the built executable automatically, and creates
   the GitHub release. No manual version bump is needed in the source code.
2. A tag containing a hyphen (`v1.2.0-rc.1`) is published as a pre-release.

The notes list `feat`, `perf` and `fix` commits since the previous tag; see [COMMITS.md](COMMITS.md).
If a release contains only internal changes, the notes say so. The text can still be edited on GitHub afterwards.

To check a download, compare `Get-FileHash SplashScreenModify.exe` with the `.sha256` file from the release.
