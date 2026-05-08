FROM python:3.11-slim

WORKDIR /app

RUN pip install aiohttp --no-cache-dir

COPY . .

EXPOSE 8000

CMD ["python", "server.py"]