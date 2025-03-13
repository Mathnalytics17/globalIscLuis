
from ..models.index import Carpeta
from ..models.analysis.index import AnalisisLubricante
from ..models.machines.index import Maquina
from ..models.resultsAnalysis.index import ResultadoMuestrasAceite

from rest_framework import serializers
       
class CarpetaSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Carpeta
        fields = '__all__'


class MaquinaSerializer(serializers.ModelSerializer):

    class Meta:
        model = Maquina
        fields = '__all__'
        
        
class AnalisisLubricanteSerializer(serializers.ModelSerializer):
    Maquina= MaquinaSerializer()  # Incluye los datos del análisis relacionado
    class Meta:
        model = AnalisisLubricante
        fields = '__all__'


class ResultadoMuestrasAceiteSerializer(serializers.ModelSerializer):
    analisis = AnalisisLubricanteSerializer()  # Incluye los datos del análisis relacionado

    class Meta:
        model = ResultadoMuestrasAceite
        fields = '__all__'
        


        

 



