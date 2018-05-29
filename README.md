# Visualizer

# Overview:
This project aims to set up a structure for visualizing and alerting on metrics gathered from a sensor.

As the base for a good monitoring and alerting, it is highly appreciated to know what are the metrics we are interested in, and what they mean.
A value jumping from 0 to 10 in some seconds could be a good thing if we are measuring the number of visitors on our website, but would turn into a bad news if it actually monitors the number of critical errors in a small system.
To make sure we understand what this project monitors, we will define the behavior of the sensor:
- Every second, the sensor generates 3 values, one sine-like, one random integer and one counter.
- The first value, a sine-like value, output numbers usually between 5 and 10, in a sine-like shape. We will consider this as being the load of a 8 cores CPU on a server, which means that most of the metrics value show a server with a quite high load.
- The second value, a random number, seems to indeed show random numbers between 4 000 000 and 8 000 000. We will then consider that this random number is the value of a random generator supposed to create random numbers between 4 000 000 and 8 000 000
- The third value, a counter, is considered as a count of the number of time the sensor tried to output metrics. It should then always go up at a rate of 1 metric per second, a counter not increasing, decreasing or increasing too much would be a potential issue.
- Looking at the values of the sensor, it seems that we can see some outliers in the metrics, that could be a defect. As we don't want those known outliers to pollute our good metrics, we will tag such outliers (3 values to 0 at the same time) with a special tag so that we can keep track on how much this defect happens without it interfering with other values (See below under `Dashboard and Alarms/Other metrics`).

## Building and running the service:

Install docker and docker-compose last version (>=1.7.1)

Navigate to the root folder, and run:
  - `docker-compose build`
  - `docker-compose up ` (Adding -d for having it in the background)

Note that by the nature of the sensor, metrics could stay equal from 2 seconds after starting. Restart the sensor container to try another time if needed.
You can now login to http://localhost:3000/ enter admin/admin credentials and observe the dashboards under the Sensor monitoring dashboard

### Using another sensor:
 To use your custom sensor sending the same kind of metrics, replace the `sensor` executable in the ./sensor_runner folder.
Another solution is described below.

### Customize parameters running the sensor_runner not on a container:
You need python 3.6 to run the program
Install the visualizer package by typing `pip install -e .` in the root folder. Make sure your default pip is for python3 though, or use pip3

Run
- `docker-compose -f ./docker-compose-minimal.yaml build`
-  `docker-compose -f ./docker-compose-minimal.yaml up -d`

Then you can run `python run.py --host localhost --port 8086` with other options if needed (See below).

```
usage: run.py [-h] [--path-executable PATH_EXECUTABLE] [--host HOST]
              [--port PORT] [--env ENV] [--use-udp] [--clear-data]

optional arguments:
  -h, --help            show this help message and exit

--path-executable PATH_EXECUTABLE
                        Path of the executable to run (the sensor)
  --host HOST           Name of the host to which metrics will be sent
  --port PORT           Port number to which metrics will be sent
  --env ENV             current environment
  --use-udp             NON USABLE YET (Set a flag to use UDP instead of
                        TCP connections to the metric service)
  --clear-data          Set the flag to force a clear of metrics before
                        inserting the new ones.
```

## Architecture:

### The sensor runner
The sensor executable is run from a small python program, the "sensor runner", which reads its output values, for simplicity. Note that the choice of redirecting the output of the program in a log file and reading this file could have been more flexible as restarting a sensor wouldn't have required to restart the python program.

The sensor runner can be summarized in 4 steps:
- Getting the values from the output into 3 strings
- Pre-processing those values and preparing tags to define them (This is where the potential sensor defect is tagged)
- Naming and casting those values to their corresponding metric value
- Sending those metrics to a Metric Service.
The sensor runner will attempt to reconnect to the Metric Service if needed.

### Sending the metrics

The Metric Service chosen is InfluxDB, a time series database which allows us to send metrics that will directly be stored in a database. InfluxDB is well supported by Grafana, the visualization tool we will choose to display those metrics in dashboards.

While several ways of gathering metrics could have been chosen (Prometheus+Grafana, Datadog...), InfluxDB offered the possibility to easily and simply write any metrics at any time, in a push-mode, while Prometheus core functionality relies on polling (Even if some pushing is possible), and Datadog trivial usage for custom metrics uses an collector which aggregates metrics to limit calls to its API.
More possibilities are obviously to take into consideration for a bigger and different project, but the scope of the project and its characteristics prove InfluxDB to be a good fit.

