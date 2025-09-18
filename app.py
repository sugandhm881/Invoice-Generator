import os
import json
import logging
from datetime import date
from fpdf import FPDF
from flask import Flask, request, send_file, jsonify, render_template
import io
from dotenv import load_dotenv

# ------------------ Load .env ------------------
load_dotenv()

# ------------------ CONFIG ------------------
CLIENTS_FILE = "clients.json"
INVOICES_FILE = "invoices.json"
INVOICE_COUNTER_FILE = "invoice_counter.json"
SIGNATURE_IMAGE = r"Signatory.jpg"
CALIBRI_FONT_PATH = "CALIBRI.TTF"

app = Flask(__name__)

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
    
    def two_digit(n):
        if n < 20:
            return units[n]
        else:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 else "")
    
    def three_digit(n):
        h = n // 100
        r = n % 100
        if h and r:
            return units[h] + " Hundred " + two_digit(r)
        elif h:
            return units[h] + " Hundred"
        else:
            return two_digit(r)
    
    n = int(number)
    paise = int(round((number - n) * 100))
    
    words = ""
    
    crore = n // 10000000
    n %= 10000000
    if crore:
        words += three_digit(crore) + " Crore "
    
    lakh = n // 100000
    n %= 100000
    if lakh:
        words += three_digit(lakh) + " Lakh "
    
    thousand = n // 1000
    n %= 1000
    if thousand:
        words += three_digit(thousand) + " Thousand "
    
    if n:
        words += three_digit(n)
    
    words = words.strip()
    
    if paise:
        words += f" and {two_digit(paise)} Paise"
    
    return words + " Only"


# ------------------ PDF Generation ------------------
def generate_pdf(invoice_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Calibri", "", CALIBRI_FONT_PATH, uni=True)
    pdf.add_font("Calibri", "B", CALIBRI_FONT_PATH, uni=True)

    margin = 15
    page_width = pdf.w - 2 * margin

    # Header
    pdf.set_font("Calibri", "B", 20)
    pdf.cell(page_width, 10, "MB COLLECTION", ln=True, align='C')
    pdf.set_font("Calibri", "B", 14)
    pdf.cell(page_width, 8, "Tax Invoice", ln=True, align='C')
    pdf.set_font("Calibri", "", 10)
    pdf.cell(page_width, 5, "H.No 3A Shri Krishana Vatika, Sudamapuri, Vijaynagar, Ghaziabad, Uttar Pradesh - 201001", ln=True, align='C')
    pdf.cell(page_width, 5, "Phone: +91-8651537856 | GSTIN: 09ENEPM4809Q1Z8", ln=True, align='C')
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

    # Invoice info
    pdf.set_xy(140, 65)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(0, 5, f"Invoice No: {invoice_data['bill_no']}", ln=True)
    pdf.set_x(140)
    pdf.cell(0, 5, f"Date: {invoice_data['invoice_date']}", ln=True)

    pdf.ln(10)
    pdf.line(margin, pdf.get_y(), pdf.w - margin, pdf.get_y())

    # Table Header
    pdf.set_y(pdf.get_y() + 5)
    pdf.set_fill_color(200, 200, 200)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(120, 8, "Particulars", border=1, align='C', fill=True)
    pdf.cell(30, 8, "HSN", border=1, align='C', fill=True)
    pdf.cell(40, 8, "Amount", border=1, align='C', fill=True)
    pdf.ln()

    # Table Row
    pdf.set_font("Calibri", "", 10)
    pdf.cell(120, 8, invoice_data['particulars'], border=1)
    pdf.cell(30, 8, "998222", border=1, align='C')
    pdf.cell(40, 8, f"{invoice_data['amount']:.2f}", border=1, align='R')
    pdf.ln()

    # Totals Table
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(150, 6, "Sub Total", border=1)
    pdf.cell(40, 6, f"{invoice_data['sub_total']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.cell(150, 6, "IGST @18%", border=1)
    pdf.cell(40, 6, f"{invoice_data['igst']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.cell(150, 6, "CGST @9%", border=1)
    pdf.cell(40, 6, f"{invoice_data['cgst']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.cell(150, 6, "SGST @9%", border=1)
    pdf.cell(40, 6, f"{invoice_data['sgst']:.2f}", border=1, align='R')
    pdf.ln()
    pdf.cell(150, 6, "Grand Total", border=1)
    pdf.cell(40, 6, f"{invoice_data['grand_total']:.2f}", border=1, align='R')
    pdf.ln(10)

    # Amount in words
    pdf.set_font("Calibri", "", 10)
    pdf.multi_cell(0, 6, f"Rupees: {convert_to_words(invoice_data['grand_total'])}")

    # Bank Details
    pdf.cell(0, 5, "Bank Name: Yes Bank", ln=True)
    pdf.cell(0, 5, "Account Holder Name: MB Collection", ln=True)
    pdf.cell(0, 5, "Account No: 003861900014956", ln=True)
    pdf.cell(0, 5, "IFSC Code: YESB0000038", ln=True)

    pdf.ln(15)
    pdf.set_font("Calibri", "B", 10)
    pdf.cell(0, 5, "For MB COLLECTION", ln=True, align='R')

    if os.path.exists(SIGNATURE_IMAGE):
        pdf.image(SIGNATURE_IMAGE, x=150, y=pdf.get_y(), w=40)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return io.BytesIO(pdf_bytes)


# ------------------ Routes ------------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/generate-invoice", methods=["POST"])
def handle_invoice():
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

        # GST Calculation
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
    return jsonify(load_clients())

# ------------------ Run ------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
