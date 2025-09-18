import json
import os
import logging
from datetime import date
from fpdf import FPDF
from flask import Flask, request, send_file, redirect, url_for, session, render_template
from flask_cors import CORS
import io

# ------------------ CONFIG ------------------
CLIENTS_FILE = "clients.json"
INVOICES_FILE = "invoices.json"
INVOICE_COUNTER_FILE = "invoice_counter.json"
SIGNATURE_IMAGE = r"Signatory.jpg"
CALIBRI_FONT_PATH = "CALIBRI.TTF"  # font in project folder

SECRET_USERNAME = "sugandhm881@gmail.com"
SECRET_PASSWORD = "Avkash@1997"
app = Flask(__name__)
app.secret_key = "YourSecretKey123=Kalkibaathai"
CORS(app)

# ------------------ LOGGING ------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler()])

# ------------------ Helpers ------------------
def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error reading {filename}: {e}")
            return default
    return default

def save_json(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def load_clients():
    return load_json(CLIENTS_FILE, {})

def save_clients(clients):
    save_json(clients, CLIENTS_FILE)

def load_invoices():
    return load_json(INVOICES_FILE, [])

def save_invoices(invoices):
    save_json(invoices, INVOICES_FILE)

# ------------------ Amount in words ------------------
def convert_to_words(number):
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
             "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
             "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_group(n):
        if n < 20:
            return units[n]
        else:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 else "")

    n = int(number)
    paise = round((number - n) * 100)
    s = str(n)
    p = len(s)
    words = []

    if p >= 8:
        crores = int(s[p - 8:p - 6])
        if crores:
            words.append(convert_group(crores) + " Crore")
    if p >= 6:
        lakhs = int(s[max(0, p - 8):p - 6]) if p >= 8 else int(s[max(0, p - 6):p - 4])
        if lakhs:
            words.append(convert_group(lakhs) + " Lakh")
    if p >= 4:
        thousands = int(s[max(0, p - 6):p - 4]) if p >= 6 else int(s[max(0, p - 4):p - 2])
        if thousands:
            words.append(convert_group(thousands) + " Thousand")
    if p >= 3:
        hundreds = int(s[max(0, p - 4):p - 3]) if p >= 4 else int(s[max(0, p - 3):p - 2])
        if hundreds:
            words.append(convert_group(hundreds) + " Hundred")

    remaining = int(s[-2:]) if p >= 2 else int(s)
    if remaining:
        words.append(convert_group(remaining))

    result = " ".join(words)
    if paise:
        result += f" and {convert_group(paise)} Paise"
    return result + " Only"

