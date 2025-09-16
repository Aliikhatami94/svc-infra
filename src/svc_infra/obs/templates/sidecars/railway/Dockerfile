FROM grafana/agent:latest
COPY agent.yaml /etc/agent/agent.yaml
CMD ["/bin/grafana-agent","--config.file=/etc/agent/agent.yaml","--config.expand-env"]
