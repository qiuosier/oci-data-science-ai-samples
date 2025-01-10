import json
from garden.jobs import JobLogKeeper


log_keeper = JobLogKeeper()


METRIC_MAPPINGS = {
    "Loss": ["loss", "eval_loss"],
    "Accuracy": ["accuracy", "eval_accuracy"],
    "GPU0 Memory Used (GB)": ["used"],
}


def get_log_metrics_names(ocid):
    logs = log_keeper.get(ocid).get("logs")
    is_aqua_ft = any(["aqua_fine_tune.cli train" in log for log in logs])
    if is_aqua_ft:
        return list(METRIC_MAPPINGS.keys())
    return []


def get_log_metrics(ocid):
    logs = log_keeper.get(ocid).get("logs")
    is_aqua_ft = any(["aqua_fine_tune.cli train" in log for log in logs])
    if not is_aqua_ft:
        return {}
    data = []
    for log in logs:
        if "{" not in log or "}" not in log:
            continue
        if "epoch" not in log:
            continue
        try:
            payload = str(log)[str(log).find("{") : str(log).rfind("}") + 1].replace(
                "'", '"'
            )
            data.append(json.loads(payload))
        except Exception:
            continue

    metrics = {}
    keys = ["loss", "eval_loss", "accuracy", "eval_accuracy", "used"]
    for line in data:
        epoch = line.get("epoch")
        epoch_metrics = metrics.get(epoch, {})
        for key in keys:
            if key not in line:
                continue
            val = line.get(key)
            epoch_metrics[key] = val
        metrics[epoch] = epoch_metrics

    print(json.dumps(metrics, indent=2))
    return metrics


def get_log_metric(ocid: str, name: str):
    # Get all the metrics from the logs
    metrics = get_log_metrics(ocid)
    data = []
    # Filter the metrics
    for epoch, metric in metrics.items():
        values = {k: v for k, v in metric.items() if k in METRIC_MAPPINGS[name]}
        # Skip the data point if there is no matching metric
        if not values:
            continue
        data.append((epoch, values))
    x = []
    y = []
    if data:
        sorted(data, key=lambda x: x[0])
        x = [p[0] for p in data]
        labels = data[0][1].keys()
        y = []
        for label in labels:
            y.append({"label": label, "data": [p[1].get(label) for p in data]})
    return x, y
