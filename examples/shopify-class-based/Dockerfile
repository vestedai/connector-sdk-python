FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
COPY bootstrap.py ./
RUN pip install --no-cache-dir .
CMD ["vested-connect", "worker", "--bootstrap=./bootstrap.py"]
