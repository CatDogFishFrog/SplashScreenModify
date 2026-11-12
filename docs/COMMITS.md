# Commit messages

Release notes are generated from commit messages (git-cliff, see `cliff.toml`), so a commit subject is what users
read in the release. Write it for them.

## Format

```
type(scope): what changed for the user
```

- `scope` is optional. Use a name a user recognizes: `jetbrains`, `unity`, `android-studio`, `cli`.
- Describe the visible result, not the implementation. No trailing period, no emoji, no issue numbers.
- Capitalization does not matter: the changelog capitalizes the first letter itself.

| Type                                         | In the release notes          |
|----------------------------------------------|-------------------------------|
| `feat`                                       | Added                         |
| `perf`                                       | Improved                      |
| `fix`                                        | Fixed                         |
| `feat!`, `fix!` (any type with `!`)          | Breaking changes, listed first |
| `refactor`, `docs`, `style`, `test`, `build`, `ci`, `chore` | not shown       |

Whatever the type, the scopes `ci`, `build`, `deps`, `docs`, `test`, `tests` and `release` are never shown.
A commit that does not follow the format is also left out, which is fine for internal changes.

## Several changes in one commit

Every body line that is itself a conventional commit becomes a separate entry. Other body text is ignored.

```
feat(unity): support the splash screen of Unity 6.3

fix(unity): keep the backup when the splash is replaced twice
fix: accept image paths wrapped in quotes
```

## Examples

| Good                                                  | Why not                                               |
|-------------------------------------------------------|-------------------------------------------------------|
| `fix(jetbrains): detect IDEs installed through Toolbox` | `fix: refactor registry lookup` (says nothing to a user) |
| `feat(unity): support Unity 6.3`                      | `feat: new stuff` (too vague)                          |
| `feat!: drop support for Python 3.11`                 | `fix: Fixed bug. (#42)` (noise: period, number)       |
