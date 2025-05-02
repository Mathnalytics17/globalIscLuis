# Usar una imagen base de Python
FROM python:3.12-slim 

# Establecer el directorio de trabajo
WORKDIR /usr/src/aladinosWebPrueba

# Establecer PYTHONPATH
ENV PYTHONPATH=/usr/src/aladinosWebPrueba

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar el archivo requirements.txt
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

ENTRYPOINT [ "/usr/src/aladinosWebPrueba/entrypoint.sh" ]


# Exponer el puerto en el que se ejecutará la aplicación
EXPOSE 8000

# Comando para ejecutar la aplicación usando Gunicorn
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000"]
