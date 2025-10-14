# models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ExtraField(models.Model):
    """
    Modelo auxiliar para manejar campos extras dinámicos en otras tablas
    """
    
    ESTADO_OPCIONES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('archivado', 'Archivado'),
        ('pendiente_revision', 'Pendiente de Revisión'),
    ]
    
    TIPO_CAMPO_OPCIONES = [
        ('texto', 'Texto'),
        ('numero', 'Número'),
        ('decimal', 'Decimal'),
        ('fecha', 'Fecha'),
        ('fecha_hora', 'Fecha y Hora'),
        ('booleano', 'Booleano'),
        ('opciones', 'Opciones'),
        ('archivo', 'Archivo'),
        ('email', 'Email'),
        ('url', 'URL'),
    ]
    
    # Relación con el modelo principal (genérico)
    tabla_relacionada = models.CharField(max_length=100)  # Ej: 'muestra', 'maquina', 'empresa'
    objeto_id = models.CharField(max_length=50)  # ID del objeto relacionado
    
    # Información del campo
    nombre_campo = models.CharField(max_length=100)
    tipo_campo = models.CharField(max_length=20, choices=TIPO_CAMPO_OPCIONES, default='texto')
    etiqueta = models.CharField(max_length=200, blank=True, null=True)  # Label para mostrar
    descripcion = models.TextField(blank=True, null=True)
    
    # Valor del campo (almacenado como texto para flexibilidad)
    valor_texto = models.TextField(blank=True, null=True)
    valor_numero = models.FloatField(blank=True, null=True)
    valor_fecha = models.DateTimeField(blank=True, null=True)
    valor_booleano = models.BooleanField(blank=True, null=True)
    
    # Opciones para campos de selección (JSON)
    opciones = models.JSONField(blank=True, null=True)
    
    # Configuración del campo
    requerido = models.BooleanField(default=False)
    orden = models.IntegerField(default=0)  # Para ordenar campos
    estado = models.CharField(max_length=20, choices=ESTADO_OPCIONES, default='activo')
    
    # Auditoría
    usuario_creacion = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='extrafields_creados'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    usuario_actualizacion = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='extrafields_actualizados',
        blank=True, 
        null=True
    )
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)
    usuario_ultima_edicion = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='extrafields_editados',
        blank=True, 
        null=True
    )
    fecha_ultima_edicion = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    version = models.IntegerField(default=1)
    es_editable = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'extra_fields'
        verbose_name = 'Campo Extra'
        verbose_name_plural = 'Campos Extras'
        unique_together = ['tabla_relacionada', 'objeto_id', 'nombre_campo']
        indexes = [
            models.Index(fields=['tabla_relacionada', 'objeto_id']),
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_creacion']),
        ]
        ordering = ['tabla_relacionada', 'objeto_id', 'orden', 'nombre_campo']
    
    def __str__(self):
        return f"{self.tabla_relacionada}.{self.objeto_id}.{self.nombre_campo}"
    
    def save(self, *args, **kwargs):
        # Actualizar fechas de modificación
        if self.pk:
            self.fecha_actualizacion = timezone.now()
        super().save(*args, **kwargs)
    
    def get_valor(self):
        """
        Devuelve el valor según el tipo de campo
        """
        if self.tipo_campo == 'texto':
            return self.valor_texto
        elif self.tipo_campo == 'numero':
            return self.valor_numero
        elif self.tipo_campo in ['decimal', 'numero']:
            return self.valor_numero
        elif self.tipo_campo in ['fecha', 'fecha_hora']:
            return self.valor_fecha
        elif self.tipo_campo == 'booleano':
            return self.valor_booleano
        return self.valor_texto
    
    def set_valor(self, valor):
        """
        Establece el valor según el tipo de campo
        """
        if self.tipo_campo == 'texto':
            self.valor_texto = str(valor) if valor else None
        elif self.tipo_campo in ['numero', 'decimal']:
            self.valor_numero = float(valor) if valor else None
        elif self.tipo_campo in ['fecha', 'fecha_hora']:
            self.valor_fecha = valor
        elif self.tipo_campo == 'booleano':
            self.valor_booleano = bool(valor)
    
    def clonar_para_objeto(self, nuevo_objeto_id, usuario):
        """
        Clona el campo para otro objeto
        """
        return ExtraField.objects.create(
            tabla_relacionada=self.tabla_relacionada,
            objeto_id=nuevo_objeto_id,
            nombre_campo=self.nombre_campo,
            tipo_campo=self.tipo_campo,
            etiqueta=self.etiqueta,
            descripcion=self.descripcion,
            valor_texto=self.valor_texto,
            valor_numero=self.valor_numero,
            valor_fecha=self.valor_fecha,
            valor_booleano=self.valor_booleano,
            opciones=self.opciones,
            requerido=self.requerido,
            orden=self.orden,
            estado=self.estado,
            usuario_creacion=usuario,
            es_editable=self.es_editable
        )