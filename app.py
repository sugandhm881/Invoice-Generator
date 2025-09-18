# app.py
import os
import io
import json
import logging
from datetime import date
from urllib.parse import unquote

from flask import (
    Flask, request, send_file, send_from_directory, jsonify,
    render_template, redirect, url_for
)
from flask_login import (
    LoginManager, UserMixin, login_user, login_required, logout_user, current_user
)
from dotenv import load_dotenv
from fpdf import FPDF

# ------------------ Load .env ------------------
load_dotenv()

# ------------------ CONFIG ------------------
CLIENTS_FILE = "clients.json"
INVOICES_FILE = "invoices.json"
INVOICE_COUNTER_FILE = "invoice_counter.json"
SIGNATURE_IMAGE = r"Signatory.jpg"
CALIBRI_FONT_PATH = "CALIBRI.TTF"  # ensure this file exists or change to a built-in font
INVOICE_PDF_FOLDER = "generated_invoices"
os.makedirs(INVOICE_PDF_FOLDER, exist_ok=True)

# ------------------ FLASK APP ------------------
app = Flask(__name__, static_folder='.', static_url_path='')  # static files served from project root
app.secret_key = os.getenv("SECRET_KEY", "change_this_secret")

# ------------------ LOGGING ------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)


# ----- Flask-Login Setup -----
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Single user credentials (from .env or default)
AUTH_USERNAME = os.getenv("LOGIN_USER", "admin")
AUTH_PASSWORD = os.getenv("LOGIN_PASS", "password")

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# ------------------ Helpers ------------------
def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error reading {filename}: {e}")
            return default
    return default

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_clients():
    return load_json(CLIENTS_FILE, {})

def save_clients(clients):
    save_json(clients, CLIENTS_FILE)

def load_invoices():
    return load_json(INVOICES_FILE, [])

def save_invoices(invoices):
    save_json(invoices, INVOICES_FILE)

