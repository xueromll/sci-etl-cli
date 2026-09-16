# Plug-ins

Domain rules that don't fit in a config file plug in as Python code. Point
`export.normalizer` at a `KeyNormalizer` and `export.validators` at one or more
`RecordValidator`s, each written as `module:attribute`:

```yaml title="config.yaml"
export:
  destination: out/planets.csv
  key_column: planet_name
  value_columns: [orbital_period_days, mass_jupiter, radius_jupiter]
  normalizer: planet_rules:DesignationNormalizer
  validators:
    - planet_rules:short_period_planets
```

With `planet_rules.py` saved beside `config.yaml`:

```python title="planet_rules.py"
from sci_etl_core.processors import DefaultKeyNormalizer, KeyNormalizer, NumericRangeValidator


class DesignationNormalizer(KeyNormalizer):
    def normalize(self, raw_value):
        key = DefaultKeyNormalizer().normalize(raw_value)
        return "wasp" + key[len("superwasp"):] if key.startswith("superwasp") else key


def short_period_planets():
    return NumericRangeValidator({"orbital_period_days": (0.0, 10.0)})
```

- **Where modules are found.** The config file's folder is searched first, so a
  module or package beside `config.yaml` works without being installed.
  Installed packages work too.
- **Classes or factories.** The attribute is called with no arguments, so it
  can be a class or a function that builds the object. The result must be a
  `KeyNormalizer` or a `RecordValidator`, as the key requires.
- **What they do.** The normalizer turns each `key_column` value into the key
  that decides which CSV rows are the same entity; here `SuperWASP-12 b` and
  `WASP-12 b` share one row. Validators see every extracted entity before it is
  exported, and an entity any validator rejects is dropped and logged.
- **Catching mistakes early.** `sci-etl validate` imports and builds every
  plug-in, and `run` does so before any network request, so a broken plug-in
  exits with code 3 without spending tokens.

The base classes and the bundled validators are documented in the
[sci-etl-core processors reference](https://xueromll.github.io/sci-etl-core/latest/reference/processors/).
