# Almurrib — Unity Full-Stack Phase 3 E2E
## Mission: Turn Unity from Extract/Translate into Select Game → Localize → Patch/Overlay → Launch

You are the lead architect, Unity localization engineer, reverse-engineering/tool-integration engineer, QA engineer, performance engineer, UI engineer, and release engineer for **Almurrib (المعرب)**.

This is a **Unity-only Phase 3 milestone**. Do not start Unreal/RPG Maker/VN engines until this Unity milestone is genuinely stable.

The current Unity implementation has:
- working detection for Unity
- useful extraction for some TextAsset/MonoBehaviour layouts
- real extraction success on games such as Hollow Knight
- incomplete write-back
- no complete AssetBundle `.ab` write-back
- limited coverage of Unity Localization/TMP/UI/Addressables
- difficult old Mono/DLL cases
- difficult IL2CPP cases
- Unity Arabic runtime/font/RTL challenges

The goal is:

> **User selects a Unity game folder → Almurrib detects and analyzes it → creates a safe working copy → discovers text sources → extracts → applies glossary/context → translates → runs Arabic QA → patches/rebuilds or prepares a runtime overlay → validates → produces a ready-to-run localized copy.**

Normal users should not need to hunt through assets, bundles, helper scripts, or output folders.

---

# 1. HARD PRODUCT RULE

Keep the game's base/original locale as English whenever possible.

The desired model is:

```text
Game base = English
        ↓
Almurrib patch/overlay
        ↓
Player sees Arabic
```

Do not assume the game must officially add an Arabic locale.

The `ar` locale used in the Ren'Py Phase 2 visual test was a test mechanism, not the universal product architecture.

---

# 2. SAFETY

Never overwrite the original game by default.

Use:

```text
Original game
    ↓
Read-only analysis
    ↓
Working copy
    ↓
Localized build
```

Before writing:
- verify disk space
- create backup/manifest
- preserve original hashes where practical
- record modified files
- support rollback

Patching the original game must require explicit user confirmation.

---

# 3. FULL REPOSITORY RECONNAISSANCE

Inspect the entire current repository first:

```text
src/
tests/
fixtures/
docs/
tools/
gui/
providers/
storage/
engine_adapters/
arabic/
scripts/
```

and root files such as:

```text
pyproject.toml
README.md
THIRD_PARTY_NOTICES.md
build_exe.py
*.spec
```

Understand and reuse:
- core/domain
- pipeline/workflow
- cache/TM
- provenance
- glossary
- QA
- Arabic processing
- overlay
- GUI
- CLI
- current Unity implementation
- packaging

Do not create a second Unity architecture.

---

# 4. CURRENT GITHUB / COMMUNITY RESEARCH — REQUIRED

Before integrating tools, research current GitHub repositories/releases/docs in English and, where useful, Chinese.

Search themes:

```text
Unity game localization extraction
Unity 游戏 汉化
Unity 资源 文本 提取
UnityPy localization
AssetsTools.NET text extraction
UABEA localization
Unity AssetBundle localization
Unity Localization package extraction
TextMeshPro localization
BepInEx Unity translation
XUnity AutoTranslator
Unity IL2CPP localization
Cpp2IL strings
Unity AssetBundle rebuild
Unity Arabic localization
```

For every candidate record:

```text
name
repository
status
latest useful release/commit
license
purpose
platform
build requirements
CLI/API availability
maintenance quality
integration method
reason for acceptance/rejection
```

Decide whether each should be:
- integrated dependency
- external tool/subprocess
- optional tool
- dev/reference only
- rejected

Do not download random repositories just to claim breadth.

---

# 5. REQUIRED ARSENAL TO AUDIT

At minimum evaluate:

```text
K0lb3/UnityPy
nesrak1/UABEA
nesrak1/AssetsTools.NET
SamboyCoding/Cpp2IL
BepInEx/BepInEx
bbepis/XUnity.AutoTranslator
xSh4r103/AnyFontUnity
```

Also discover mature Chinese/international Unity localization projects that solve gaps.

Integrate only what has a clear engineering purpose.

---

# 6. LICENSE SAFETY

For every integration:
- verify actual license
- preserve attribution
- record version/commit/source
- update THIRD_PARTY_NOTICES.md

