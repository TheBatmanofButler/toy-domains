# Earlier code (reference for tests only)

Copies of the earlier pilots' code, kept so that tests can check the new code against it and so that the
fixtures can be made again. They are not used by `tptp_count/` and are not to be changed.

- `fol/` (`terms.py`, `canon.py`, `engine.py`, `harvest.py`, `tptp.py`, `oracle.py`, `__init__.py`) and
  `label_h.py`: from the single-fact pilot, unchanged. `label_h.py` sets a default prover location of the pod
  it ran on; the fixture script sets its own.
- `pt/stage0.py`: the later pilot's reader with the fix for quantifier lists (`read_formulas_fixed`), unchanged.
- `make_fixtures.py`: the script that made `tests/fixtures/` (see the README there). When it runs the earlier
  harvest it hands it only the lines that code reads (clause lines of at most 220 characters, the first 1,501),
  instead of the whole printout, because some deriving runs print gigabytes.

sha256 of the copies: `fol/terms.py` 0028a774…, `fol/canon.py` 412c5c24…, `fol/engine.py` 153d7302…,
`fol/harvest.py` 18db105a…, `fol/tptp.py` f486808d…, `fol/oracle.py` ef896d59…, `label_h.py` a0ded077…,
`pt/stage0.py` 0b97cbfb… (the same as the originals).
