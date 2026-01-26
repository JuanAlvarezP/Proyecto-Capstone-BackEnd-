import resend
from django.conf import settings
from django.contrib.auth.models import User
from .models import Assessment
import logging
import time

logger = logging.getLogger(__name__)


def send_assessment_invitation(assessment_id, user_ids, custom_message=None):
    """
    Envía invitación de evaluación a múltiples usuarios
    
    Args:
        assessment_id: ID del assessment
        user_ids: Lista de IDs de usuarios a invitar
        custom_message: Mensaje personalizado opcional
    
    Returns:
        dict: Resultado del envío con conteo de éxitos/errores
    """
    try:
        # Configurar API key de Resend
        resend.api_key = settings.RESEND_API_KEY
        
        # Obtener el assessment con relaciones
        assessment = Assessment.objects.select_related(
            'candidate', 'project'
        ).get(id=assessment_id)
        
        # Obtener usuarios a notificar
        users = User.objects.filter(id__in=user_ids)
        
        emails_sent = 0
        failed = 0
        recipients = []
        errors = []
        
        for user in users:
            try:
                # Construir el link directo
                assessment_link = f"{settings.FRONTEND_URL}/assessments"
                
                # Mensaje personalizado si existe
                custom_msg_section = ""
                if custom_message:
                    custom_msg_section = f"\n\n💬 Mensaje del equipo:\n{custom_message}\n"
                
                # Template del email
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #4F46E5;">Nueva Evaluación Técnica Asignada</h2>
                    
                    <p>Hola <strong>{user.first_name or user.username}</strong>,</p>
                    
                    <p>Te han asignado una nueva evaluación técnica:</p>
                    
                    <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 8px 0;"><strong>📋 Evaluación:</strong> {assessment.title}</p>
                        <p style="margin: 8px 0;"><strong>🎯 Tipo:</strong> {assessment.get_assessment_type_display()}</p>
                    </div>
                    {custom_msg_section}
                    <p>
                        <a href="{assessment_link}" 
                           style="display: inline-block; background-color: #4F46E5; color: white; 
                                  padding: 12px 24px; text-decoration: none; border-radius: 6px; 
                                  font-weight: bold;">
                            Iniciar Evaluación
                        </a>
                    </p>
                    
                    <p style="color: #6B7280; font-size: 14px;">
                        ¡Mucho éxito! Si tienes alguna duda, no dudes en contactarnos.
                    </p>
                </body>
                </html>
                """
                
                # Enviar email
                params = {
                    "from": settings.FROM_EMAIL,
                    "to": [user.email],
                    "subject": f"Nueva Evaluación Técnica Asignada - {assessment.title}",
                    "html": html_content,
                }
                
                resend.Emails.send(params)
                emails_sent += 1
                recipients.append(user.email)
                logger.info(f"✅ Email enviado a {user.email} para assessment {assessment_id}")
                time.sleep(0.6)  # Delay para respetar rate limit de Resend (2 req/sec)
                
            except Exception as e:
                failed += 1
                error_msg = f"Error enviando a {user.email}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            "success": True,
            "emails_sent": emails_sent,
            "failed": failed,
            "recipients": recipients,
            "errors": errors if errors else None,
            "message": f"Invitaciones enviadas: {emails_sent} exitosas, {failed} fallidas"
        }
        
    except Assessment.DoesNotExist:
        logger.error(f"Assessment {assessment_id} no existe")
        return {
            "success": False,
            "emails_sent": 0,
            "failed": 0,
            "recipients": [],
            "message": "Assessment no encontrado"
        }
    except Exception as e:
        logger.error(f"Error general en send_assessment_invitation: {str(e)}")
        return {
            "success": False,
            "emails_sent": 0,
            "failed": 0,
            "recipients": [],
            "message": f"Error: {str(e)}"
        }


def notify_assessment_completed(assessment_id):
    """
    Notifica que una evaluación fue completada:
    - Al candidato: Confirmación de recepción
    - A los admins: Nueva evaluación para revisar
    
    Args:
        assessment_id: ID del assessment completado
    
    Returns:
        dict: Resultado del envío
    """
    try:
        resend.api_key = settings.RESEND_API_KEY
        
        # Obtener assessment con relaciones
        assessment = Assessment.objects.select_related(
            'candidate', 'project'
        ).prefetch_related('answers').get(id=assessment_id)
        
        emails_sent = 0
        failed = 0
        recipients = []
        errors = []
        
        # 1. NOTIFICAR AL CANDIDATO
        try:
            candidate = assessment.candidate
            
            html_candidate = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #10B981;">¡Evaluación Completada!</h2>
                
                <p>Hola <strong>{candidate.first_name or candidate.username}</strong>,</p>
                
                <p>¡Gracias por completar la evaluación "<strong>{assessment.title}</strong>"!</p>
                
                <div style="background-color: #f0fdf4; padding: 20px; border-radius: 8px; 
                            border-left: 4px solid #10B981; margin: 20px 0;">
                    <p style="margin: 8px 0;">✅ <strong>Tu evaluación ha sido recibida exitosamente</strong></p>
                    <p style="margin: 8px 0;">📊 <strong>Está siendo revisada por nuestro equipo</strong></p>
                    <p style="margin: 8px 0;">📧 <strong>Te contactaremos pronto con los resultados</strong></p>
                </div>
                
                <p style="color: #6B7280;">
                    ¡Muchas gracias por tu tiempo y dedicación!
                </p>
            </body>
            </html>
            """
            
            resend.Emails.send({
                "from": settings.FROM_EMAIL,
                "to": [candidate.email],
                "subject": f"Evaluación Completada - {assessment.title}",
                "html": html_candidate,
            })
            
            emails_sent += 1
            recipients.append(candidate.email)
            logger.info(f"✅ Confirmación enviada a candidato {candidate.email}")
            
        except Exception as e:
            failed += 1
            error_msg = f"Error notificando a candidato: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        # 2. NOTIFICAR A LOS ADMINS
        admins = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)
        admins = admins.distinct()
        
        num_answers = assessment.answers.count()
        completed_at = assessment.completed_at.strftime("%d/%m/%Y %H:%M") if assessment.completed_at else "Ahora"
        admin_link = f"{settings.FRONTEND_URL}/admin/assessments"
        
        for admin in admins:
            try:
                html_admin = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #F59E0B;">Evaluación Completada para Revisión</h2>
                    
                    <p>Hola <strong>Admin</strong>,</p>
                    
                    <p>Un candidato ha completado una evaluación:</p>
                    
                    <div style="background-color: #fef3c7; padding: 20px; border-radius: 8px; 
                                border-left: 4px solid #F59E0B; margin: 20px 0;">
                        <p style="margin: 8px 0;"><strong>👤 Candidato:</strong> {assessment.candidate.first_name} {assessment.candidate.last_name}</p>
                        <p style="margin: 8px 0;"><strong>📧 Email:</strong> {assessment.candidate.email}</p>
                        <p style="margin: 8px 0;"><strong>📋 Evaluación:</strong> {assessment.title}</p>
                        <p style="margin: 8px 0;"><strong>🎯 Tipo:</strong> {assessment.get_assessment_type_display()}</p>
                        <p style="margin: 8px 0;"><strong>📝 Respuestas:</strong> {num_answers}</p>
                        <p style="margin: 8px 0;"><strong>📅 Completada:</strong> {completed_at}</p>
                    </div>
                    
                    <p>
                        <a href="{admin_link}" 
                           style="display: inline-block; background-color: #F59E0B; color: white; 
                                  padding: 12px 24px; text-decoration: none; border-radius: 6px; 
                                  font-weight: bold;">
                            Revisar y Calificar
                        </a>
                    </p>
                </body>
                </html>
                """
                
                resend.Emails.send({
                    "from": settings.FROM_EMAIL,
                    "to": [admin.email],
                    "subject": f"Evaluación Completada para Revisión - {assessment.title}",
                    "html": html_admin,
                })
                
                emails_sent += 1
                recipients.append(admin.email)
                logger.info(f"✅ Notificación enviada a admin {admin.email}")
                time.sleep(0.6)  # Delay para respetar rate limit de Resend (2 req/sec)
                
            except Exception as e:
                failed += 1
                error_msg = f"Error notificando a admin {admin.email}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            "success": True,
            "emails_sent": emails_sent,
            "failed": failed,
            "recipients": recipients,
            "errors": errors if errors else None,
            "message": f"Notificaciones enviadas: {emails_sent} exitosas, {failed} fallidas"
        }
        
    except Assessment.DoesNotExist:
        logger.error(f"Assessment {assessment_id} no existe")
        return {
            "success": False,
            "emails_sent": 0,
            "failed": 0,
            "recipients": [],
            "message": "Assessment no encontrado"
        }
    except Exception as e:
        logger.error(f"Error en notify_assessment_completed: {str(e)}")
        return {
            "success": False,
            "emails_sent": 0,
            "failed": 0,
            "recipients": [],
            "message": f"Error: {str(e)}"
        }