### Global schema
![alt text](https://i.imgur.com/Av78SQW.png)

Dashboards have then been created in Grafana with a set of alarms that will help us monitoring the metrics and being informed of potential problems, which will be described later. **Those dashboards and alerts are directly setup in the running process through config files**

### Dashboards and Alarms.
![alt text](https://i.imgur.com/RRnZYZW.png)

Grafana is used in this project to display dashboard and create alarms. Before continuing, let's mention that alerting through Grafana has its limitation:
- A graph must be created to create an alarm, only one alarm can be created by graph (with multiple conditions though). This means that for a graph showing data from several systems, an alarm would trigger if one system fails, but be already triggered is a second condition is met later.
- Alarms rules are quite basic
- No way to have degrees of severity in alarming (does the alarm require immediate action, or long term action)
- No way to get an alert condition to be true for a given number of period before alerting (Compared to monitoring tools like Cloudwatch)

While Kapacitor alerting might have been a solution for adding alerts directly from InfluxDB data, overcoming limitation such as having only one alarm per graph (or a graph per alert), Grafana will be enough to detect anomalies in our case.

The created alerts are:

#### For the CPU load:
- Too much load for the cpu is not good. However, we consider that we know that our server runs heavy jobs continuously. So we would tolerate an average load of 6 or 7 per minute, but not more (As this is a good usage for a 8 cores cpu). This alarm does not necessarily require an immediate action, thus is not critical, but might indicate a need for our server to scale.
- Too low load on the cpu could mean at least two things:
- - Some jobs are not properly running (given that we know our server is supposed to run quite heavy jobs)
- - We might need to scale down our infrastructure
- A too important spread of the metrics could mean a non linear use of the cpu, which is common, but should not happen in a usually loaded server. Naturally, the spread varies always a bit, a spread of 0 over a given period of time would be a sign that something might be weird with the metric.
- Several occurrences of an important load way above the number of cores could mean that something is wrong, even for a short amount of time.

-> We deduce that the system is often too loaded in our case, as the average load quite often goes over 7 (As seen in the dashboard picture)

#### For the random generator:

Here we are interested in knowing if the generator keeps showing values that look acceptable for a random generator. As we don't posses enough data to statistically test the generator (through the chi-square method...), we will try to detect basic anomalies:
- We display the distribution of the variables over 10 buckets of equal size in the range of the random generated number for visual monitoring.
- We check that the generator didn't give us the same value more than twice in the last 30s (It would be very unlikely, 2 values being the same would already have only a 0.01% chance of happening (birthday paradox))
- The average standard deviation should remain above 1 000 000 in the last minute, as random uniformly distributed variables are highly likely to be sparse.


#### For the counter:

Here we want to be sure our counter keeps increasing at a decent rate (No increase means no metrics technically sent, too fast increase means the systems is over sending metrics)
- The average of the non negative difference should remain between 1 and 3
- The counter should not decrease.


#### Other Metrics:

When the sensor runner parses and sends the metrics, he could face some problems. Instead of silently not sending any metrics if failing, the sensor runner will emit error metrics:
- If the values of the output cannot be associated to their metric (cast failing for instance): an error metric is sent, whose name is `error.{name of the failed metric}`
- If the communication to influx is synchronous, a fail to write will be sent as a `batch_sending_error`
- If the connection to influx is lost, failure metrics will be stored offline and sent once online, with a name `connectivity_error`
- As mentioned earlier, the potential 'sensor defect' measures are tagged in a special way, the number of occurence of those measures is shown in a counter (top left counter) and an alarm is set under the `Error occurring` dashboard


## Future improvements:
- Taking action on alerts. Alerts currently only show up in the dashboard, but email, slack notifications or webhooks could be used. With webhooks, actions could be taken for the sensor to restart, if we wanted so. Note while restarting can solve issues, it is quite often good to investigate why a system turned bad before restarting it.
- Some refactoring of the code could be done to be able to configure the kind of metrics expected.
- In case of scaling, using collecting agents such as statsd or telegraf before sending to InfluxDB could help.
- Other alerting systems could be used if Grafana alerts are too limited.
- Logging should be used if the project grows a bit as print statements are limited compared to logs.
- The current architecture uses HTTP calls to InfluxDB, which might become an issue as this blocks the code. Using threads could be a solution, an other would be to use UDP protocol to communicate to InfluxDB, with the risk of loosing data without being aware. A UDP support had been written for the sensor runner but some configurations are incomplete, making it unusable in the current state.
- Tests should be added as soon as the project grows more than this simple code.
- The error metrics in grafana could be wrongly named and this would fail silently as there is no metrics if no error. A good solution would be to always send such metrics with a counter to 0 if no problem happened