Never copy code from an unlicensed/unknown-license repository.

Do not vendor source unless legally and technically justified.

---

# 7. UNITY DETECTION

Build a structured detector that determines where possible:

```text
Unity version
Mono vs IL2CPP
architecture
managed assemblies
StreamingAssets
Resources
AssetBundles
Addressables
Unity Localization package
TextMeshPro
legacy Unity UI Text
BepInEx already present
other localization frameworks
```

Return structured evidence and capabilities.

Do not claim support just because "Unity" was detected.

---

# 8. CAPABILITY-DRIVEN UNITY SUPPORT

Represent capabilities such as:

```text
TEXT_ASSET
MONOBEHAVIOUR
UNITY_UI_TEXT
TEXTMESHPRO
UNITY_LOCALIZATION
ADDRESSABLES
ASSET_BUNDLE
SERIALIZED_ASSET
MONO_ASSEMBLY_STRINGS
IL2CPP_ANALYSIS
RUNTIME_HOOK
FONT_OVERRIDE
```

Each detected game should receive a capability profile:

```text
Automatic
Supported with warning
Experimental
Unsupported
```

---

# 9. TEXT DISCOVERY — EXPAND BEYOND CURRENT SUPPORT

The current implementation handles some TextAssets and MonoBehaviour fields. Expand it to cover, where safely possible:

## A. TextAsset
Extract + write back.

## B. MonoBehaviour serialized fields
Extract strings while preserving unrelated fields.

## C. Unity UI Text
Discover visible text stored in UI components.

## D. TextMeshPro
Support TMP text fields/components.

## E. Unity Localization package
Investigate and support:
- string tables
- table collections
- locale data
- stable localization keys

## F. Addressables
Detect localization/content accessed through Addressables.

## G. AssetBundles
Make `.ab` read/write support a first-class goal:
- inspect
- extract
- modify
- rebuild
- validate
- replace only inside working copy

Do not generate corrupt bundles.

---

# 10. STRING CANDIDATE CLASSIFICATION

Do not translate every string blindly.

Classify candidates as:

```text
Likely translatable
Possibly translatable
Technical / leave unchanged
```

Usually do not auto-translate:
- GUIDs
- file paths
- URLs
- class names
- shader names
- assembly names
- JSON keys
- internal IDs
- debug identifiers

Potentially translate:
- dialogue
- UI labels
- descriptions
- item names
- quests
- tutorials
- character names
- localization table values

Make classification explainable.

---

# 11. STABLE SOURCE REFERENCES

Every Unity entry must preserve write-back information:

```text
game_id
asset_file
bundle
asset_type
object/path ID
component/field
localization key
source hash
```

The system must be able to answer:

> where did this string come from?

and:

> exactly where does its Arabic replacement go?

Avoid relying only on list position.

---

# 12. WRITE-BACK IS THE MAIN REQUIREMENT

Extraction alone is not success.

For every supported source type:

```text
extract
→ translate
→ modify
→ serialize
→ rebuild
→ reparse
→ verify
```

Preserve unrelated data.

Test round-trips:

```text
original
→ parse
→ change one string
→ write
→ parse again
→ verify non-target data
```

---

# 13. ASSETBUNDLE `.ab` WRITE-BACK

Treat this as high priority.

Desired flow:

```text
Game
→ discover bundle
→ inspect
→ extract
→ modify selected assets
→ rebuild bundle
→ validate bundle
→ place rebuilt bundle in working copy
```

Do not overwrite source bundles.

Support common compression/layout variants where actually proven.

For unsupported variants, provide a precise diagnostic instead of corrupting the file.

---

# 14. MONO / DLL TEXT

For old Unity Mono games:

```text
Unity Mono
→ detect assemblies
→ inspect managed resources/string candidates
→ extract where safe
```

Do not pretend UnityPy handles all DLL-resident text.

If safe static write-back is not possible:

```text
Extraction: Supported
Write-back: Unsupported
Runtime override: Supported/Unsupported
```

Document the actual state.

Never corrupt assemblies.

---

# 15. IL2CPP

Investigate and integrate `Cpp2IL` where it materially helps.

Goal:

```text
IL2CPP
→ detect
→ analyze metadata/native structures
→ find candidate text
→ expose extractable strings
```

