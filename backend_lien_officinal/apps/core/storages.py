from storages.backends.s3boto3 import S3Boto3Storage


class LogoStorage(S3Boto3Storage):
    """Stockage S3 des logos de pharmacie.

    Privé et à URL signée comme le stockage par défaut, mais avec une signature
    valable **7 jours** au lieu d'1h (settings.AWS_QUERYSTRING_EXPIRE). Un logo
    reste ainsi affichable pendant toute une session (barre latérale, écran de
    connexion) sans que son URL n'expire, tout en restant privé — pas d'exposition
    publique, pas de dépendance aux ACL publiques du bucket. Les objets déjà
    stockés (privés) continuent de fonctionner : seule la durée de signature change.
    """
    default_acl = 'private'
    querystring_auth = True
    querystring_expire = 7 * 24 * 3600  # 7 jours
    file_overwrite = False
