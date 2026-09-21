# Tiny Unity Fixture (SYNTHETIC structure, NOT a real Unity build)

`TinyGame_Data/` mimics a Unity player layout just enough for **detection**:
a `*_Data` dir, a `globalgamemanagers` file starting with the real
`UnityFS` magic (+ version marker), and a stub `.assets` file.

What this fixture proves and does NOT prove:

* PROVES: detection (structure + magic + version sniff), the missing-UnityPy
  error path, walker/normalizer/write-back logic (via duck-typed fakes in
  tests), patch mirroring.
* DOES NOT prove: parsing real UnityFS binaries (that is UnityPy's job;
  real-game E2E stays UNVERIFIED until a redistributable game is available).
