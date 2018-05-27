FROM python:3.6
MAINTAINER Adrien Duffy <adrien.duffy@gmail.com>


RUN mkdir -p /app/sensor_runner

WORKDIR /app/sensor_runner

COPY requirements.txt .

RUN pip install --no-cache-dir -r ./requirements.txt

COPY run.py .
COPY . sensor_runner

CMD ["python", "run.py", "--path-executable", "./sensor_runner/sensor"]
