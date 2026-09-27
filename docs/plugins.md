# Plug-ins

Domain rules that don't fit in a config file plug in as Python code. Point
`export.validators` at one or more `RecordValidator`s, each written as
`module:attribute`:

```yaml title="config.yaml"
export:
  destination: out/planets.csv
  key_column: planet_name
  value_columns: [orbital_period_days, mass_jupiter, radius_jupiter]
  validators:
    - planet_rules:NamedPlanets
    - planet_rules:short_period_planets
```

With `planet_rules.py` saved beside `config.yaml`:

```python title="planet_rules.py"
from sci_etl_core.processors import NumericRangeValidator, RecordValidator, ValidationResult, Violation


class NamedPlanets(RecordValidator):
    def is_valid(self, record):
        return self.validate(record).ok

    def validate(self, record):
        name = str(record.get("planet_name") or "")
        if name.strip().isdigit() or not name.strip():
            violation = Violation(code="unnamed", field="planet_name", severity="error", message=f"{name!r} is not a planet name")
            return ValidationResult(violations=(violation,))
        return ValidationResult()


def short_period_planets():
    return NumericRangeValidator({"orbital_period_days": (0.0, 10.0)})
```

- **Where modules are found.** A module or package beside `config.yaml` is
  loaded from its file, so it works without being installed. The folder is
  never added to Python's import path, so a file there cannot replace a module
  that other code imports, and a plug-in named like a standard-library module,
  such as `csv.py`, is rejected. Any other name is imported as an installed
  package.
- **Plug-ins run code.** Loading a plug-in runs its module, so only run configs
  and project folders you trust.
- **Classes or factories.** The attribute is called with no arguments, so it
  can be a class or a function that builds the object. The result must be a
  `RecordValidator`.
- **What they do.** Validators see every extracted entity before it is
  exported. An entity any validator rejects is dropped, and the log names the
  entity and every reason, for example
  `Entity rejected by validation: 'KELT-9 b' (orbital_period_days is 40, outside [0, 10])`.
  A validator that implements only `is_valid` is reported as
  `Rejected by <ClassName>`; implement `validate` too, as `NamedPlanets` does,
  to say why.
- **Catching mistakes early.** `sci-etl validate` imports and builds every
  plug-in, and `run` does so before any network request, so a broken plug-in
  exits with code 3 without spending tokens.

The base classes and the bundled validators are documented in the
[sci-etl-core processors reference](https://xueromll.github.io/sci-etl-core/latest/reference/processors/).
