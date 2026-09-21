from database import engine, Base, SessionLocal
import models

def setup():
    # 1. Crear todas las tablas en el archivo sello.db
    print("Creando tablas en la base de datos...")
    Base.metadata.create_all(bind=engine)

    # 2. Insertar un comercio de prueba inicial
    db = SessionLocal()
    existing_business = db.query(models.Business).filter(models.Business.slug == "demo-cafe").first()
    
    if not existing_business:
        demo_business = models.Business(
            name="Café Demo Sello",
            slug="demo-cafe"
        )
        db.add(demo_business)
        db.commit()
        db.refresh(demo_business)
        print(f"Comercio de prueba creado:")
        print(f"-> Nombre: {demo_business.name}")
        print(f"-> ID: {demo_business.id}")
        print(f"-> Slug: {demo_business.slug}")
    else:
        print(f"El comercio '{existing_business.name}' ya existe en la base de datos.")
    
    db.close()

if __name__ == "__main__":
    setup()