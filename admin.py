"""
Herramienta de línea de comandos para el Super Admin.
Permite crear comercios y definir la clave de caja (/pos) de cada uno sin exponer endpoints.

Uso:
    python admin.py comercios
    python admin.py pendientes
    python admin.py aprobar <slug>
    python admin.py suspender <slug>
    python admin.py crear-comercio "Cafetería Roma" [slug]
    python admin.py clave-pos <slug>
    python admin.py plantilla-wallet
"""

import getpass
import sys
from database import setup_database, SessionLocal
import models
from auth import hash_password, MIN_PASSWORD_LENGTH
from GoogleWallet import MI_ISSUER_ID, apply_class_template
from routers.businesses import generate_slug


STATUS_LABELS = {"pending": "PENDIENTE", "active": "activo", "suspended": "SUSPENDIDO"}


def list_businesses(db, only_status: str | None = None):
    query = db.query(models.Business).order_by(models.Business.created_at)
    if only_status:
        query = query.filter(models.Business.status == only_status)

    businesses = query.all()
    if not businesses:
        print("No hay comercios" + (" pendientes" if only_status == "pending" else ""))
    for b in businesses:
        has_password = "con clave" if b.pos_credential else "SIN clave"
        status_label = STATUS_LABELS.get(b.status, b.status)
        email = b.contact_email or "sin email"
        print(f"- {b.slug:<25} {b.name}  [{status_label}]  ({has_password}, {email})  registro: /c/{b.slug}")


def set_status(db, slug: str, new_status: str):
    business = db.query(models.Business).filter(models.Business.slug == slug).first()
    if not business:
        sys.exit(f"No existe el comercio '{slug}'. Mirá la lista con: python admin.py comercios")

    business.status = new_status
    db.commit()
    print(f"{business.name} ahora está {STATUS_LABELS[new_status]}.")
    if new_status == "active":
        if business.contact_email:
            print(f"Avisale a {business.contact_email} que ya puede usar /pos y compartir /c/{business.slug}")
        if not business.pos_credential:
            print(f"Ojo: no tiene clave de caja. Definila con: python admin.py clave-pos {business.slug}")


def create_business(db, name: str, slug: str | None):
    slug = slug or generate_slug(name)
    if db.query(models.Business).filter(models.Business.slug == slug).first():
        sys.exit(f"Ya existe un comercio con el slug '{slug}'")

    db.add(models.Business(name=name, slug=slug))
    db.commit()
    print(f"Comercio creado: {name} ({slug})")
    print(f"Link de registro para sus clientes: /c/{slug}")
    print(f"Ahora definile la clave de caja con: python admin.py clave-pos {slug}")


def set_pos_password(db, slug: str):
    business = db.query(models.Business).filter(models.Business.slug == slug).first()
    if not business:
        sys.exit(f"No existe el comercio '{slug}'. Mirá la lista con: python admin.py comercios")

    password = getpass.getpass(f"Nueva clave de caja para {business.name}: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"La clave tiene que tener al menos {MIN_PASSWORD_LENGTH} caracteres")
    if getpass.getpass("Repetila: ") != password:
        sys.exit("Las claves no coinciden")

    if business.pos_credential:
        business.pos_credential.password_hash = hash_password(password)
    else:
        db.add(models.PosCredential(business_id=business.id, password_hash=hash_password(password)))
    db.commit()
    print(f"Clave de caja guardada para {business.name}. Las cajas que estaban abiertas van a tener que volver a entrar.")


def main():
    setup_database()
    args = sys.argv[1:]
    db = SessionLocal()
    try:
        if args == ["comercios"]:
            list_businesses(db)
        elif args == ["pendientes"]:
            list_businesses(db, only_status="pending")
        elif len(args) == 2 and args[0] == "aprobar":
            set_status(db, args[1], "active")
        elif len(args) == 2 and args[0] == "suspender":
            set_status(db, args[1], "suspended")
        elif len(args) in (2, 3) and args[0] == "crear-comercio":
            create_business(db, args[1], args[2] if len(args) == 3 else None)
        elif args == ["plantilla-wallet"]:
            print(apply_class_template(MI_ISSUER_ID))
        elif len(args) == 2 and args[0] == "clave-pos":
            set_pos_password(db, args[1])
        else:
            print(__doc__)
    finally:
        db.close()


if __name__ == "__main__":
    main()