# ------------------ Number to words (Indian) ------------------
def convert_to_words(number):
    units = ["","One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten",
             "Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"]
    tens = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"]

    def two_digit(n):
        if n < 20:
            return units[n]
        else:
            return tens[n//10] + (" " + units[n%10] if n%10 else "")

    def three_digit(n):
        s = ""
        if n >= 100:
            s += units[n//100] + " Hundred"
            if n % 100:
                s += " "
        if n % 100:
            s += two_digit(n%100)
        return s

    n = int(abs(number))
    paise = round((abs(number) - n) * 100)

    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    hundred = n

    parts = []
    if crore:
        parts.append(three_digit(crore) + " Crore")
    if lakh:
        parts.append(three_digit(lakh) + " Lakh")
    if thousand:
        parts.append(three_digit(thousand) + " Thousand")
    if hundred:
        parts.append(three_digit(hundred))

    if not parts:
        words = "Zero"
    else:
        words = " ".join(parts)

    if paise:
        words += f" and {two_digit(paise)} Paise"

    return words + " Only"

def generate_pdf(invoice_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Calibri", "", CALIBRI_FONT_PATH, uni=True)
    pdf.add_font("Calibri", "B", CALIBRI_FONT_PATH, uni=True)

    margin = 15
    page_width = pdf.w - 2 * margin

    # Header
    pdf.set_font("Calibri", "B", 22)
    pdf.set_text_color(255, 165, 0)  # Orange
    pdf.cell(page_width, 10, "MB COLLECTION", ln=True, align='C')
    pdf.set_font("Calibri", "B", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(page_width, 8, "Tax Invoice", ln=True, align='C')
    pdf.set_font("Calibri", "", 10)
    pdf.multi_cell(page_width, 5, "H.No 3A Shri Krishana Vatika, Sudamapuri, Vijaynagar, Ghaziabad, Uttar Pradesh - 201001\nPhone: +91-8651537856 | E-mail: skpa.avkashmishra@gmail.com\nGSTIN: 09ENEPM4809Q1Z8", align='C')
    pdf.ln(5)
    pdf.line(margin, pdf.get_y(), pdf.w - margin, pdf.get_y())

    # Bill To
    pdf.ln(5)
    pdf.set_font("Calibri", "B", 12)
    pdf.cell(0, 5, "Bill To:", ln=True)
    pdf.set_font("Calibri", "", 10)
    pdf.cell(0, 5, invoice_data['client_name'], ln=True)
    pdf.cell(0, 5, invoice_data['client_address1'], ln=True)
    pdf.cell(0, 5, invoice_data['client_address2'], ln=True)
    pdf.cell(0, 5, f"GSTIN: {invoice_data['client_gstin']}", ln=True)
    pdf.set_xy(140, 65)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(0, 5, f"Invoice No: {invoice_data['bill_no']}", ln=True)
    pdf.set_x(140)
    pdf.cell(0, 5, f"Date: {invoice_data['invoice_date']}", ln=True)

    pdf.ln(10)
    pdf.set_fill_color(255, 204, 153)  # Light orange header
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(130, 8, "Particulars", border=1, align='C', fill=True)
    pdf.cell(30, 8, "HSN", border=1, align='C', fill=True)
    pdf.cell(30, 8, "Amount", border=1, align='C', fill=True)
    pdf.ln()

    # Table rows
    pdf.set_font("Calibri", "", 10)
    particulars = invoice_data['particulars'].split('\n')
    hsn_list = ["998222"] * len(particulars)
    amounts = [invoice_data['amount'] / len(particulars)] * len(particulars)  # evenly split if needed

    for i in range(len(particulars)):
        if i % 2 == 0:
            pdf.set_fill_color(255, 255, 204)  # Light yellow
        else:
            pdf.set_fill_color(255, 255, 230)  # Slightly different yellow
        pdf.cell(130, 7, particulars[i], border=1, fill=True)
        pdf.cell(30, 7, hsn_list[i], border=1, align='C', fill=True)
        pdf.cell(30, 7, f"{amounts[i]:.2f}", border=1, align='R', fill=True)
        pdf.ln()

    # Totals
    pdf.set_font("Calibri", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(160, 7, "Sub Total", border=1, align='R', fill=True)
    pdf.cell(30, 7, f"{invoice_data['sub_total']:.2f}", border=1, align='R', fill=True)
    pdf.ln()
    pdf.cell(160, 7, "IGST @18%", border=1, align='R', fill=True)
    pdf.cell(30, 7, f"{invoice_data['igst']:.2f}", border=1, align='R', fill=True)
    pdf.ln()
    pdf.cell(160, 7, "CGST @9%", border=1, align='R', fill=True)
    pdf.cell(30, 7, f"{invoice_data['cgst']:.2f}", border=1, align='R', fill=True)
    pdf.ln()
    pdf.cell(160, 7, "SGST @9%", border=1, align='R', fill=True)
    pdf.cell(30, 7, f"{invoice_data['sgst']:.2f}", border=1, align='R', fill=True)
    pdf.ln()
    pdf.cell(160, 7, "Grand Total", border=1, align='R', fill=True)
    pdf.cell(30, 7, f"{invoice_data['grand_total']:.2f}", border=1, align='R', fill=True)
    pdf.ln(15)

    # Amount in words & bank details
    pdf.set_font("Calibri", "", 10)
    pdf.multi_cell(0, 5, f"Rupees: {convert_to_words(invoice_data['grand_total'])}\nBank Name: Yes Bank\nAccount Holder Name: MB Collection\nAccount No: 003861900014956\nIFSC Code: YESB0000038")
    pdf.ln(10)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(0, 5, "For MB COLLECTION", ln=True, align='R')

    if os.path.exists(SIGNATURE_IMAGE):
        pdf.image(SIGNATURE_IMAGE, x=150, y=pdf.get_y(), w=40)
    pdf.ln(20)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return io.BytesIO(pdf_bytes)

# ----- Routes -----

# Root route: redirect to login if not authenticated
@app.route("/", methods=["GET"])
def root():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return redirect(url_for("login"))

# Login page & POST action
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            user = User(id=username)
            login_user(user)
            return redirect(url_for("home"))
        else:
            error = "Invalid username or password"
    return render_template("login.html", error=error)

# Protected Home page
@app.route("/home", methods=["GET"])
@login_required
def home():
    return render_template("index.html")

# Logout
@app.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# Home (protected). Serves your existing index.html file — keep it where it is.
@app.route("/", methods=["GET"])
@login_required
def home():
    # index.html is expected to be in project root (same location as app.py)
    # we use send_file so you don't need to move existing index.html
    return render_template("index.html")

# Generate invoice (protected)
@app.route("/generate-invoice", methods=["POST"])
@login_required
def handle_invoice():
    try:
        data = request.json or {}
        client_name = data.get('client_name', '').strip()
        client_address1 = data.get('client_address1', '').strip()
        client_address2 = data.get('client_address2', '').strip()
        client_gstin = data.get('client_gstin', '').strip()
        particulars = data.get('particulars', '').strip()
        # support either single amount or per-item amounts list
        amounts = data.get('amounts')
        if amounts and isinstance(amounts, list):
            amount = float(sum([float(x) for x in amounts]))
        else:
            amount = float(data.get('amount', 0))

        # Save client (if new)
        clients = load_clients()
        if client_name and client_name not in clients:
            clients[client_name] = {
                'address1': client_address1,
                'address2': client_address2,
                'gstin': client_gstin
            }
            save_clients(clients)

        # Invoice counter (persisted)
        counter_data = load_json(INVOICE_COUNTER_FILE, {"counter": 0})
        counter = counter_data.get('counter', 0) + 1
        counter_data['counter'] = counter
        save_json(counter_data, INVOICE_COUNTER_FILE)
        bill_no = f"INV/{counter:04d}/25-26"

        invoice_date_str = date.today().strftime('%d-%b-%Y')
        my_gstin = "09ENEPM4809Q1Z8"

        # GST calculation
        sub_total = round(amount, 2)
        igst = cgst = sgst = 0.0
        if client_gstin and client_gstin[:2] == my_gstin[:2]:
            cgst = round(sub_total * 0.09, 2)
            sgst = round(sub_total * 0.09, 2)
        else:
            igst = round(sub_total * 0.18, 2)
        grand_total = round(sub_total + igst + cgst + sgst, 2)

        invoice_data = {
            "bill_no": bill_no,
            "invoice_date": invoice_date_str,
            "client_name": client_name,
            "client_address1": client_address1,
            "client_address2": client_address2,
            "client_gstin": client_gstin,
            "my_gstin": my_gstin,
            "particulars": particulars,
            # include both flattened amount and optional per-item amounts
            "amount": sub_total,
            "amounts": amounts if isinstance(amounts, list) else None,
            "sub_total": sub_total,
            "igst": igst,
            "cgst": cgst,
            "sgst": sgst,
            "grand_total": grand_total
        }

        invoices = load_invoices()
        invoices.append(invoice_data)
        save_invoices(invoices)

        pdf_file = generate_pdf(invoice_data)
        download_name = f"Invoice_{bill_no.replace('/','_')}.pdf"
        # Save generated pdf to disk for reference (optional)
        try:
            path = os.path.join(INVOICE_PDF_FOLDER, download_name)
            with open(path, "wb") as f:
                f.write(pdf_file.getbuffer())
            pdf_file.seek(0)
        except Exception as e:
            logging.warning(f"Could not save generated PDF to disk: {e}")

        # Return PDF with correct filename in Content-Disposition
        return send_file(pdf_file, mimetype="application/pdf", as_attachment=True, download_name=download_name)

    except Exception as e:
        logging.error(f"Error generating invoice: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Clients list (protected)
@app.route('/clients', methods=['GET'])
@login_required
def get_clients_route():
    return jsonify(load_clients())

# Invoices list for dropdown (protected)
@app.route('/invoices-list', methods=['GET'])
@login_required
def invoices_list_route():
    invoices = load_invoices()
    brief = [{
        "bill_no": inv["bill_no"],
        "date": inv.get("invoice_date"),
        "grand_total": inv.get("grand_total"),
        "client_name": inv.get("client_name")  # <-- add this
    } for inv in invoices]
    return jsonify(brief)

# Download previous invoice by bill_no (protected) - allow slashes via path:
@app.route('/download-invoice/<path:bill_no>', methods=['GET'])
@login_required
def download_invoice(bill_no):
    bill_no = unquote(bill_no)
    invoices = load_invoices()
    invoice_data = next((inv for inv in invoices if inv['bill_no'] == bill_no), None)
    if not invoice_data:
        return jsonify({"error": "Invoice not found"}), 404
    pdf_file = generate_pdf(invoice_data)
    download_name = f"Invoice_{bill_no.replace('/','_')}.pdf"
    return send_file(pdf_file, mimetype="application/pdf", as_attachment=True, download_name=download_name)

# ------------------ Run ------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)