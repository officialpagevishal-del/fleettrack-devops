FROM python:3.12-slim
WORKDIR /sim
RUN pip install --no-cache-dir paho-mqtt==2.1.0
COPY gps_simulator.py .
CMD ["python", "gps_simulator.py"]
