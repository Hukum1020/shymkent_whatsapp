import os
import time
import qrcode
import json
import traceback
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, send_from_directory
from twilio.rest import Client
from weasyprint import HTML
from pdf2image import convert_from_path
import threading

app = Flask(__name__)

# Twilio config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = 'whatsapp:+14155238886'

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Google Sheets config
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

if not SPREADSHEET_ID or not CREDENTIALS_JSON:
    raise ValueError("SPREADSHEET_ID или GOOGLE_CREDENTIALS_JSON не найдены")

creds_dict = json.loads(CREDENTIALS_JSON)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n").strip()
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

def html_to_image(html_path, image_path):
    temp_pdf = image_path.replace('.png', '.pdf')
    HTML(html_path).write_pdf(temp_pdf)
    images = convert_from_path(temp_pdf)
    images[0].save(image_path, 'PNG')

def send_whatsapp(phone, image_filename):
    try:
        url = f"https://yourdomain.kz/qrcodes/{image_filename}"
        message = twilio_client.messages.create(
            from_=TWILIO_FROM,
            to=f"whatsapp:{phone}",
            body="Привет! Вот твой персональный QR-код для участия 🚁",
            media_url=[url]
        )
        print(f"✅ WhatsApp отправлено на {phone}")
        return True
    except Exception as e:
        print(f"❌ Ошибка WhatsApp: {e}")
        traceback.print_exc()
        return False

def process_new_guests():
    try:
        all_values = sheet.get_all_values()
        for i in range(1, len(all_values)):
            row = all_values[i]
            if len(row) < 10:
                continue

            name, email, phone, status, language = row[0], row[1], row[2], row[8], row[3].strip().lower()

            if not name or not phone or not email or status.strip().lower() == "done":
                continue

            qr_data = f"Name: {name}\nPhone: {phone}\nEmail: {email}"
            os.makedirs("qrcodes", exist_ok=True)
            qr_filename = f"qrcodes/{email.replace('@', '_')}.png"
            qr = qrcode.make(qr_data)
            qr.save(qr_filename)

            html_template_path = f"shym{language}.html"
            img_filename = qr_filename.replace(".png", "_full.png")
            html_to_image(html_template_path, img_filename)

            whatsapp_sent = send_whatsapp(phone, os.path.basename(img_filename))

            if whatsapp_sent:
                sheet.update_cell(i+1, 9, "Done")

            time.sleep(1)

    except Exception as e:
        print(f"[Ошибка] при обработке гостей: {e}")
        traceback.print_exc()

def background_task():
    while True:
        try:
            process_new_guests()
        except Exception as e:
            print(f"[Ошибка] {e}")
        time.sleep(15)

@app.route('/qrcodes/<path:filename>')
def serve_qr_image(filename):
    return send_from_directory('qrcodes', filename)

@app.route("/")
def home():
    return "WhatsApp QR Code Sender is running!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=background_task, daemon=True).start()
    app.run(host="0.0.0.0", port=port)
