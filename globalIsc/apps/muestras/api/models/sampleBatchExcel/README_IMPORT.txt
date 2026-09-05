Agregar en apps/muestras/api/models/index.py:

from .sampleBatchExcel.index import SampleBatchExcelTemplateToken

Luego:
python manage.py makemigrations muestras
python manage.py migrate
