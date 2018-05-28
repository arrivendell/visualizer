import argparse
import os
import sys
import subprocess
import time
from datetime import datetime
from requests.exceptions import ConnectionError
from sensor_runner.metrics_service import MetricsService

MAX_CONNECTION_RETRIES = 20

# Assumptions on the name of metrics from the sensor
SINE_NAME = "sensor.cpu_load"
RANDOM_NAME = "sensor.bounded_random_generator"
COUNTER_NAME = "sensor.generated_metrics_number"
ERROR_METRIC_NAME = "sensor.error"

INFLUXDB_DB_NAME = "sensor"


def cast_metric(metric_value, cast_function, metric_name, tags):
    """
    This tries to apply <cast_function> to the metric_value and handle potential errors
    :return: The metric formatted to influxdb format if the cast worked or an error metric
    if the cast failed.
    """
    try:
        casted_metric_value = cast_function(metric_value)
        return metric_service.format_single_value_metric(metric_name, tags, casted_metric_value)
    except ValueError:
        print(f"Cannot cast {metric_name} with value {metric_value}")
        return metric_service.format_single_value_metric(f"{ERROR_METRIC_NAME}.{metric_name}", {}, 1)


def get_common_preprocess_tags(list_variables):
    """
    Return a set of tags to apply to the metrics sent from :list_variables:, after
    checking the content of :list_variables:
    """
    is_ok = any([float(var) != 0 for var in list_variables])
    return {"is_valid_preprocess": is_ok}


def run(path_executable: str, metric_service: MetricsService, environment: str):
    """
    Read values from a program output, interpret the 3 first values of this output as known metrics
    and send these metrics to the metric_service
    """
    #### BUG PATCH# ###
    while True:
        previous_vars = ['', '', '']
        #####

        # We open the executable as a subprocess in order to catch its ouput
        process = subprocess.Popen(
            path_executable, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

        for line in iter(process.stdout.readline, b''):
            list_variables = line.decode(
                sys.stdout.encoding).rstrip().split(' ')
            #### BUG PATCH# ###
            if previous_vars == list_variables:
                break
            previous_vars = list_variables
            ####
            time_now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            print(time_now, list_variables)

            try:
                common_pre_processing_tags = get_common_preprocess_tags(
                    list_variables)
            except ValueError as e:
                print("Cannot preprocess the output of the executable")
                common_pre_processing_tags = {}

            common_tags = {"env": environment, **common_pre_processing_tags}

            formatted_metrics = []
            #TODO The following code could be wrapped using a config file containing a list
            # of dataset with information on the metrics (its position, name and cast function)
            formatted_metrics.append(cast_metric(
                list_variables[0], lambda x: float(x), SINE_NAME, common_tags))
            formatted_metrics.append(cast_metric(
                list_variables[1], lambda x: int(x), RANDOM_NAME, common_tags))
            formatted_metrics.append(cast_metric(
                list_variables[2], lambda x: int(x), COUNTER_NAME, common_tags))

            metric_service.send_batch_metrics(formatted_metrics)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--path-executable', default="./sensor", type=str,
                        help="Path of the executable to run (the sensor)")
    parser.add_argument('--host', type=str, default=os.environ.get('HOST_METRICS'),
                        help="Name of the host to which metrics will be sent")
    parser.add_argument('--port', type=int, default=os.environ.get('PORT_METRICS'),
                        help="Port number to which metrics will be sent")
    parser.add_argument('--env', type=str, default=os.environ.get('ENV'),
                        help="current environment")
    parser.add_argument('--use-udp', dest='use_udp', action='store_true',
                        help="Set a flag to use UDP instead of TCP connections to the metric service")
    parser.add_argument('--clear-data', dest='clear_data', action='store_true',
                        help="Set the flag to force a clear of metrics before inserting the new ones.")
    parsed = parser.parse_args()

    metric_service = MetricsService(INFLUXDB_DB_NAME, ERROR_METRIC_NAME)

    retries = MAX_CONNECTION_RETRIES
    # We need to be able to handle the case where the metric service would not be ready
    while retries > 0:
        try:
            metric_service.init_connection(
                parsed.host, parsed.port, parsed.use_udp, parsed.clear_data)
            break
        except ConnectionError:
            retries-=1
            time.sleep(1)
            print(f"Connection attempt to metric service failed, retrying {retries} times")
    run(parsed.path_executable, metric_service, parsed.env)
