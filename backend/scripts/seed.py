from app.core.config import get_settings
from app.database.session import SessionLocal, initialize_database
from app.modules.auth.service import seed_initial_admin
from app.modules.products.service import seed_demo_products


def main() -> None:
    initialize_database()
    with SessionLocal() as session:
        seed_demo_products(session)
        admin = seed_initial_admin(session, get_settings())
    if admin:
        print(f"Seed concluído; administrador disponível em {admin.email}")
    else:
        print("Seed de produtos concluído; ADMIN_INITIAL_EMAIL/PASSWORD não configurados")


if __name__ == "__main__":
    main()
