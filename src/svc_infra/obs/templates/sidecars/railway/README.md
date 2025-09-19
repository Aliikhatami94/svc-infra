Set Railway Variables:
APP_HOST=<your-app>.up.railway.app
METRICS_PATH=/metrics
GRAFANA_CLOUD_PROM_URL=https://<stack>.grafana.net/api/prom/push
GRAFANA_CLOUD_PROM_USERNAME=<stack_id>
GRAFANA_CLOUD_TOKEN=<metrics_write_token>

# NEW: optional scrape interval (default 5s)
SCRAPE_INTERVAL=30s
