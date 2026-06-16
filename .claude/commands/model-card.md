---
description: Create or update a model card for a trained model
argument-hint: <track>/<model>   e.g. irrigation/lstm
---
Create or update the model card for **$ARGUMENTS** at `docs/models/$ARGUMENTS.md`.

Use the template at `docs/models/_template.md`. Fill every section from the
actual experiment: training data + window, intended use, the baseline it beats
and by how much (pull metrics from MLflow), evaluation protocol (walk-forward /
held-out split), limitations, and ethical/operational caveats (e.g. "do not use
to override grower judgment on frost nights").

If a number isn't available yet, write "TBD — pending run", never invent it.
Link the card from `docs/models/index.md`.
