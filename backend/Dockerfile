FROM python:3.11-slim

WORKDIR /app

# system deps for PyMuPDF / pdfplumber / Camelot (opencv) rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
