# KB-Studio

## About

KB-Studio is a desktop application for working with OSTIS knowledge bases. It
combines a project file browser, an SCs-code editor with syntax parsing and
highlighting, and an AI chat assistant in one interface.

The editor works with `.scs` files, the text representation of SC-code. The AI
assistant can answer questions about OSTIS and SCs-code and can use files
explicitly attached by the user as request context. AI providers and models
are configured in the application.

## Build on Linux

Build the application on the target operating system and architecture. The
current PyInstaller spec creates a single-file executable:

```bash
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --noconfirm KB-Studio.spec
```

The executable is written to `dist/KB-Studio`. Run it with:

```bash
./dist/KB-Studio
```

## Linux compatibility

Linux compatibility depends on the executable architecture, the system
libraries that remain external to the PyInstaller bundle, and the GNU C
Library (glibc) version required by the executable and bundled native
libraries.

Inspect the executable architecture and ELF interpreter:

```bash
file dist/KB-Studio
```

Inspect glibc symbol-version requirements visible in the executable:

```bash
readelf --version-info dist/KB-Studio \
  | grep -o 'GLIBC_[0-9.]*' \
  | sort -Vu
```

The highest `GLIBC_x.y` value shown is the highest glibc symbol version
referenced by that ELF file. This is a useful initial check, but it does not
prove that the complete PyInstaller application runs on a distribution:
PyInstaller bundles Python, Qt, and other native libraries, each of which may
have its own system-library requirements. `ldd dist/KB-Studio` only reports
the executable's direct dynamic dependencies and does not fully audit every
library packed inside a one-file bundle.

For the broadest compatibility with glibc-based distributions, build on the
oldest Linux distribution you intend to support, then test the generated
executable on that distribution and on the other target distributions. Test
the actual application, including its GUI, bundled resources, and file
operations. A build made on a newer distribution is not guaranteed to run on
older ones.

Build and test separately for each target operating system and architecture.
A Linux executable is not a Windows or macOS build.
