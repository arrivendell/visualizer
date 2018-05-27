from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from datetime import datetime


class MetricsService():

    def __init__(self, db_name, error_metric_name):
        self.client = None
        self.db_name = db_name
        self.error_metric_name = error_metric_name

    def init_connection(self, host: str, port: int, use_udp: bool, clear_data: bool):
        """
        Basic setup of the connection, if use_udp is not set to true, the metrics
        will be sent synchronously with a risk of blocking the execution if the call
        to the metric service is too slow. Using udp prevents checking if the variables
        have been correctly written by influxDB.
        """
        print(
            f"Initializing connection to influxDB on {host}:{port}, with udp usage to {use_udp} and clear data to {clear_data}")
        if use_udp:
            self.client = InfluxDBClient(
                host=host, use_udp=True, udp_port=port)
        else:
            self.client = InfluxDBClient(host=host, port=port)
        if clear_data:
            self.client.drop_database(self.db_name)
        self.client.create_database(self.db_name)
        self.client.switch_database(self.db_name)

    def format_single_value_metric(self, metric_name: str, tags: dict, value):
        """
        Simply format to the influxdb metric formatting.
        """
        return {
            "measurement": metric_name,
            "tags": tags,
            "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "fields": {
                "value": value
            }
        }

    def send_batch_metrics(self, metrics: list):
        try:
            self.client.write_points(metrics)
        except InfluxDBClientError as ie:
            print(
                f"Impossible to send one of the data points, sending failure metric. Error is {ie}")
            self.client.write_points([self.format_single_value_metric(
                f"{self.error_metric_name}.batch_sending_error", {}, 1)])
