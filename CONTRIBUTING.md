# Contributing

Hardware test reports are especially valuable for this integration.

## Before opening an issue

- Enable debug logging for `custom_components.carlo_gavazzi_em` and `pymodbus`.
- Download Home Assistant diagnostics for the integration entry.
- Record the meter model, firmware shown on the device, gateway model, gateway framing mode, serial settings, and slave address.
- Remove private network information before posting logs or diagnostics.

## Development

```bash
python -m pip install -r requirements-dev.txt
ruff format .
ruff check .
python -m compileall custom_components/carlo_gavazzi_em
```

Keep the integration read-only unless a future change has a clear safety review and explicit user confirmation for every write or reset operation.
