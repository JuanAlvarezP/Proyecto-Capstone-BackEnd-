import resend
from django.conf import settings
from django.contrib.auth.models import User
from .models import Application
import logging

logger = logging.getLogger(__name__)


def notify_new_application(application_id):
    """
    Notifica a todos los administradores sobre una nueva aplicación recibida
    
    Args:
        application_id: ID de la aplicación
    
    Returns:
        dict: Resultado del envío con conteo de éxitos/errores
    """
    try:
        # Configurar API key de Resend
        resend.api_key = settings.RESEND_API_KEY
        
        # Obtener la aplicación con relaciones
        application = Application.objects.select_related(
            'candidate', 'project'
        ).get(id=application_id)
        
        # Obtener todos los administradores
        admins = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)
        admins = admins.distinct()
        
        if not admins.exists():
            logger.warning("No hay administradores para notificar")
            return {
                "success": True,
                "emails_sent": 0,
                "failed": 0,
                "recipients": [],
                "message": "No hay administradores registrados"
            }
        
        emails_sent = 0
        failed = 0
        recipients = []
        errors = []
        
        # Información de la aplicación
        candidate = application.candidate
        project = application.project
        applied_at = application.created_at.strftime("%d/%m/%Y %H:%M")
        admin_link = f"{settings.FRONTEND_URL}/admin/applications/{application_id}"
        
        # Información del CV
        cv_info = ""
        if application.cv_file:
            cv_info = f'<p style="margin: 8px 0;"><strong>📄 CV:</strong> <a href="{application.cv_file.url}">Ver CV</a></p>'
        
        # Enviar a cada administrador
        for admin in admins:
            try:
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #3B82F6;">Nueva Aplicación Recibida</h2>
                    
                    <p>Hola <strong>Admin</strong>,</p>
                    
                    <p>Se ha recibido una nueva aplicación que requiere revisión:</p>
                    
                    <div style="background-color: #dbeafe; padding: 20px; border-radius: 8px; 
                                border-left: 4px solid #3B82F6; margin: 20px 0;">
                        <p style="margin: 8px 0;"><strong>👤 Candidato:</strong> {candidate.first_name} {candidate.last_name}</p>
                        <p style="margin: 8px 0;"><strong>📧 Email:</strong> {candidate.email}</p>
                        <p style="margin: 8px 0;"><strong>📁 Proyecto:</strong> {project.title}</p>
                        <p style="margin: 8px 0;"><strong>📅 Fecha:</strong> {applied_at}</p>
                        {cv_info}
                        <p style="margin: 8px 0;"><strong>📊 Estado:</strong> {application.get_status_display()}</p>
                    </div>
                    
                    <p>
                        <a href="{admin_link}" 
                           style="display: inline-block; background-color: #3B82F6; color: white; 
                                  padding: 12px 24px; text-decoration: none; border-radius: 6px; 
                                  font-weight: bold;">
                            Revisar Aplicación
                        </a>
                    </p>
                    
                    <p style="color: #6B7280; font-size: 14px;">
                        Revisa el perfil del candidato y toma las acciones necesarias.
                    </p>
                </body>
                </html>
                """
                
                # Enviar email
                params = {
                    "from": settings.FROM_EMAIL,
                    "to": [admin.email],
                    "subject": f"Nueva Aplicación Recibida - {project.title}",
                    "html": html_content,
                }
                
                resend.Emails.send(params)
                emails_sent += 1
                recipients.append(admin.email)
                logger.info(f"✅ Notificación enviada a admin {admin.email} para application {application_id}")
                
            except Exception as e:
                failed += 1
                error_msg = f"Error enviando a {admin.email}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            "success": True,
            "emails_sent": emails_sent,
            "failed": failed,
            "recipients": recipients,
            "errors": errors if errors else None,
            "message": f"Notificaciones enviadas a admins: {emails_sent} exitosas, {failed} fallidas"
        }
        
    except Application.DoesNotExist:
        logger.error(f"Application {application_id} no existe")
        return {
            "success": False,
            "emails_sent": 0,
            "failed": 0,
            "recipients": [],
            "message": "Aplicación no encontrada"
        }
    except Exception as e:
        logger.error(f"Error general en notify_new_application: {str(e)}")
        return {
            "success": False,
            "emails_sent": 0,
            "failed": 0,
            "recipients": [],
            "message": f"Error: {str(e)}"
        }
