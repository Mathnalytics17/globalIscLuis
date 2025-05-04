from django.db import models

class Marca(models.Model):
    nombre = models.CharField(max_length=100)
    carpeta = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return self.nombre
class ComentarioPredefinido(models.Model):
    TIPO_CHOICES = [
        ('NORMAL', 'Normal'),
        ('NO_DESEADO', 'No deseado'),
    ]
    
    texto = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Comentario predefinido"
        verbose_name_plural = "Comentarios predefinidos"
    
    def __str__(self):
        return f"{self.texto} ({self.get_tipo_display()})"


class Calidad(models.Model):
    tipo = models.CharField(max_length=20)  # API, ISO-L-, JASO, etc.
    
    def __str__(self):
        return self.tipo

class Color(models.Model):
    nombre = models.CharField(max_length=50)
    
    def __str__(self):
        return self.nombre

class MarcaGrasa(models.Model):
    nombre = models.CharField(max_length=100)
    color = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return self.nombre

class NLGI(models.Model):
    grado = models.CharField(max_length=10)
    minimo = models.IntegerField()
    maximo = models.IntegerField()
    
    def __str__(self):
        return f"NLGI {self.grado}"

class Jabon(models.Model):
    tipo = models.CharField(max_length=50)
    acidez_alcali = models.CharField(max_length=50)
    metodo = models.CharField(max_length=50)
    valor = models.CharField(max_length=50)
    agua = models.CharField(max_length=50, blank=True, null=True)
    goteo = models.IntegerField(blank=True, null=True)
    
    def __str__(self):
        return self.tipo

class ColorGrasa(models.Model):
    nombre = models.CharField(max_length=50)
    
    def __str__(self):
        return self.nombre
    


class SistemaFiltracion(models.Model):
    codigo_iso = models.CharField(max_length=50)
    tipo_sistema = models.TextField()
    componentes_tipicos = models.TextField()
    sensibilidad = models.CharField(max_length=50)
    um_4 = models.IntegerField()
    um_6 = models.IntegerField()
    um_14 = models.IntegerField()

    def __str__(self):
        return f"{self.codigo_iso} - {self.tipo_sistema[:50]}..."