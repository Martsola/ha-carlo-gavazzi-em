# Changelog

## 1.0.0

- Clean repository rebuild replacing the earlier prototype history.
- Fixed the config-flow `400 Bad Request` caused by serializing a null unit into number selectors.
- Made package initialization independent of `pymodbus`, allowing Home Assistant to import and display the first config-flow form before any Modbus client is created.
- Added CI smoke tests that start the flow through Home Assistant’s real flow manager on Home Assistant 2026.2.3 and 2026.6.1.
- Added a retryable config-flow error path instead of aborting setup after a failed or empty discovery scan.
- Added automatic Modbus TCP versus RTU-over-TCP probing, three-pass slave discovery, and skip-on-found behaviour.
- Added one Home Assistant device per meter with serial number, model, model ID, and firmware device metadata.
- Added the complete documented read-only measurement and diagnostic register map.
- Added configurable polling, advanced communication settings, reconfiguration/rescan, options, diagnostics, HACS metadata, brand assets, and release automation.