Do not patch native binaries blindly.

Prefer runtime interception or safe data-level patching when appropriate.

Clearly separate:
- extraction
- static write-back
- runtime support

---

# 16. BepInEx / RUNTIME OVERLAY

For games where static patching is insufficient, implement a runtime strategy.

Evaluate:

```text
BepInEx
XUnity.AutoTranslator
```

and relevant mature Unity localization projects discovered during research.

Target behavior:

```text
Game starts
→ text appears
→ Almurrib identifies source
→ local Arabic lookup
→ Arabic displayed
→ original English remains safe internally
```

Fallback must always be safe:

```text
No translation
→ original English displayed
```

No crash.

---

# 17. FONT / TMP / RTL

Reuse the existing Almurrib Arabic layer.

Unity-specific code should only provide the engine-specific bridge.

Investigate:
- AnyFontUnity
- TextMeshPro font assets
- BepInEx font/runtime strategies
- current TMP Arabic limitations

Support where possible:
- project-local Arabic font
- glyph coverage checks
- font asset generation/selection
- fallback
- RTL handling
- Arabic line wrapping integration

Do not install fonts globally by default.

---

# 18. UNITY ARABIC E2E FIXTURE

Create small Unity fixtures containing:

```text
مرحبا بالعالم
مرحبا OpenAI
السعر 123 جنيه
{name} مرحبا
long Arabic text
Arabic punctuation
mixed Arabic/Latin
emoji
URL
```

Verify where supported:
- glyph connection
- RTL
- numbers
- mixed scripts
- wrapping
- missing-glyph detection
- no crashes

Only label real runtime rendering as verified if actually observed.

---

# 19. TRANSLATION PIPELINE INTEGRATION

All Unity localization must reuse:

```text
Detect
→ Extract
→ Normalize
→ Glossary
→ TranslationContext
→ Provider
→ Placeholder QA
→ Arabic QA
→ Canonical persistence
→ Unity write-back/runtime mapping
```

Do not create a Unity-only translator.

---

# 20. GLOSSARY / CONTEXT

Preserve:
- speaker if available
- scene/context
- asset/object
- localization key

Reuse the existing Glossary and TranslationContext.

Do not duplicate glossary logic in Unity.

---

# 21. CACHE / TM / PROVENANCE

Unity entries must participate in:
- project scope
- engine scope
- source hashes
- glossary revision
- provider/model provenance
- QA state
- static/runtime strategy

No cross-game contamination.

---

# 22. ONE-CLICK HIGH-LEVEL SERVICE

Create a unified operation conceptually like:

```text
localize_unity_game(game_folder, options)
```

The actual API is your choice.

It must be capable of:

```text
1. detect
2. analyze
3. prepare safe workspace
4. extract
5. translate
6. QA
7. choose patch/runtime strategy
8. prepare Arabic resources
9. write back / build patch
10. reparse/validate
11. create localized copy
12. generate report/manifest
13. offer launch
```

Both CLI and GUI must use shared application services.

---

# 23. PATCH MANIFEST / ROLLBACK

Every build must record:

```text
original game identity
working copy
Unity version
adapter version
modified assets
modified bundles
translation count
QA result
font resources
runtime components
tool versions
build timestamp
rollback location
```

Support rollback and verify it restores baseline hashes for tested cases.

---

# 24. GUI — UNITY SHOULD FEEL ONE-CLICK

Main UI should be close to:

```text
Game Folder: [ Browse / Drop ]

Detected:
Unity 2021.3.x
IL2CPP
Capabilities:
✓ TextAsset
✓ TMP
✓ AssetBundles
✓ Static patch
✓ Runtime overlay

Language: Arabic
Provider: Local / Cloud
Glossary: Default

[ Localize Game ]
```

Progress:

```text
Detecting Unity...
Analyzing assets...
Found 4,092 candidate strings
Applying glossary...
Translating...
QA...
Patching...
Validating...
Creating localized copy...
Done
[ Launch Game ]
```

Hide low-level details in Advanced/Diagnostics.

---

# 25. FAILURE DIAGNOSTICS

For any string that did not translate, show:

```text
Source
Location
Extraction method
Glossary match
Provider result
QA state
Write-back state
```

Example:

