# set_webhook.py

import httpx

# Datos fijos de tu .env ya sustituidos
TELEGRAM_BOT_TOKEN = "8432104323:AAELC_M4AYlv8tXbpOQlnWQiiMI8AFJqT1U"
PUBLIC_BASE_URL = "https://nutricoach-production-ee6b.up.railway.app"

def main():
    webhook_url = f"{PUBLIC_BASE_URL.rstrip('/')}/webhook"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"

    print(f"➡️ Configurando webhook en: {webhook_url}")

    payload = {"url": webhook_url}

    try:
        r = httpx.post(api_url, json=payload, timeout=10)
        r.raise_for_status()
        print("✅ Respuesta Telegram:", r.json())
    except Exception as e:
        print("❌ Error configurando webhook:", e)


if __name__ == "__main__":
    main()
