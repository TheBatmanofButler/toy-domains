# Old cube model (reference for tests only)

`old_puzzle.py` and `old_features.py` are copies of the earlier cube run's cube model and surface-reader
features, kept so the tests can check the new code against them as a second opinion. They are not used by
`cube_ladder/` and are not to be changed. The only edit is in `old_features.py`, whose import line
`from .puzzle import ...` became `from old_puzzle import ...` so the two files work outside their old package.
