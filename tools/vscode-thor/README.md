# THOR Syntax for VS Code

Local VS Code-compatible syntax highlighting for THOR `.thor` source files.
The extension contributes the `thor` language id and a TextMate grammar with the
`source.thor` scope.

## Local development

Open this folder in VS Code, then press F5 to launch an Extension Development
Host. Open one of the top-level files in `../examples/` to inspect highlighting.

No Node/npm dependencies are required for the repository's default pytest checks.

## Optional packaging smoke

If `vsce` is already installed, you can create and install a local VSIX package:

```sh
vsce package
code --install-extension thor-syntax-0.1.0.vsix
```

`vsce` and npm are optional tools for manual packaging only; they are not part of
default project validation.
