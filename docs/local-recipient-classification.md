# Local Recipient Classification

The local Ollama pass is intentionally last in the classification sequence. It
only handles recipients still unresolved after deterministic rules and IRS NTEE
data, and it never overwrites a record tagged by either higher-confidence pass.
The preparation step also adds an index on `grants(grantee_name)` so the model
can attach one representative location and purpose context to each 500-row batch
without scanning the full grants table repeatedly.

1. Apply the additive schema and provenance migration. This does not call Ollama:

   ```bash
   python3 -m src.local_recipient_classification --prepare
   ```

2. Run the read-only validation harness against existing precise rule/NTEE
   classifications. It must show at least 90% major-category agreement and no
   major category with F1 below 85% before a full pass is approved:

   ```bash
   python3 -m src.validate_classifier --sample-size 1000
   ```

3. Review the confusion matrix, especially Jewish-to-Christian errors and
   Catholic-versus-Evangelical confusion. Tune the prompt or model if required.

4. Start the resumable local pass only after validation succeeds:

   ```bash
   python3 -m src.local_recipient_classification
   ```

SQLite is the restart source of truth: committed recipients leave the pending
query automatically. `data/classification_checkpoint.json` is a bounded,
atomic journal for only the most recently committed batch, preventing the old
full-history JSON map from consuming memory or increasing write latency.
