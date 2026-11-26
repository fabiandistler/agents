# Add structured logging to the exporter

The repository has no log format yet, so this introduces one: a JSON object
per line with `time` and `msg`, written to stdout.
