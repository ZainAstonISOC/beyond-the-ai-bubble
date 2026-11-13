# Beyond the AI Bubble: KMSI, KBRI and KCEI

Code and data pipeline for the Howden Research paper *Beyond the AI Bubble*. Every published index value can be rebuilt from public sources with:

```
python3 -m src.ingest.run_ingest      # fetch raw data, record URL/time/SHA-256 in data/raw/manifest.json
python3 -m src.validate.check_staged  # Phase 2 data checks -> reports/phase2_data_validation.md
```

Specification: `config/kmsi_v1.0.yaml` (frozen 13 Nov 2026). Changes after first results are released as new versions.

Yahoo Finance and AAII files are not redistributed here; the ingestion code downloads them and the manifest records the hashes of the copies used.

Research and educational use only. Not investment advice.
