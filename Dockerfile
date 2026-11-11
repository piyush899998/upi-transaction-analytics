FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e '.[dashboard]'
COPY sql ./sql
COPY scripts ./scripts
COPY powerbi ./powerbi
EXPOSE 8501
CMD ["python", "-m", "upi_analytics.cli", "scheduler"]