```text
Source: Alex
Location: asset X / object Y / field Z
Extraction: TextMeshPro
Glossary: no match
Translation: unchanged
QA: suspicious Latin
Write-back: skipped
```

No mystery failures.

---

# 26. TOOL MANAGER

Create a registry for external/optional Unity tools:

```text
UnityPy
UABEA
AssetsTools.NET
Cpp2IL
BepInEx
XUnity.AutoTranslator
...
```

Track:

```text
installed
version
compatible
license acknowledged
required by current game
```

If automatic acquisition is implemented:
- use a trusted official/repository source
- record exact version/hash where practical
- do not silently download arbitrary binaries
- never expose credentials

---

# 27. COMPATIBILITY MATRIX

Build actual tested support across relevant Unity eras.

Do not assume ranges.

For each tested version/backend report:

```text
Detected
Extracted
Written back
Runtime
Arabic
E2E
```

---

# 28. LEGAL TEST MATERIAL

Use only:
- synthetic fixtures
- open-source demos
- redistributable projects
- user's own installed games for local testing

A proprietary game may be used as a local manual test when the user owns it, but do not redistribute its files or commit them.

---

# 29. FULL UNITY E2E CONTRACT

For any game marked "supported":

```text
Game folder
→ Detect
→ Analyze
→ Working copy
→ Extract
→ Persist
→ Translate
→ QA
→ Write-back / runtime map
→ Reparse
→ Launch
→ Observe Arabic
→ Exit
→ Rollback verification
```

If only extraction works:

```text
Extraction-only support
```

Do not call it fully supported.

---

# 30. ADVERSARIAL TESTING

Attack:
- corrupted assets
- unsupported versions
- missing typetrees
- compressed bundles
- duplicate IDs
- duplicate localization keys
- huge projects
- malformed Unicode
- placeholders
- markup
- missing fonts
- TMP edge cases
- interrupted patch
- read-only directory
- low disk simulation where practical
- spaces/Arabic paths
- repeated localization
- changed source hashes
- game updates

For every real bug:

```text
reproduce
→ regression test
→ fix
→ targeted tests
→ full suite
```

---

# 31. PERFORMANCE

Benchmark realistic workloads:

```text
1k assets
10k assets
50k assets
100k where practical
```

Measure:
- detection
- discovery
- extraction
- candidate classification
- glossary
- QA
- DB
- write-back
- bundle rebuild
- runtime lookup

Avoid loading entire projects into memory unnecessarily.

Use streaming/chunking where practical.

---

# 32. REFACTOR AFTER INTEGRATION

This is mandatory.

After Unity features work, stop and refactor the entire project again.

Look for:
- duplicate asset readers
- duplicate path handling
- scattered Unity version checks
- provider logic leaking into adapters
- duplicate Arabic processing
- temporary scripts
- dead code
- hard-coded paths
- weak interfaces
- prototype code left in production

Consolidate and rerun the full suite.

---

# 33. CLI

Support a coherent Unity workflow while preserving old commands:

```text
almurrib unity detect <game>
almurrib unity inspect <game>
almurrib unity extract <game>
almurrib unity translate <project>
almurrib unity build <project>
almurrib unity patch <game>
almurrib unity run <project>
almurrib unity localize <game>
```

Exact syntax is your decision.

---

# 34. PACKAGING

Build:

```powershell
.\.venv\Scripts\python build_exe.py
```

Launch the EXE from a different working directory.

Verify:
- tools registry
- optional components
- fonts
- DB
- glossary
- providers
- runtime files
- manifests
- logs
- resources

No repository-relative assumptions.

---

# 35. DOCUMENTATION

Create/update:

```text
docs/UNITY.md
docs/UNITY_SUPPORT_MATRIX.md
docs/UNITY_TOOLS.md
docs/UNITY_E2E.md
docs/UNITY_RUNTIME.md
docs/UNITY_TROUBLESHOOTING.md
```

Document:
- detection
- version/backend support
- extraction sources
- write-back sources
- AssetBundles
- Localization package
- Addressables
- TMP
- Mono
- IL2CPP
- runtime
- fonts
- limitations
- tool versions
- licenses
- verification status

Use:

```text
VERIFIED
PARTIALLY VERIFIED
EXTRACTION ONLY
RUNTIME ONLY
EXPERIMENTAL
UNVERIFIED
UNSUPPORTED
```

