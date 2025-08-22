# Dockerfile para OpenShift Monitor
FROM python:3.11-slim

# Metadatos
LABEL maintainer="OpenShift Monitor Team"
LABEL description="Monitor continuo de clusters OpenShift usando APIs de Prometheus"
LABEL version="1.0.0"

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalar OpenShift CLI (oc) - versión compatible con glibc 2.28
RUN wget -O /tmp/oc.tar.gz https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/4.10.60/openshift-client-linux.tar.gz \
    && tar -xzf /tmp/oc.tar.gz -C /usr/local/bin oc kubectl \
    && chmod +x /usr/local/bin/oc /usr/local/bin/kubectl \
    && rm /tmp/oc.tar.gz

# Verificar que oc esté disponible
RUN oc version --client

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash monitor

# Cambiar al directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY openshift_monitor.py .
COPY telegram_bot.py .
COPY config.env .

# Crear directorios necesarios y ajustar permisos
RUN mkdir -p /app/reports /app/logs && \
    chown -R monitor:monitor /app && \
    chmod -R 755 /app && \
    chmod 777 /app/reports /app/logs

# Cambiar al usuario monitor
USER monitor

# Exponer puerto
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Comando por defecto
CMD ["python", "openshift_monitor.py"] 