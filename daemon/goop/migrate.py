"""Config migrations, so a later Goop release can rename or add settings without breaking the config file an earlier release wrote.
Every config carries `config_version`. `migrate(cfg)` brings an older one up to CURRENT step by step and reports what it did; a config from a NEWER Goop is left
exactly as it is (an older Goop must never rewrite settings it does not understand). config.load() applies this in memory every time; `settings.py migrate` writes the result."""
CURRENT = 1


def _v0_to_v1(cfg):
    """The first versioned config. Nothing to rename yet: it only gets its stamp."""
    return []


# version N -> the function that turns an N config into an N+1 config; each returns a list of human-readable notes
STEPS = {0: _v0_to_v1}


def version_of(cfg):
    v = cfg.get("config_version", 0)
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def migrate(cfg):
    """-> (config, notes). Never raises; a config that is already current or newer comes back unchanged with no notes."""
    cfg, notes, v = dict(cfg), [], version_of(cfg)
    if v >= CURRENT:
        return cfg, notes
    while v < CURRENT:
        notes += STEPS[v](cfg)
        v += 1
        cfg["config_version"] = v
    return cfg, notes