---

# 36. UNITY SUPPORT MATRIX

Produce:

| Capability | Detection | Extraction | Write-back | Runtime | Arabic | E2E |
|---|---|---|---|---|---|---|
| TextAsset | | | | | | |
| MonoBehaviour | | | | | | |
| Unity UI Text | | | | | | |
| TextMeshPro | | | | | | |
| Unity Localization | | | | | | |
| Addressables | | | | | | |
| AssetBundle | | | | | | |
| Mono DLL | | | | | | |
| IL2CPP | | | | | | |
| BepInEx | | | | | | |

Fill it only from actual tests.

---

# 37. DEFINITION OF DONE

Unity is NOT done because extraction works.

It is done only when the actually supported subset has:
- structured detection
- capability discovery
- TextAsset write-back
- MonoBehaviour write-back
- UI Text support where proven
- TMP support where proven
- Unity Localization support where proven
- Addressables support where proven
- AssetBundle write-back where proven
- honest Mono DLL handling
- honest IL2CPP handling
- Cpp2IL path where useful
- BepInEx runtime path where proven
- XUnity AutoTranslator evaluated/integrated where justified
- Arabic font strategy
- shared Arabic layer
- shared Glossary
- shared QA
- project-scoped cache/TM/provenance
- working-copy/backup
- rollback
- patch manifest
- one-click GUI path
- CLI path
- E2E fixtures
- adversarial tests
- performance measurements
- EXE verification
- complete documentation
- no hidden critical/high defects

---

# 38. FINAL REPORT

Return exactly:

## 1. Unity Architecture Before
## 2. Unity Architecture After
## 3. GitHub / Community Research
For every candidate:
- repo
- version/commit
- license
- purpose
- integration method
- result

## 4. Detection
## 5. Extraction Matrix
## 6. Write-back Matrix
## 7. AssetBundle
## 8. Mono / IL2CPP
## 9. Runtime / BepInEx
## 10. Arabic / TMP / Fonts
## 11. Glossary / QA / Translation Integration
## 12. GUI
## 13. CLI
## 14. Backup / Rollback
## 15. E2E Tests
## 16. Bugs Found
For each:
- reproduction
- root cause
- fix
- regression

## 17. Performance
## 18. Security
## 19. Licenses / Third-Party
## 20. Packaging
## 21. Documentation
## 22. Remaining Limitations
## 23. Unity Support Matrix
## 24. Final Verification Matrix

For every capability use:

```text
IMPLEMENTED
AUTOMATED VERIFIED
INTEGRATION VERIFIED
E2E VERIFIED
MANUALLY VERIFIED
EXPERIMENTAL
UNVERIFIED
UNSUPPORTED
```

---

# 39. ABSOLUTE RULES

1. Unity is the only Phase 3 engine in this milestone.
2. Do not stop at extraction.
3. Write-back is a first-class requirement.
4. Never destroy the original game by default.
5. Do not corrupt unsupported assets/binaries.
6. Do not fake IL2CPP support.
7. Do not fake AssetBundle support.
8. Do not fake runtime support.
9. Research current Chinese/international GitHub projects before integration.
10. Do not copy unlicensed code.
11. Prefer mature open-source building blocks.
12. Keep the Almurrib core authoritative.
13. Keep cloud optional.
14. Preserve secrets.
15. Add a regression test for every real bug.
16. Refactor after integration.
17. Run full E2E before declaring success.
18. Do not silently mark extraction-only as full support.
19. Do not auto-commit.
20. Be explicit about every unverified case.

# FINAL SUCCESS CONDITION

The intended experience is:

```text
USER CHOOSES UNITY GAME
        ↓
Automatic detection
        ↓
Game/version/backend analysis
        ↓
Safe working copy
        ↓
Discover text sources
        ↓
Extract
        ↓
Glossary + context
        ↓
Translate
        ↓
Arabic QA
        ↓
Arabic processing
        ↓
Static patch OR runtime overlay
        ↓
Rebuild/validate
        ↓
Localized game copy
        ↓
[ Launch Game ]
        ↓
PLAYER SEES ARABIC
```

Build the engineering needed to make this workflow real for the actually supported Unity subset, with honest diagnostics and verified E2E behavior.
