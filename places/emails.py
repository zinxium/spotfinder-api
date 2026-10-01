"""
Emails de compte envoyés par l'API : code de réinitialisation, alertes de sécurité.

L'envoi part en arrière-plan (EMAIL_SEND_ASYNC) : la réponse HTTP n'attend pas le serveur
SMTP. Elle met donc le même temps, que le compte existe ou non (pas d'indice pour deviner
quels emails sont inscrits), et une panne d'envoi ne fait pas échouer la requête.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send(subject, body, recipient):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])
    except Exception:
        # Jamais l'adresse ni le contenu dans les journaux : le message contient un code secret
        logger.exception("Échec de l'envoi d'un email de compte")


def send_account_email(subject, body, recipient):
    """Envoie un email de compte, en arrière-plan sauf si EMAIL_SEND_ASYNC vaut False"""
    if settings.EMAIL_SEND_ASYNC:
        threading.Thread(target=_send, args=(subject, body, recipient), daemon=True).start()
    else:
        _send(subject, body, recipient)


def send_reset_code(user, code):
    minutes = settings.PASSWORD_RESET_CODE_MINUTES
    send_account_email(
        'Votre code SpotFinder',
        f"Bonjour {user.username},\n\n"
        f"Voici votre code pour choisir un nouveau mot de passe : {code}\n\n"
        f"Il est valable {minutes} minutes. Ne le communiquez à personne : "
        "l'équipe SpotFinder ne vous le demandera jamais.\n\n"
        "Vous n'êtes pas à l'origine de cette demande ? Ignorez cet email, "
        "votre mot de passe reste inchangé.",
        user.email,
    )


def send_password_changed(user):
    send_account_email(
        'Votre mot de passe SpotFinder a été modifié',
        f"Bonjour {user.username},\n\n"
        "Le mot de passe de votre compte SpotFinder vient d'être modifié. "
        "Vos autres appareils ont été déconnectés.\n\n"
        "Ce n'est pas vous ? Utilisez « Mot de passe oublié » sur l'écran de connexion "
        "pour reprendre la main sur votre compte, puis contactez le support.",
        user.email,
    )


def send_account_deleted(username, email):
    """Appelée avec les valeurs copiées avant la suppression : l'utilisateur n'existe plus"""
    send_account_email(
        'Votre compte SpotFinder a été supprimé',
        f"Bonjour {username},\n\n"
        "Votre compte SpotFinder a bien été supprimé, avec vos avis, vos favoris et vos visites. "
        "Les lieux que vous avez ajoutés restent visibles, sans votre nom.\n\n"
        "Merci d'avoir fait partie de la communauté.",
        email,
    )
