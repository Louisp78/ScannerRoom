# ScannerRoom

## Doc rules

- documentation inside md files will be written in english
- documentation inside code will be written in english

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
