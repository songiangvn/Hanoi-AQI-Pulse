# Deployment Notes

The grading rubric says the live demo should be deployed on shinyapps.io, so shinyapps.io is the primary deployment target.

## Primary Deployment: shinyapps.io

Official app target:

```text
shinyapps.io
```

Account/name used for deployment:

```text
giangnguyenson
```

Deploy the `dashboard/` directory, not the whole repository. The app is now self-contained for this:

- `dashboard/app.py` loads processed data from `dashboard/processed/`.
- `dashboard/requirements.txt` sits beside `app.py`, so rsconnect-python includes it in the deployment bundle.
- `dashboard/.python-version` requests Python `3.11`.
- `dashboard/models/` contains cached `.joblib` model artifacts.
- `dashboard/aqicn_api_key.md` is a local, uncommitted secret file included only in the deployment bundle so AQICN realtime data works on shinyapps.io.

## One-Time shinyapps.io Setup

Install rsconnect-python in the environment you use for deployment:

```bash
pip install rsconnect-python
```

In shinyapps.io:

```text
Account menu -> Tokens -> Show
```

Copy the generated command. It will look like:

```bash
rsconnect add --account <ACCOUNT> --name <NAME> --token <TOKEN> --secret <SECRET>
```

Run that command locally once.

## Deploy / Redeploy to shinyapps.io

From the repository root:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI
dashboard/.venv/bin/rsconnect deploy shiny --name giangnguyenson --title hanoi-aqi-pulse \
  --exclude "processed/hanoi_district_hourly.parquet" \
  --exclude "processed/model_features.parquet" \
  --exclude "processed/preprocess.log" \
  --exclude "task.md" \
  --exclude "walkthrough.md" \
  --exclude "tests" \
  dashboard dashboard/aqicn_api_key.md
```

For later code updates, commit your changes as usual, then run the same deploy command again:

```bash
dashboard/.venv/bin/rsconnect deploy shiny --name giangnguyenson --title hanoi-aqi-pulse \
  --exclude "processed/hanoi_district_hourly.parquet" \
  --exclude "processed/model_features.parquet" \
  --exclude "processed/preprocess.log" \
  --exclude "task.md" \
  --exclude "walkthrough.md" \
  --exclude "tests" \
  dashboard dashboard/aqicn_api_key.md
```

## Realtime Token Note

The app reads `AQICN_TOKEN` locally, but shinyapps.io does not support environment variable management through rsconnect-python. To make realtime AQICN work on shinyapps.io, keep a local file at:

```text
dashboard/aqicn_api_key.md
```

Include it explicitly in the deploy command as shown above. Do not commit `aqicn_api_key.md`, `.env`, or `.env.*`.

## 24/7 Realtime History Crawler With Hugging Face Dataset

shinyapps.io can pause or restart the app process when nobody is connected, so runtime collection inside Shiny is not guaranteed to run 24/7. To collect realtime AQI history on the department server before the demo, run the standalone crawler job:

1. Create a Hugging Face user access token with write permission for datasets.
2. Save it locally. Do not commit this file:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI
printf "hf_your_token_here" > hf_token.txt
chmod 600 hf_token.txt
```

3. Make sure the project venv has the HF upload dependency:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI
dashboard/.venv/bin/pip install -r dashboard/requirements.txt
```

4. Submit the crawler:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI
sbatch run_slurm_realtime_crawler.sh
```

The current SLURM script requests the `gpus` partition because that is the accepted long-running partition on the department cluster:

```text
#SBATCH --partition=gpus
```

The job uses the project virtualenv:

```text
dashboard/.venv/bin/python
```

and writes:

```text
dashboard/runtime/realtime_history.csv
```

It also uploads the same CSV to this public Hugging Face Dataset:

```text
https://huggingface.co/datasets/MountainRiver/hanoi-aqi-realtime-history
```

The deployed Shiny app reads:

```text
https://huggingface.co/datasets/MountainRiver/hanoi-aqi-realtime-history/resolve/main/realtime_history.csv
```

After the app has been redeployed once with this HF-reading code, future crawler updates do not require a redeploy.

In production, the Shiny session does not auto-call AQICN/Open-Meteo. This avoids a stuck busy overlay on shinyapps.io. The department-server crawler is the realtime source of truth, and the app reads the latest Hugging Face CSV when a session starts or the page is refreshed. For local debugging only, set `ENABLE_SESSION_NETWORK_REFRESH=1` before launching the app.

To run one manual collection for testing:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI/dashboard
.venv/bin/python scripts/collect_realtime_history.py --once --create-hf-repo
```

If you only want to test local CSV writing without uploading to Hugging Face:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI/dashboard
.venv/bin/python scripts/collect_realtime_history.py --once --no-hf-upload
```

Redeploy the app once after the HF integration code changes:

```bash
dashboard/.venv/bin/rsconnect deploy shiny --name giangnguyenson --title hanoi-aqi-pulse \
  --exclude "processed/hanoi_district_hourly.parquet" \
  --exclude "processed/model_features.parquet" \
  --exclude "processed/preprocess.log" \
  --exclude "task.md" \
  --exclude "walkthrough.md" \
  --exclude "tests" \
  dashboard dashboard/aqicn_api_key.md
```

## Hugging Face Backup

The app is also deployed as a Hugging Face Space:

```text
https://huggingface.co/spaces/MountainRiver/hanoi-aqi-pulse
```

This is useful as a backup/demo link, but the rubric specifically asks for shinyapps.io.

HF details:

- SDK: Docker
- Runtime port: `7860`
- Deploy branch: local `hf-space` pushed to remote `main`

To redeploy HF after code updates:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI
git switch hf-space
git cherry-pick main
git push hf hf-space:main --force
git switch main
```

The `hf-space` branch has `.gitattributes` so `.png`, `.joblib`, and `.parquet` files go through Git LFS.

## Useful References

- shinyapps.io Python deployment docs: https://docs.posit.co/shinyapps.io/guide/getting_started/
- rsconnect-python deploy docs: https://docs.posit.co/rsconnect-python/commands/deploy/
