# Dockerfile

# 1. Basisimage wählen (spezifische Version, slim ist kleiner)
FROM python:3.13-slim

# 2. Arbeitsverzeichnis im Container setzen
WORKDIR /app

# 3. Umgebungsvariable für unbuffered Python-Output (gut für Logs)
ENV PYTHONUNBUFFERED=1

# 4. Abhängigkeiten installieren (wird beim Image-Bau ausgeführt)
# Nur requirements.txt kopieren, um den Build-Cache zu nutzen
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Restlichen Anwendungscode in das Image kopieren
COPY . .

# 6. (Optional) Sicherstellen, dass das logs/ und db/ Verzeichnis existiert
#    Dies ist nützlich, wenn Volumes später von Docker erstellt werden sollen
RUN mkdir -p /app/logs /app/db

# 7. Standardbefehl zum Starten der Anwendung
CMD ["python", "main.py"]