# ScannerRoom

## Doc rules

- documentation inside md files will be written in english
- documentation inside code will be written in english

## Front-end structure (`src/`)

- `app/`: entry point, root component and router; wires features together, holds no feature logic
- `features/<name>/`: one folder per product area (`landing`, `explore`, `transect`, `ingest`, `account`), flat, holding its views, components and scene code; imports inside a feature are relative
- `shared/`: what several features use: the API client (`api.ts`), the site catalog (`sites.ts`, `sites.json`) and the design system (`assets/`)
- code used by a single feature lives in that feature; move it to `shared/` only once a second feature needs it

## Transect pipeline rules

- improvements to reconstruction / export must be generic: they must benefit every future transect, never patch one specific transect
- no per-transect parameters, thresholds or hardcoded tweaks; derive values from the data itself (e.g. relative to median depth, seconds of video)
- data processing belongs in the export script (`playground/scripts/export-web.py`); the viewer only renders
- validate a change on at least two transects and check it does not regress the others

## Commit rules

- add the US name and number in each commit message

## Ressources

- [Brand identity](./docs/brand.md)
- [Application specifications](./docs/specs.md)
