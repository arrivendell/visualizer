from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from datetime import datetime
from requests.exceptions import ConnectionError


class MetricsService():

    def __init__(self, db_name, error_metric_name):
        self.client = None
        self.db_name = db_name
        self.error_metric_name = error_metric_name
        self.connectivity_errors = []
        self.host = None
        self.port = None
        self.is_udp = None

    def init_connection(self, host: str, port: int, use_udp: bool, clear_data: bool):
        """
        Basic setup of the connection, if use_udp is not set to true, the metrics
        will be sent synchronously with a risk of blocking the execution if the call
        to the metric service is too slow. Using udp prevents checking if the variables
        have been correctly written by influxDB.
        """
        self.host = host
        self.port = port
        self.is_udp = use_udp

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
            "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "fields": {
                "value": value
            }
        }

    def _handle_connectivity_error(self):
        """
        Used in case of a connectivity issue, this will store a connectivity error metric
        and reattempt the connection initialization
        """
        self.connectivity_errors.append(self.format_single_value_metric(
            f"{self.error_metric_name}.connectivity_error", {}, 1))

        print("Impossible to reach the metric service. "
              "Dropping metrics but preparing connectivity error metric, reattempting connection")
        try:
            self.init_connection(self.host, self.port, self.is_udp, False)
        except ConnectionError as ce:
            print(
                "Attempt to reconnect failed, will reattempt next time a metric is sent")
        else:
            print("Attempt to reconnect Succeeded")

    def send_batch_metrics(self, metrics: list):
        """
        Attempt to send several metrics to the metric services. If the udp mode is not set,
        a failure writing metrics or connecting to the service will be handled by sending
        error metrics as soon as the service is available again. Attempt to reconnect will
        be done.
        """
        try:
            self.client.write_points(metrics + self.connectivity_errors)
        except InfluxDBClientError as ie:
            # We specify again the database switch in case we're back from an connection outtage,
            # as we are not guaranted to have a connection reinitialization before running this
            # piece of code
            self.client.switch_database(self.db_name)
            print(
                f"Impossible to send one of the data points, sending failure metric. Error is {ie}")
            self.client.write_points([self.format_single_value_metric(
                f"{self.error_metric_name}.batch_sending_error", {}, 1)])
        except ConnectionError as ce:
            self._handle_connectivity_error()
        else:
            # If everything went well, clear the connectivity error cache
            self.connectivity_errors = []
