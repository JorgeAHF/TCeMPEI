"""Comandos CLI auxiliares para la administración de TCeMPEI."""

import argparse

from .auth_service import ensure_default_admin


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI de mantenimiento para TCeMPEI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    admin_parser = subparsers.add_parser(
        "ensure-default-admin",
        help="Crea un usuario administrador por defecto si aún no existe",
    )
    admin_parser.add_argument(
        "--email",
        help="Correo del administrador por defecto (por defecto usa DEFAULT_ADMIN_EMAIL)",
    )
    admin_parser.add_argument(
        "--password",
        help="Contraseña del administrador por defecto (por defecto usa DEFAULT_ADMIN_PASSWORD)",
    )

    args = parser.parse_args()

    if args.command == "ensure-default-admin":
        created, message = ensure_default_admin(email=args.email, password=args.password)
        print(message)
        return


if __name__ == "__main__":
    main()
