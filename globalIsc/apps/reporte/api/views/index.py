import os
import io
import uuid
import base64
import logging
from datetime import datetime

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.loader import get_template, render_to_string
from django.core.files.storage import default_storage
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from xhtml2pdf import pisa

from apps.misc.api.models.limitesyaux.index import (
    ElementoAnalisis,
    ComentarioElemento,
    LimiteViscosidad,
)
from apps.reporte.api.models.index import (
    Interpretacion,
    DetalleInterpretacion,
    Reporte,
)
from apps.reporte.api.serializers.index import (
    InterpretacionSerializer,
    DetalleInterpretacionSerializer,
    ReporteSerializer,
    CreateReporteSerializer,
    ReporteSerializerConBase64,
)

# Configuración del logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)



class InterpretacionViewSet(viewsets.ModelViewSet):
    queryset = Interpretacion.objects.all()
    serializer_class = InterpretacionSerializer

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class DetalleInterpretacionViewSet(viewsets.ModelViewSet):
    queryset = DetalleInterpretacion.objects.all()
    serializer_class = DetalleInterpretacionSerializer

class ReporteViewSet(viewsets.ModelViewSet):
    queryset = Reporte.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreateReporteSerializer
        return ReporteSerializerConBase64  # Cambiar a este serializer
    
    def perform_create(self, serializer):
        serializer.save(usuario_emision=self.request.user, fecha_emision=timezone.now())
    
    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        reporte = self.get_object()
        
        if reporte.estatus != 'pendiente_aprobacion':
            return Response({'error': 'El reporte no está pendiente de aprobación'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        reporte.usuario_aprobacion = request.user
        reporte.fecha_aprobacion = timezone.now()
        reporte.estatus = 'aprobado'
        reporte.save()
        
        return Response(ReporteSerializer(reporte).data)
    
    @action(detail=True, methods=['post'])
    def enviar_aprobacion(self, request, pk=None):
        reporte = self.get_object()
        
        if reporte.estatus != 'borrador':
            return Response({'error': 'Solo reportes en borrador pueden enviarse a aprobación'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        reporte.estatus = 'pendiente_aprobacion'
        reporte.save()
        
        return Response(ReporteSerializer(reporte).data)
    
    
    # En tu función donde generas el PDF, también convierte las rutas de logos
    def get_pdf_context(self, context):
        """Convierte todas las rutas de imágenes a absolutas"""
        # Logo Global Oil
        logo_path = os.path.join(settings.STATIC_ROOT, 'logo-globaloil.jpg')
        logger.debug(logo_path)
        if os.path.exists(logo_path):
            context['logo_globaloil'] = logo_path
        else:
            # Fallback a ruta relativa si no existe
            context['logo_globaloil'] = 'logo-globaloil.jpg'
        
        # Icono reporte
        icon_path = os.path.join(settings.STATIC_ROOT, 'icon-report.png')
        if os.path.exists(icon_path):
            context['icon_report'] = icon_path
        else:
            context['icon_report'] = 'icon-report.png'
        
        return context
    @action(detail=True, methods=['get'])
    def firma_base64(self, request, pk=None):
        """
        Obtener la firma en base64
        """
        reporte = self.get_object()
        
        if not reporte.firma_ruta:
            return Response({'error': 'No hay firma disponible'}, status=404)
        
        try:
            # Construir ruta completa del archivo
            if reporte.firma_ruta.startswith('/media/'):
                file_path = reporte.firma_ruta.replace('/media/', '')
            else:
                file_path = reporte.firma_ruta
            
            # Verificar si el archivo existe
            if not default_storage.exists(file_path):
                return Response({'error': 'Archivo de firma no encontrado'}, status=404)
            
            # Leer el archivo y convertir a base64
            with default_storage.open(file_path, 'rb') as f:
                file_content = f.read()
                base64_encoded = base64.b64encode(file_content).decode('utf-8')
                
                # Determinar el tipo MIME
                if file_path.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif file_path.lower().endswith(('.jpg', '.jpeg')):
                    mime_type = 'image/jpeg'
                else:
                    mime_type = 'image/png'  # default
                
                data_url = f"data:{mime_type};base64,{base64_encoded}"
                
                return Response({
                    'firma_base64': data_url,
                    'mime_type': mime_type,
                    'file_name': os.path.basename(file_path)
                })
                
        except Exception as e:
            logger.error(f"Error leyendo firma: {str(e)}")
            return Response({'error': 'Error al leer la firma'}, status=500)
    def _evaluar_resultado_vs_limite(self, valor, limites):
        """
        Evalúa si un valor cumple con los límites establecidos
        Basado en los modelos: LimiteGenericoPrueba, ElementoAnalisis, LimiteCalidad, LimiteViscosidad
        Retorna: 'NORMAL', 'PENDIENTE' o 'NO DESEADO'
        """
        if not limites:
            return 'PENDIENTE'
        
        if valor is None or valor == '' or valor == '-':
            return 'PENDIENTE'
        
        try:
            valor_str = str(valor).strip()
            # Mejor conversión a número que maneje decimales y negativos
            try:
                valor_num = float(valor_str)
            except ValueError:
                # Si no se puede convertir a número, verificar si es texto para calidad
                if limites.get('tipo') == 'calidad':
                    return 'NORMAL'  # Para calidad, asumimos normal si hay valor
                return 'PENDIENTE'
            
            tipo_limite = limites.get('tipo')
            
            if tipo_limite == 'generico':
                # Para LimiteGenericoPrueba
                limite_valor = limites.get('valor')
                operador = limites.get('symbol_operation')
                
                if limite_valor is not None:
                    limite_num = float(limite_valor)
                    return self._aplicar_operador_comparacion(valor_num, limite_num, operador)
            
            elif tipo_limite == 'elemento_analisis':
                # Para ElementoAnalisis
                limite_valor = limites.get('valor')
                operador = limites.get('symbol_operation')
                
                if limite_valor is not None:
                    limite_num = float(limite_valor)
                    return self._aplicar_operador_comparacion(valor_num, limite_num, operador)
            
            elif tipo_limite == 'viscosidad':
                # Para LimiteViscosidad
                vmin = limites.get('vmin')
                vmax = limites.get('vmax')
                
                if vmin is not None and vmax is not None:
                    vmin_num = float(vmin)
                    vmax_num = float(vmax)
                    
                    if vmin_num <= valor_num <= vmax_num:
                        return 'NORMAL'
                    else:
                        return 'NO DESEADO'
                
                # También verificar v1 si no hay rango
                v1 = limites.get('v1')
                if v1 is not None:
                    # Para viscosidad con valor único, asumimos que debe ser igual
                    v1_num = float(v1)
                    if valor_num == v1_num:
                        return 'NORMAL'
                    else:
                        return 'NO DESEADO'
            
            elif tipo_limite == 'calidad':
                # Para LimiteCalidad - normalmente son valores categóricos
                # Si hay valor numérico, verificamos contra el límite de calidad
                limite_valor = limites.get('valor')
                if limite_valor is not None:
                    try:
                        limite_num = float(limite_valor)
                        # Para calidad, podrías tener lógica específica
                        # Por ahora, asumimos que si hay valor y límite, es normal
                        return 'NORMAL'
                    except ValueError:
                        # Si el límite no es numérico, es normal por defecto
                        return 'NORMAL'
                return 'NORMAL'  # Calidad siempre normal si hay límites definidos
                
        except (ValueError, TypeError) as e:
            logger.error(f"Error evaluando límites para valor '{valor}': {e}")
        
        return 'PENDIENTE'

    def _aplicar_operador_comparacion(self, valor, limite, operador):
        """
        Aplica el operador de comparación y retorna el estado
        """
        if operador == '<' and valor < limite:
            return 'NORMAL'
        elif operador == '<=' and valor <= limite:
            return 'NORMAL'
        elif operador == '=' and valor == limite:
            return 'NORMAL'
        elif operador == '>=' and valor >= limite:
            return 'NORMAL'
        elif operador == '>' and valor > limite:
            return 'NORMAL'
        else:
            return 'NO DESEADO'
    # NUEVO ENDPOINT PARA SUBIR FIRMAS
    @action(detail=False, methods=['post'], url_path='upload-signature')
    def upload_signature(self, request):
        """
        Endpoint para subir archivos de firma
        """
        try:
            # Verificar que se haya enviado un archivo
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'No se encontró ningún archivo en la solicitud'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            file = request.FILES['file']
            folder = request.POST.get('folder', 'firmas')
            
            # Validar que sea una imagen
            if not file.content_type.startswith('image/'):
                return Response(
                    {'error': 'El archivo debe ser una imagen'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validar tamaño del archivo (máximo 2MB)
            if file.size > 2 * 1024 * 1024:
                return Response(
                    {'error': 'El archivo no puede ser mayor a 2MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generar nombre único para el archivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = uuid.uuid4().hex[:8]
            file_extension = os.path.splitext(file.name)[1]
            filename = f"firma_{timestamp}_{unique_id}{file_extension}"
            
            # Ruta donde se guardará el archivo
            file_path = os.path.join(folder, filename)
            
            # Guardar el archivo
            saved_path = default_storage.save(file_path, file)
            
            # Construir la URL completa para acceder al archivo
            if hasattr(settings, 'MEDIA_URL'):
                file_url = settings.MEDIA_URL + saved_path
            else:
                # Si no hay MEDIA_URL configurado, usar ruta relativa
                file_url = '/' + saved_path
            
            return Response({
                'message': 'Firma guardada exitosamente',
                'filePath': file_url,
                'fileName': filename,
                'savedPath': saved_path
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error al guardar firma: {str(e)}")
            return Response(
                {'error': f'Error interno del servidor: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @action(detail=False, methods=['get'])
    def imprimir_reporte(self, request):
        """
        Endpoint para generar PDF del reporte - COMPLETO Y CORREGIDO
        """
        try:
            reporte_id = request.query_params.get('pdf')
            if not reporte_id:
                return Response({
                    'error': True, 
                    'message': 'Parámetro "pdf" requerido'
                }, status=400)
            
            # Obtener reporte y muestra
            reporte, muestra = self._obtener_reporte_y_muestra(reporte_id)
            if not reporte:
                return Response({
                    'error': True, 
                    'message': 'Reporte no encontrado'
                }, status=404)
            
            # Preparar datos para el template
            context = self._preparar_contexto_reporte(reporte, muestra)
            
            # Generar HTML - USANDO TU TEMPLATE GLOBALREPORT.HTML
            html_content = self._render_html_template_globalreport(context)
            
            # Logging corregido
            logger.debug(f"HTML generado, tamaño: {len(html_content)} caracteres")
            
            # Generar PDF
            pdf_result = self._generar_pdf(html_content)
            
            if pdf_result.get('error'):
                return Response({
                    'error': True, 
                    'message': f'Error generando PDF: {pdf_result.get("error")}'
                }, status=500)
            
            return Response({
                'error': False, 
                'pdf': pdf_result['pdf'],
                'data': context
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error en imprimir_reporte: {str(e)}")
            return Response({
                'error': True, 
                'message': f'Error al procesar solicitud: {str(e)}'
            }, status=500)
    
    def _obtener_reporte_y_muestra(self, reporte_id):
        """Obtiene reporte y muestra basado en el ID"""
        if reporte_id.startswith('M'):
            from apps.muestras.api.models.muestras.index import Muestra
            muestra = Muestra.objects.filter(id=reporte_id).first()
            logger.debug(muestra)
            if not muestra:
                return None, None
            reporte = self.get_queryset().filter(muestra=muestra).first()
            return reporte, muestra
        else:
            try:
                reporte_id_int = int(reporte_id)
                reporte = self.get_queryset().filter(id=reporte_id_int).first()
                if reporte:
                    return reporte, reporte.muestra
            except ValueError:
                pass
        return None, None
    


    def _preparar_contexto_reporte(self, reporte, muestra):
        
        logger.debug(f'hola {settings.MEDIA_ROOT}')
        """Prepara todos los datos para el template"""
        # Obtener datos relacionados con prefetch para optimizar
        resultados = muestra.resultados.all().select_related(
            'prueba'
        ).prefetch_related(
            'prueba__limite_asignado',
            'prueba__limite_asignado__limite'
        ) if hasattr(muestra, 'resultados') else []

        equipo_info = muestra.referencia_equipo if hasattr(muestra, 'referencia_equipo') else None
        empresa_info = getattr(equipo_info, 'empresa', None) if equipo_info else None
        lubricante_info = muestra.lubricante if hasattr(muestra, 'lubricante') else None

          # ✅ CORREGIDO: Convertir ruta de firma a ruta absoluta
        firma_ruta =os.path.join(settings.MEDIA_ROOT, 'firmas',reporte.firma_ruta.split('/')[-1])
        logo_global_ruta=os.path.join(settings.MEDIA_ROOT,'templates','logo-globaloil.jpg')
        logo_report_ruta=os.path.join(settings.MEDIA_ROOT,'templates','icon-report.png')
        # Estructurar datos de manera clara
        context = {
            # Información principal
            'reporte_info': {
                'consecutivo': reporte.consecutivo or 'N/A',
                'fecha_emision': reporte.fecha_emision.strftime('%d/%m/%Y') if reporte.fecha_emision else 'N/A',
                'comentarios': reporte.comentarios or '',
                'conclusiones': reporte.conclusiones or '',
                'responsable': getattr(reporte, 'Responsable', 'Ing. Responsable'),
                'firma_ruta': firma_ruta,  # ✅ Usar ruta absoluta
                'estatus': reporte.estatus,
                'with_limites': reporte.with_limites,
                'logo_global':logo_global_ruta,
                'logo_report':logo_report_ruta,
             
            },
            'muestra_info': {
                'id': muestra.id,
                'fecha_toma': muestra.fecha_toma.strftime('%d/%m/%Y') if muestra.fecha_toma else 'N/A',
                'periodo_servicio_aceite': muestra.periodo_servicio_aceite or 'N/A',
                'unidad_periodo_aceite': muestra.unidad_periodo_aceite or '',
                'periodo_servicio_equipo': muestra.periodo_servicio_equipo or 'N/A',
                'unidad_periodo_equipo': muestra.unidad_periodo_equipo or '',
                'equipo_placa': muestra.equipo_placa or 'N/A',
                'contacto_cliente': muestra.contacto_cliente or 'N/A',
                'observaciones': muestra.observaciones or '',
            },
            'equipo_info': {
                'nombre': getattr(equipo_info, 'nombre', 'N/A'),
                'codigo_equipo': getattr(equipo_info, 'codigo_equipo', 'N/A'),
            },
            'empresa_info': {
                'nombre': getattr(empresa_info, 'nombre', 'N/A'),
                'direccion': getattr(empresa_info, 'direccion', 'N/A'),
                'telefono': getattr(empresa_info, 'telefono', 'N/A'),
                'email': getattr(empresa_info, 'email', 'N/A'),
            },
            'lubricante_info': {
                'nombre_comercial': getattr(lubricante_info, 'nombre_comercial', 'N/A'),
                'referencia': getattr(lubricante_info, 'referencia', 'N/A'),
            },
            # Datos para el template (formato simplificado)
            'pruebas_estructuradas': [],
            'observaciones': reporte.comentarios or 'No hay comentarios registrados',
            'conclusiones': reporte.conclusiones or 'No hay conclusiones registradas',
            'responsable': getattr(reporte, 'Responsable', 'Ing. Responsable'),
            'empresa': getattr(empresa_info, 'nombre', 'N/A') if empresa_info else 'N/A',
            'consecutivo': reporte.consecutivo or 'N/A',
            'fecha_emision': reporte.fecha_emision.strftime('%d/%m/%Y') if reporte.fecha_emision else 'N/A',
            'muestra': {
                'id': muestra.id,
                'fecha_toma': muestra.fecha_toma.strftime('%d/%m/%Y') if muestra.fecha_toma else 'N/A',
                'periodo_servicio_aceite': muestra.periodo_servicio_aceite or 'N/A',
                'unidad_periodo_aceite': muestra.unidad_periodo_aceite or '',
                'periodo_servicio_equipo': muestra.periodo_servicio_equipo or 'N/A', 
                'unidad_periodo_equipo': muestra.unidad_periodo_equipo or '',
                'equipo_placa': muestra.equipo_placa or 'N/A',
                'contacto_cliente': muestra.contacto_cliente or 'N/A',
            }
        }

        for resultado in resultados:
            # Obtener límites usando la misma lógica que PruebaSerializer
            limites = self._obtener_limites_prueba(resultado.prueba)
            
            # ✅ EVALUAR SI CUMPLE CON LOS LÍMITES (usando la función mejorada)
            estado = self._evaluar_resultado_vs_limite(resultado.valor, limites)
            
            # ✅ DETERMINAR SI ESTÁ COMPLETADA BASADO EN EL ESTADO
            completada = estado == 'NORMAL'
            
            prueba_data = {
                'id': resultado.id,
                'prueba': {
                    'nombre': getattr(resultado.prueba, 'nombre', 'N/A'),
                    'metodo_referencia': getattr(resultado.prueba, 'metodo_referencia', '-'),
                    'unidad_medida': getattr(resultado.prueba, 'unidad_medida', '-'),
                    'limites': limites
                },
                'valor': resultado.valor or '-',
                'unidad': resultado.unidad or '-',
                'observaciones': resultado.observaciones or '',
                'completada': completada,
                'estatus': estado,  # 'NORMAL', 'PENDIENTE' o 'NO DESEADO'
                'estado_evaluado': estado  # Para usar en el template
            }
            context['pruebas_estructuradas'].append(prueba_data)
        
        logger.debug(f'Contexto preparado: {len(context["pruebas_estructuradas"])} resultados')
        return context
    def _obtener_limites_prueba(self, prueba_obj):
        """Función auxiliar para obtener límites de cualquier objeto Prueba (misma lógica que PruebaSerializer)"""
        try:
            # Buscar la relación PruebaLimite para esta prueba
            if not hasattr(prueba_obj, 'limite_asignado') or not prueba_obj.limite_asignado:
                return None
            
            prueba_limite = prueba_obj.limite_asignado
            
            # Obtener el objeto límite a través del GenericForeignKey
            limite_obj = prueba_limite.limite
            
            if not limite_obj:
                return None
            
            # Serializar según el tipo de límite
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get_for_model(limite_obj)
            
            if content_type.model == 'limitegenericoprueba':
                return {
                    'tipo': 'generico',
                    'nombre': getattr(limite_obj, 'nombre', ''),
                    'valor': getattr(limite_obj, 'valor', ''),
                    'symbol_operation': getattr(limite_obj, 'symbol_operation', ''),
                    'type_operation': getattr(limite_obj, 'type_operation', '')
                }
            
            elif content_type.model == 'limitecalidad':
                return {
                    'tipo': 'calidad',
                    'c1': getattr(limite_obj, 'c1', ''),
                    'c2': getattr(limite_obj, 'c2', ''),
                    'seq_espuma': getattr(limite_obj, 'seq_espuma', ''),
                    'chispa': getattr(limite_obj, 'chispa', ''),
                    'valor': getattr(limite_obj, 'valor', '')
                }
            
            elif content_type.model == 'limiteviscosidad':
                return {
                    'tipo': 'viscosidad',
                    'v1': getattr(limite_obj, 'v1', ''),
                    'v2': getattr(limite_obj, 'v2', ''),
                    'vmin': getattr(limite_obj, 'vmin', ''),
                    'vmax': getattr(limite_obj, 'vmax', ''),
                    'iv1': getattr(limite_obj, 'iv1', ''),
                    'iv2': getattr(limite_obj, 'iv2', '')
                }
            
            elif content_type.model == 'elementoanalisis':
                return {
                    'tipo': 'elemento_analisis',
                    'simbolo': getattr(limite_obj, 'simbolo', ''),
                    'nombre': getattr(limite_obj, 'nombre', ''),
                    'valor': getattr(limite_obj, 'valor', ''),
                    'symbol_operation': getattr(limite_obj, 'symbol_operation', ''),
                }
            
            else:
                return {
                    'tipo': 'desconocido',
                    'content_type': content_type.model,
                    'object_id': prueba_limite.object_id
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo límites para prueba {prueba_obj.id}: {e}")
            return None
    
    def _render_html_template_globalreport(self, context):
        """
        Renderiza específicamente el template globalreport.html
        SIEMPRE usa renderizado manual para control total
        """
        # Ruta exacta de tu template
        template_paths = [
            
            os.path.join(settings.BASE_DIR, 'apps', 'media', 'templates', 'globalreport.html'),
            os.path.join(settings.BASE_DIR, 'templates', 'globalreport.html'),
            'globalreport.html',  # Último recurso: sistema de templates de Django
        ]
        
        for template_path in template_paths:
            try:
               
                # Es un nombre de template Django
                template = get_template(template_path)
                html_content = template.render(context)
                logger.debug(f'✅ Template cargado via Django: {template_path}')
                return html_content
                    
            except Exception as e:
                logger.debug(f'❌ No se pudo cargar {template_path}: {str(e)}')
                continue

  


    def _render_loop_pruebas_completo(self, html_content, context):
        """Renderiza COMPLETAMENTE el loop de pruebas"""
        start_tag = '{% for prueba in pruebas_estructuradas %}'
        end_tag = '{% endfor %}'
        
        start_idx = html_content.find(start_tag)
        if start_idx == -1:
            logger.debug("❌ No se encontró el loop de pruebas")
            return html_content
        
        end_idx = html_content.find(end_tag, start_idx)
        if end_idx == -1:
            logger.error("❌ Loop de pruebas incompleto (no se encontró endfor)")
            return html_content
        
        loop_template = html_content[start_idx + len(start_tag):end_idx]
        pruebas = context.get('pruebas_estructuradas', [])
        
        logger.debug(f"🔄 Renderizando {len(pruebas)} pruebas en el loop...")
        
        rendered_rows = []
        
        for i, prueba in enumerate(pruebas):
            row_content = loop_template
            
            # Reemplazar TODAS las variables de la prueba
            row_content = self._reemplazar_variables_prueba(row_content, prueba)
            
            # Procesar condicional de completada
            row_content = self._procesar_condicional_completada_completo(row_content, prueba)
            
            rendered_rows.append(row_content)
        
        # Reemplazar el bloque completo del loop
        full_loop_block = html_content[start_idx:end_idx + len(end_tag)]
        replacement_content = ''.join(rendered_rows)
        html_content = html_content.replace(full_loop_block, replacement_content)
        
        logger.debug(f"✅ Loop renderizado: {len(rendered_rows)} filas")
        return html_content

    def _reemplazar_variables_prueba(self, row_content, prueba):
        """Reemplaza TODAS las variables de una prueba individual"""
        replacements = {
            '{{ prueba.prueba.nombre }}': prueba.get('prueba', {}).get('nombre', 'N/A'),
            '{{ prueba.prueba.metodo_referencia }}': prueba.get('prueba', {}).get('metodo_referencia', '-'),
            '{{ prueba.prueba.metodo_referencia|default:"-" }}': prueba.get('prueba', {}).get('metodo_referencia', '-'),
            '{{ prueba.prueba.unidad_medida }}': prueba.get('prueba', {}).get('unidad_medida', '-'),
            '{{ prueba.prueba.unidad_medida|default:"-" }}': prueba.get('prueba', {}).get('unidad_medida', '-'),
            '{{ prueba.valor }}': str(prueba.get('valor', '-')),
            '{{ prueba.valor|default:"-" }}': str(prueba.get('valor', '-')),
        }
        
        for var, val in replacements.items():
            row_content = row_content.replace(var, val)
        
        return row_content

    def _procesar_condicional_completada_completo(self, row_content, prueba):
        """Procesa COMPLETAMENTE el condicional de completada"""
        if_start = '{% if prueba.completada %}'
        if_else = '{% else %}'
        if_end = '{% endif %}'
        
        start_idx = row_content.find(if_start)
        if start_idx == -1:
            return row_content
        
        else_idx = row_content.find(if_else, start_idx)
        end_idx = row_content.find(if_end, start_idx)
        
        if else_idx == -1 or end_idx == -1:
            return row_content
        
        # Determinar qué contenido usar
        if prueba.get('completada', False):
            selected_content = row_content[start_idx + len(if_start):else_idx]
            # Asegurar que muestre "NORMAL"
            selected_content = selected_content.replace('PENDIENTE', 'NORMAL')
            selected_content = selected_content.replace('badge-pending', 'badge-normal')
        else:
            selected_content = row_content[else_idx + len(if_else):end_idx]
            # Asegurar que muestre "PENDIENTE"  
            selected_content = selected_content.replace('NORMAL', 'PENDIENTE')
            selected_content = selected_content.replace('badge-normal', 'badge-pending')
        
        # Reemplazar el bloque condicional completo
        full_block = row_content[start_idx:end_idx + len(if_end)]
        row_content = row_content.replace(full_block, selected_content)
        
        return row_content

    def _obtener_todas_las_variables(self, context):
        """Obtiene TODAS las variables para reemplazar"""
        def safe_str(value):
            if value is None:
                return ''
            return str(value)
        
        # Obtener firma_ruta de diferentes ubicaciones posibles
        firma_ruta = (
            context.get('firma_ruta') or 
            context.get('reporte_info', {}).get('firma_ruta') or
            ''
        )
        
        return {
            '{{ observaciones }}': safe_str(context.get('observaciones', '')),
            '{{ conclusiones }}': safe_str(context.get('conclusiones', '')),
            '{{ responsable }}': safe_str(context.get('responsable', '')),
            '{{ empresa }}': safe_str(context.get('empresa', '')),
            '{{ consecutivo }}': safe_str(context.get('consecutivo', '')),
            '{{ fecha_emision }}': safe_str(context.get('fecha_emision', '')),
            '{{ firma_ruta }}': safe_str(firma_ruta),
            
            # Variables de muestra
            '{{ muestra.id }}': safe_str(context.get('muestra_info', {}).get('id')),
            '{{ muestra.fecha_toma }}': safe_str(context.get('muestra_info', {}).get('fecha_toma')),
            '{{ muestra.periodo_servicio_aceite }}': safe_str(context.get('muestra_info', {}).get('periodo_servicio_aceite')),
            '{{ muestra.unidad_periodo_aceite }}': safe_str(context.get('muestra_info', {}).get('unidad_periodo_aceite')),
            '{{ muestra.periodo_servicio_equipo }}': safe_str(context.get('muestra_info', {}).get('periodo_servicio_equipo')),
            '{{ muestra.equipo_placa }}': safe_str(context.get('muestra_info', {}).get('equipo_placa')),
            '{{ muestra.contacto_cliente }}': safe_str(context.get('muestra_info', {}).get('contacto_cliente')),
            
            # Variables de empresa
            '{{ empresa_info.nombre }}': safe_str(context.get('empresa_info', {}).get('nombre')),
            '{{ empresa_info.direccion }}': safe_str(context.get('empresa_info', {}).get('direccion')),
            '{{ empresa_info.telefono }}': safe_str(context.get('empresa_info', {}).get('telefono')),
            '{{ empresa_info.email }}': safe_str(context.get('empresa_info', {}).get('email')),
            
            # Variables de equipo
            '{{ equipo_info.nombre }}': safe_str(context.get('equipo_info', {}).get('nombre')),
            '{{ equipo_info.codigo_equipo }}': safe_str(context.get('equipo_info', {}).get('codigo_equipo')),
            
            # Variables de lubricante
            '{{ lubricante_info.nombre_comercial }}': safe_str(context.get('lubricante_info', {}).get('nombre_comercial')),
            '{{ lubricante_info.referencia }}': safe_str(context.get('lubricante_info', {}).get('referencia')),
            
            # Variables de reporte
            '{{ reporte_info.consecutivo }}': safe_str(context.get('reporte_info', {}).get('consecutivo')),
            '{{ reporte_info.fecha_emision }}': safe_str(context.get('reporte_info', {}).get('fecha_emision')),
            '{{ reporte_info.comentarios }}': safe_str(context.get('reporte_info', {}).get('comentarios')),
            '{{ reporte_info.conclusiones }}': safe_str(context.get('reporte_info', {}).get('conclusiones')),
            '{{ reporte_info.responsable }}': safe_str(context.get('reporte_info', {}).get('responsable')),
        }
    
    
    
    def _generar_pdf(self, html_content):
        """Genera PDF desde HTML - CON DIAGNÓSTICO"""
        try:
            pdf_file = io.BytesIO()
            
            def fetch_resources(uri, rel):
                """
                Función de diagnóstico para ver QUÉ está buscando y DÓNDE
                """
                logger.debug(f"📁 xhtml2pdf está buscando: '{uri}' (rel: {rel})")
                
                # Si es una URL web, déjala como está
                if uri.startswith('http://') or uri.startswith('https://'):
                    logger.debug(f"🌐 Es URL web: {uri}")
                    return uri
                
                # RUTAS DONDE PODRÍAN ESTAR TUS IMÁGENES
                posibles_rutas = [
                    
                    # Directorio static
                    os.path.join(settings.BASE_DIR, 'static'),
                    # Directorio media de Django
                    settings.MEDIA_ROOT,
                 
                ]
                
                # Buscar en todas las rutas posibles
                for base_path in posibles_rutas:
                    if base_path and os.path.exists(base_path):
                        full_path = os.path.join(base_path, uri)
                        if os.path.exists(full_path):
                            logger.debug(f"✅ IMAGEN ENCONTRADA: {full_path}")
                            return full_path
                        else:
                            logger.debug(f"❌ No encontrada en: {full_path}")
                
                # Si no se encuentra, buscar archivos con nombres similares
                logger.debug(f"🔍 Buscando archivos con nombre similar a: {uri}")
                for base_path in posibles_rutas:
                    if base_path and os.path.exists(base_path):
                        for root, dirs, files in os.walk(base_path):
                            for file in files:
                                if uri.lower() in file.lower():
                                    found_path = os.path.join(root, file)
                                    logger.debug(f"📄 Archivo similar encontrado: {found_path}")
                                    return found_path
                
                logger.error(f"🚫 NO SE PUDO ENCONTRAR: {uri}")
                logger.error("Creando imagen dummy como fallback...")
                
              
            
            # Crear PDF
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_file,
                encoding='UTF-8',
                link_callback=fetch_resources
            )
            
            if pisa_status.err:
                return {'error': f"Error generando PDF: {pisa_status.err}"}
            
            pdf_base64 = base64.b64encode(pdf_file.getvalue()).decode('utf-8')
            pdf_file.close()
            
            return {'pdf': pdf_base64}
            
        except Exception as e:
            logger.error(f"Error en _generar_pdf: {str(e)}")
            return {'error': str(e)}

    