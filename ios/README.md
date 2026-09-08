# Ludora for iOS

A native SwiftUI client for the Ludora catalog: browse, filter, sort, search, game detail, and reviews.

Swift 6, SwiftUI, iOS 17+, no third-party dependencies.

## Getting it running

The app talks to the same backend the web frontend uses, so start that first:

```bash
make up        # Postgres
make backend   # FastAPI on :8000
```

Then, from the repo root:

```bash
make ios-test  # the package builds and tests with no Xcode at all
```

## Opening it in Xcode

The project already exists at `ios/Ludora/Ludora.xcodeproj`. Open it and press Run, with the backend up.

Two things about it are worth knowing, because both are easy to undo by accident.

**It uses a synchronized folder.** Xcode 16 projects can reference a directory rather than listing every file, so anything added under `ios/Ludora/Ludora/` joins the target automatically. There is no "drag the file into the project" step, and no `project.pbxproj` churn when a file is added or renamed.

**`LudoraKit` is wired in as a local package**, via an `XCLocalSwiftPackageReference` pointing at `../LudoraKit`. Xcode's own "Add Package Dependencies → Add Local" writes the same thing, so if the reference is ever lost, that menu item restores it.

### If you ever need to recreate the project

Xcode's App template wants to create a directory named after the product, so creating a project called `Ludora` inside `ios/` collides with the existing `ios/Ludora/` and Xcode offers to **move the existing folder to Trash**. Do not accept: that folder holds the app sources. Move `ios/Ludora/` aside first, create the project, then move the sources back into `ios/Ludora/Ludora/`.

Two template defaults also need correcting afterwards:

- **Deployment target.** Xcode 26 defaults to iOS 26.2, which excludes nearly every real device. Set it to **iOS 17.0**, which is what `LudoraKit` targets.
- **"Create Git repository on my Mac."** Leave it unchecked. This is a monorepo, and a nested `.git` inside `ios/Ludora/` makes git treat the app as an embedded repository.

## Layout

```
LudoraKit/     Swift package: models, API client, decoding tests. No UI.
Ludora/        SwiftUI app: views, thin over LudoraKit.
```

Everything worth testing lives in `LudoraKit`, which builds and tests from the command line without Xcode or a simulator. See [AGENTS.md](AGENTS.md) for why, and for what this client deliberately leaves out.

## Fixtures

The decoding tests run against real API responses captured from a running backend, not hand-written JSON:

```bash
make ios-fixtures   # re-capture, needs the backend running
make ios-test       # fails with the field named if a shape changed
```

That is the drift protection. Three clients now read one API contract and nothing type-checks Swift against Python, so refreshing fixtures is how a backend change surfaces here as a test failure rather than a blank screen.
