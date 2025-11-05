#!/usr/bin/env python3
"""
Reset Google Sheets Script
===========================

Este script resetea las hojas de datos del Google Sheet del Newsletter Bot,
manteniendo las fuentes y temas configurados, pero eliminando todas las
noticias procesadas y newsletters generados.

IMPORTANTE: Este script requiere confirmación explícita antes de ejecutar.
"""
import logging
import sys
from typing import List

from config import settings
from src.google_sheets import GoogleSheetsClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def confirm_reset() -> bool:
    """
    Pedir confirmación al usuario antes de resetear

    Returns:
        True si el usuario confirma, False en caso contrario
    """
    print("\n" + "=" * 80)
    print("⚠️  ADVERTENCIA: RESETEAR GOOGLE SHEET")
    print("=" * 80)
    print("\nEsta operación eliminará:")
    print("  • Todas las noticias procesadas")
    print("  • Todos los newsletters generados")
    print("\nEsta operación NO eliminará:")
    print("  • Las fuentes configuradas")
    print("  • Los temas configurados")
    print("\n" + "=" * 80)

    # Primera confirmación
    respuesta1 = input("\n¿Estás seguro de que deseas continuar? (escribe 'SI' para confirmar): ").strip()

    if respuesta1 != 'SI':
        print("\n❌ Operación cancelada.")
        return False

    # Segunda confirmación
    print("\n⚠️  ÚLTIMA ADVERTENCIA: Esta acción NO se puede deshacer.")
    respuesta2 = input("Confirma nuevamente escribiendo 'RESETEAR': ").strip()

    if respuesta2 != 'RESETEAR':
        print("\n❌ Operación cancelada.")
        return False

    return True


def reset_sheet(client: GoogleSheetsClient, sheet_name: str, headers: List[str]) -> bool:
    """
    Resetear una hoja específica eliminando todo excepto el encabezado

    Args:
        client: Cliente de Google Sheets
        sheet_name: Nombre de la hoja a resetear
        headers: Encabezados de la hoja

    Returns:
        True si se reseteo exitosamente, False en caso contrario
    """
    try:
        logger.info(f"Reseteando hoja: {sheet_name}")

        worksheet = client.spreadsheet.worksheet(sheet_name)

        # Obtener el número de filas actuales
        all_values = worksheet.get_all_values()
        num_rows = len(all_values)

        if num_rows <= 1:
            logger.info(f"  ✓ La hoja '{sheet_name}' ya está vacía")
            return True

        # Limpiar todo el contenido
        worksheet.clear()

        # Restaurar los encabezados
        worksheet.append_row(headers)

        logger.info(f"  ✓ Hoja '{sheet_name}' reseteada exitosamente (eliminadas {num_rows - 1} filas)")
        return True

    except Exception as e:
        logger.error(f"  ✗ Error al resetear la hoja '{sheet_name}': {e}")
        return False


def reset_google_sheets():
    """
    Función principal para resetear las hojas de Google Sheets
    """
    print("\n" + "=" * 80)
    print("RESET GOOGLE SHEETS - NEWSLETTER BOT")
    print("=" * 80)

    # Pedir confirmación
    if not confirm_reset():
        sys.exit(0)

    print("\n" + "=" * 80)
    print("Iniciando proceso de reset...")
    print("=" * 80 + "\n")

    try:
        # Inicializar cliente
        logger.info("Conectando a Google Sheets...")
        client = GoogleSheetsClient()
        logger.info(f"✓ Conectado a: {client.spreadsheet.title}\n")

        # Definir las hojas a resetear
        sheets_to_reset = [
            {
                'name': settings.SHEET_PROCESSED_NEWS,
                'headers': [
                    'fecha_publicacion', 'titulo', 'fuente', 'tema', 'contenido_completo',
                    'contenido_truncado', 'url_original', 'url_sin_paywall', 'fecha_fetch', 'hash_contenido'
                ]
            },
            {
                'name': settings.SHEET_NEWSLETTERS,
                'headers': ['fecha_generacion', 'contenido', 'num_articulos', 'temas_cubiertos']
            }
        ]

        # Resetear cada hoja
        success_count = 0
        for sheet_config in sheets_to_reset:
            if reset_sheet(client, sheet_config['name'], sheet_config['headers']):
                success_count += 1

        # Resumen
        print("\n" + "=" * 80)
        if success_count == len(sheets_to_reset):
            print("✅ RESET COMPLETADO EXITOSAMENTE")
            print("=" * 80)
            print(f"\nHojas reseteadas: {success_count}/{len(sheets_to_reset)}")
            print("\nLas siguientes hojas han sido limpiadas:")
            for sheet_config in sheets_to_reset:
                print(f"  • {sheet_config['name']}")
            print("\nLas hojas de configuración (fuentes y temas) permanecen intactas.")
        else:
            print("⚠️  RESET COMPLETADO CON ERRORES")
            print("=" * 80)
            print(f"\nHojas reseteadas: {success_count}/{len(sheets_to_reset)}")
            print("\nRevisa los logs para más detalles sobre los errores.")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"\n❌ Error fatal durante el reset: {e}", exc_info=True)
        print("\n" + "=" * 80)
        print("❌ ERROR: El reset no pudo completarse")
        print("=" * 80)
        print(f"\nError: {e}")
        print("=" * 80 + "\n")
        sys.exit(1)


def main():
    """Punto de entrada principal"""
    try:
        reset_google_sheets()
    except KeyboardInterrupt:
        print("\n\n❌ Operación cancelada por el usuario")
        sys.exit(0)


if __name__ == '__main__':
    main()
