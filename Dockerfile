FROM --platform=linux/amd64 python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OPENPYXL_DEFUSEDXML=True
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY dependency_wheels/ /app/dependency_wheels/
RUN python -m pip install --no-cache-dir --no-index --find-links=/app/dependency_wheels --require-hashes -r /app/requirements.txt
COPY main.py /app/main.py
COPY excelqa/ /app/excelqa/
ENTRYPOINT ["python", "/app/main.py"]