# ------------------ PDF Generation ------------------
def generate_pdf(invoice_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Calibri", "", CALIBRI_FONT_PATH, uni=True)
    pdf.add_font("Calibri", "B", CALIBRI_FONT_PATH, uni=True)

    pdf.set_font("Calibri", "B", 22)
    margin = 15
    page_width = pdf.w - 2 * margin

    # Header
    pdf.cell(page_width, 10, "MB COLLECTION", ln=True, align='C')
    pdf.set_font("Calibri", "B", 14)
    pdf.cell(page_width, 8, "Tax Invoice", ln=True, align='C')
    pdf.set_font("Calibri", "", 10)
    pdf.cell(page_width, 5, "H.No 3A Shri Krishana Vatika, Sudamapuri, Vijaynagar, Ghaziabad, Uttar Pradesh - 201001", ln=True, align='C')
    pdf.cell(page_width, 5, "Phone: +91-8651537856 | E-mail: skpa.avkashmishra@gmail.com", ln=True, align='C')
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

    # Invoice info
    pdf.set_xy(140, 65)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(0, 5, f"Invoice No: {invoice_data['bill_no']}", ln=True)
    pdf.set_x(140)
    pdf.cell(0, 5, f"Date: {invoice_data['invoice_date']}", ln=True)
    pdf.set_x(140)
    pdf.cell(0, 5, f"GSTIN: {invoice_data['client_gstin']}", ln=True)

    pdf.ln(5)
    pdf.line(margin, pdf.get_y(), pdf.w - margin, pdf.get_y())

    # Table header
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Calibri", "B", 10)
    pdf.set_y(pdf.get_y() + 5)
    pdf.cell(130, 7, "Particulars", border=1, align='C', fill=True)
    pdf.cell(20, 7, "HSN", border=1, align='C', fill=True)
    pdf.cell(35, 7, "Amount", border=1, align='C', fill=True)
    pdf.ln()

    # Table data
    pdf.set_font("Calibri", "", 10)
    pdf.multi_cell(130, 5, invoice_data['particulars'], border=1)
    y_start = pdf.get_y() - 5
    pdf.set_xy(145, y_start)
    pdf.cell(20, 10, "998222", border=1, align='C')
    pdf.cell(35, 10, f"{invoice_data['amount']:.2f}", border=1, align='R')
    pdf.ln(20)

    # Totals (aligned with table header)
    pdf.set_x(145)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(20, 5, "Sub Total", border=1)
    pdf.cell(35, 5, f"{invoice_data['sub_total']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.set_x(145)
    pdf.cell(20, 5, "IGST @18%", border=1)
    pdf.cell(35, 5, f"{invoice_data['igst']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.set_x(145)
    pdf.cell(20, 5, "CGST @9%", border=1)
    pdf.cell(35, 5, f"{invoice_data['cgst']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.set_x(145)
    pdf.cell(20, 5, "SGST @9%", border=1)
    pdf.cell(35, 5, f"{invoice_data['sgst']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.set_x(145)
    pdf.cell(20, 5, "Grand Total", border=1)
    pdf.cell(35, 5, f"{invoice_data['grand_total']:.2f}", border=1, align='R')
    pdf.ln(15)

    # Amount in words & bank details
    pdf.set_font("Calibri", "", 10)
    pdf.cell(0, 5, f"Rupees: {convert_to_words(invoice_data['grand_total'])}", ln=True)
    pdf.cell(0, 5, "Bank Name: Yes Bank", ln=True)
    pdf.cell(0, 5, "Account Holder Name: MB Collection", ln=True)
    pdf.cell(0, 5, "Account No: 003861900014956", ln=True)
    pdf.cell(0, 5, "IFSC Code: YESB0000038", ln=True)
    pdf.ln(15)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(0, 5, "For MB COLLECTION", ln=True, align='R')

    if os.path.exists(SIGNATURE_IMAGE):
        pdf.image(SIGNATURE_IMAGE, x=150, y=pdf.get_y(), w=40)
    pdf.ln(20)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return io.BytesIO(pdf_bytes)

# ------------------ Routes ------------------
@app.route("/", methods=["GET"])
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return send_file("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == SECRET_USERNAME and password == SECRET_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            error = "Invalid username or password"
    return render_template("login.html", error=error)

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/generate-invoice", methods=["POST"])
def handle_invoice():
    if not session.get("logged_in"):
        return {"error": "Unauthorized"}, 401
    try:
        data = request.json
        client_name = data.get('client_name')
        client_address1 = data.get('client_address1')
        client_address2 = data.get('client_address2')
        client_gstin = data.get('client_gstin')
        particulars = data.get('particulars')
        amount = float(data.get('amount'))

        # Save client
        clients = load_clients()
        if client_name not in clients:
            clients[client_name] = {
                'address1': client_address1,
                'address2': client_address2,
                'gstin': client_gstin
            }
            save_clients(clients)

        # Invoice number
        counter_data = load_json(INVOICE_COUNTER_FILE, {"counter": 0})
        counter = counter_data.get('counter', 0) + 1
        counter_data['counter'] = counter
        save_json(counter_data, INVOICE_COUNTER_FILE)
        bill_no = f"INV/{counter:04d}/24-25"

        invoice_date_str = date.today().strftime('%d-%b-%Y')
        my_gstin = "09ENEPM4809Q1Z8"

        # GST
        sub_total = amount
        igst, cgst, sgst = 0, 0, 0
        if client_gstin[:2] == my_gstin[:2]:
            cgst = sub_total * 0.09
            sgst = sub_total * 0.09
        else:
            igst = sub_total * 0.18
        grand_total = sub_total + igst + cgst + sgst

        invoice_data = {
            "bill_no": bill_no,
            "invoice_date": invoice_date_str,
            "client_name": client_name,
            "client_address1": client_address1,
            "client_address2": client_address2,
            "client_gstin": client_gstin,
            "my_gstin": my_gstin,
            "particulars": particulars,
            "amount": amount,
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
        return send_file(pdf_file, mimetype="application/pdf", as_attachment=True,
                         download_name=f"Invoice_{bill_no.replace('/', '_')}.pdf")

    except Exception as e:
        logging.error(f"Error generating invoice: {e}")
        return {"error": str(e)}, 500

@app.route('/clients', methods=['GET'])
def get_clients():
    if not session.get("logged_in"):
        return {"error": "Unauthorized"}, 401
    return load_clients()

# ------------------ Run ------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
