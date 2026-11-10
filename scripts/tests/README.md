# Python tests

Run the whole suite from the repository root, with `jus_files` checked out
(`git submodule update --init`; tests that read ROM-derived files skip without it):

```bash
source "$HOME/.venvs/jus-re/bin/activate"   # a venv; see requirements.txt
python -m pip install -r scripts/tests/requirements.txt
python -B -m unittest discover -s scripts/tests
```

One file: `cd scripts/tests && python -B -m unittest test_anim_timing`.

A clean run ends `OK (skipped=N)` and leaves `git status` clean. The suite
needs only the standard library plus the packages in `requirements.txt`
(numpy, jsonschema, Pillow). If one is missing, the tests that need it skip,
and a `SKIP <file>: needs <package> (not installed; ...)` line goes to stderr.
Install the package and rerun to get those tests back. Skips for a missing
ROM, `jus_files`, or `node` come from the tests themselves (`-v` lists reasons).

The `selftest OK`, `fresh`/`stale`, and `FAIL:` style lines some tests print
come from the tools under test. Judge the run by the unittest summary line.

## Writing tests

- A test that needs numpy, jsonschema or Pillow guards itself with `_deps.py`:
  `_deps.require("PIL")` at the top of a file, or `@_deps.needs("PIL")` on a
  class or method. Do not let a missing package fail an import.
- A test must not write inside the tracked tree. Send tool output (PNGs, CSVs)
  to a `tempfile` directory.
