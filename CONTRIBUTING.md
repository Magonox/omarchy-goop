# Contributing

Thanks for helping. The short version:

1. Fork the repo and make a branch.
2. Make one change per pull request, and say why in the description.
3. Run the tests: `python3 -I -m unittest discover -s daemon/tests` (no GPU, audio or network needed).
4. Open a pull request against `main`.

`main` is protected: every change arrives as a pull request, the tests must pass, and the maintainer reads the diff before merging.

Changes that touch `setup.sh`, `bin/goop-install-pagereader`, `browser/pagereader/`, the 3D code sandbox (`daemon/goop/explainer/codegen.py`), or anything that sends data off the machine get a closer look. Please explain them clearly.

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for the dev loop.
