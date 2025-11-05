#!/usr/bin/env python3
"""
Setup Demo Data
Adds Financial Times source and sample topics to Google Sheets
"""
from src.google_sheets import GoogleSheetsClient

def setup_demo_data():
    """Add demo data to Google Sheets"""
    print("Connecting to Google Sheets...")
    client = GoogleSheetsClient()

    # Add Financial Times as source
    print("\nAdding Financial Times as news source...")
    try:
        client.add_source(
            nombre="Financial Times",
            url="https://www.ft.com/rss/home",
            tipo="rss",
            activo="si"
        )
        print("✓ Financial Times added")
    except Exception as e:
        print(f"Note: {e}")

    # Add sample topics
    print("\nAdding sample topics...")
    sample_topics = [
        ("1", "Economía y Finanzas", "economía, finanzas, mercados, bolsa, inversión, banco central", "Noticias sobre economía, mercados financieros, política monetaria"),
        ("2", "Política y Gobierno", "política, gobierno, elecciones, legislación, regulación", "Noticias sobre política nacional e internacional"),
        ("3", "Tecnología", "tecnología, tech, software, hardware, startups, innovación, IA", "Noticias sobre tecnología e innovación"),
        ("4", "Negocios y Empresas", "negocios, empresas, corporaciones, CEO, fusiones, adquisiciones", "Noticias sobre empresas y estrategia empresarial"),
        ("5", "Energía y Medio Ambiente", "energía, petróleo, gas, renovables, clima, sostenibilidad", "Noticias sobre energía y medio ambiente"),
    ]

    for topic_id, nombre, keywords, descripcion in sample_topics:
        try:
            client.add_topic(topic_id, nombre, keywords, descripcion)
            print(f"✓ Added topic: {nombre}")
        except Exception as e:
            print(f"Note: {e}")

    print("\n" + "=" * 80)
    print("DEMO DATA SETUP COMPLETED")
    print("=" * 80)
    print("\nYour Google Sheet now has:")
    print("  • 1 active news source (Financial Times)")
    print("  • 5 predefined topics")
    print("\nYou can now run: ./venv/bin/python main.py")
    print("=" * 80)

if __name__ == '__main__':
    setup_demo_data()
