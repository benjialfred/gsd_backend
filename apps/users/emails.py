import os
from email.mime.image import MIMEImage
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

def send_verification_email(user, verify_url):
    subject = "Confirmez votre compte - Le Grand Salon Divin"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [user.email]
    
    first_name = user.first_name or "Cher membre"

    text_content = f"""Bonjour {first_name},

Bienvenue sur Le Grand Salon Divin.

Pour confirmer votre adresse e-mail et activer votre compte, veuillez ouvrir le lien suivant dans votre navigateur :
{verify_url}

Ce lien est sécurisé et valable pendant 48 heures.
Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer ce message.

L'équipe du Grand Salon Divin
"""

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confirmation de compte - Le Grand Salon Divin</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F7F5F0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F7F5F0; padding: 40px 10px;">
        <tr>
            <td align="center">
                <!-- Main Container -->
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.06); border: 1px solid #EAE6DE;">
                    <!-- Header with Navy & Logo -->
                    <tr>
                        <td align="center" style="background: linear-gradient(135deg, #1A3A5C 0%, #0d1e30 100%); padding: 40px 30px; text-align: center;">
                            <img src="cid:gsd_logo" alt="Le Grand Salon Divin" width="160" style="display: block; margin: 0 auto; max-width: 160px; height: auto;" />
                            <p style="color: #C9A84C; font-size: 11px; text-transform: uppercase; letter-spacing: 3px; margin-top: 18px; margin-bottom: 0; font-weight: 600;">
                                Rencontres & Alliances Chrétiennes
                            </p>
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 40px 36px 30px 36px;">
                            <h2 style="color: #1A3A5C; font-size: 22px; font-weight: 600; margin-top: 0; margin-bottom: 20px; font-family: Georgia, serif;">
                                Bienvenue dans l'Alliance, {first_name} ✨
                            </h2>
                            <p style="color: #4A5568; font-size: 15px; line-height: 1.7; margin-top: 0; margin-bottom: 24px;">
                                Nous sommes très honorés de vous compter parmi nous. Pour finaliser la création de votre espace et débuter vos découvertes guidées par la foi, veuillez valider votre adresse e-mail.
                            </p>

                            <!-- CTA Button -->
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 32px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{verify_url}" target="_blank" style="background: linear-gradient(135deg, #C9A84C 0%, #B8973B 100%); color: #1A3A5C; font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; text-decoration: none; padding: 16px 36px; border-radius: 12px; display: inline-block; box-shadow: 0 6px 18px rgba(201, 168, 76, 0.35);">
                                            Confirmer mon inscription
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Fallback Link -->
                            <p style="color: #718096; font-size: 12px; line-height: 1.6; margin-top: 30px; margin-bottom: 10px; border-top: 1px solid #EDF2F7; padding-top: 24px;">
                                Si le bouton ne s'affiche pas correctement, vous pouvez copier et coller ce lien dans votre navigateur :
                            </p>
                            <p style="margin: 0; word-break: break-all;">
                                <a href="{verify_url}" target="_blank" style="color: #C9A84C; font-size: 12px; text-decoration: underline;">
                                    {verify_url}
                                </a>
                            </p>
                        </td>
                    </tr>

                    <!-- Security Notice & Footer -->
                    <tr>
                        <td style="background-color: #FCFBF9; padding: 24px 36px; border-top: 1px solid #EAE6DE; text-align: center;">
                            <p style="color: #A0AEC0; font-size: 11px; line-height: 1.5; margin: 0 0 10px 0;">
                                Ce lien est valable pendant 48 heures. Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail.
                            </p>
                            <p style="color: #718096; font-size: 11px; margin: 0; font-weight: 500;">
                                © 2026 Le Grand Salon Divin. Tous droits réservés.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=to_email,
        headers={'Reply-To': from_email}
    )
    msg.attach_alternative(html_content, "text/html")

    # Attach embedded logo image with Content-ID
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo.png')
    if os.path.exists(logo_path):
        try:
            with open(logo_path, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<gsd_logo>')
                img.add_header('Content-Disposition', 'inline', filename='logo.png')
                msg.attach(img)
        except Exception as e:
            print("Could not attach embedded logo:", e)

    msg.send(fail_silently=False)
