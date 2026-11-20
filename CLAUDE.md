# ScannerRoom

## Doc rules

- do not put file paths or precise implementation details (file, function or variable names) in comments or docs: describe intent and rules, the code says where things are; otherwise every code move also forces doc edits
- documentation inside md files will be written in english
- documentation inside code will be written in english

## Front-end structure

- the front end is split into the app shell (entry, root component, routing), one folder per product feature, and shared code
- the app shell only wires features together; it holds no feature logic
- code used by a single feature lives in that feature; it moves to shared only once a second feature needs it
- shared UI (design system, common components) lives in shared, never inside a feature
- Vue single-file components are ordered template, then script, then style (enforced by the linter)

## Transect pipeline rules

- improvements to reconstruction / export must be generic: they must benefit every future transect, never patch one specific transect
- no per-transect parameters, thresholds or hardcoded tweaks; derive values from the data itself (e.g. relative to median depth, seconds of video)
- data processing belongs in the pipeline's web export; the viewer only renders
- validate a change on at least two transects and check it does not regress the others

## Commit rules

- add the US name and number in each commit message

## Ressources

- [Brand identity](./docs/brand.md)
- [Application specifications](./docs/specs.md)
