# Changelog

## 1.1.0

- Added EM24 (EM24DINAV) meter support with its own identification codes, full read-only register map, and signed 16-bit decoding.
- EM24 read blocks honour the 11-word protocol limit and skip the EM270/EM280 serial-number and secondary-address reads that EM24 does not provide.
- Replaced the non-renderable `progress_done` step with a "Discovery complete" summary form after the scan finishes, so the dialog shows the result and the flow can be submitted instead of leaking.
- Relaxed the pinned `pymodbus` requirement to `pymodbus>=3.11.2`.

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
