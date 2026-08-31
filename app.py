import os, sqlite3
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, g

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = os.environ.get("DATABASE_PATH", "pharmacy.db")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    c=g.pop("db",None)
    if c: c.close()

def init_db():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin'
    );
    CREATE TABLE IF NOT EXISTS suppliers(
      id INTEGER PRIMARY KEY, company_name TEXT NOT NULL, contact_person TEXT NOT NULL,
      phone TEXT NOT NULL, email TEXT, address TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS customers(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
      email TEXT, address TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS medicines(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
      brand TEXT NOT NULL, supplier_id INTEGER NOT NULL, unit_price REAL NOT NULL,
      stock_quantity INTEGER NOT NULL, expiration_date TEXT NOT NULL,
      FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
    );
    CREATE TABLE IF NOT EXISTS sales(
      id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, medicine_id INTEGER NOT NULL,
      quantity INTEGER NOT NULL, payment_method TEXT NOT NULL, sale_date TEXT NOT NULL,
      total_amount REAL NOT NULL,
      FOREIGN KEY(customer_id) REFERENCES customers(id),
      FOREIGN KEY(medicine_id) REFERENCES medicines(id)
    );
    """)
    c.execute("INSERT OR IGNORE INTO users(id,username,password,role) VALUES(1,'admin','admin123','admin')")
    c.commit()

@app.before_request
def ensure_database():
    init_db()

def error(field,msg,status=422):
    return jsonify(status=status,error=msg,field=field),status

def login_required(f):
    @wraps(f)
    def wrap(*a,**kw):
        if "user_id" not in session: return redirect(url_for("login"))
        return f(*a,**kw)
    return wrap

def admin_required(f):
    @wraps(f)
    def wrap(*a,**kw):
        if session.get("role")!="admin":
            return jsonify(status=403,error="Not allowed"),403
        return f(*a,**kw)
    return wrap

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password","")
        row=db().execute("SELECT * FROM users WHERE username=? AND password=?",(u,p)).fetchone()
        if row:
            session.update(user_id=row["id"],username=row["username"],role=row["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    c=db()
    stats={
      "medicines":c.execute("SELECT COUNT(*) FROM medicines").fetchone()[0],
      "suppliers":c.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
      "customers":c.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
      "sales":c.execute("SELECT COALESCE(SUM(total_amount),0) FROM sales WHERE sale_date=?",(date.today().isoformat(),)).fetchone()[0],
    }
    low=c.execute("SELECT * FROM medicines WHERE stock_quantity<=10 ORDER BY stock_quantity").fetchall()
    exp=c.execute("SELECT * FROM medicines WHERE expiration_date<=date('now','+30 day') ORDER BY expiration_date").fetchall()
    recent=c.execute("""SELECT sales.*, customers.name customer_name, medicines.name medicine_name
      FROM sales JOIN customers ON customers.id=sales.customer_id JOIN medicines ON medicines.id=sales.medicine_id
      ORDER BY sales.id DESC LIMIT 5""").fetchall()
    return render_template("dashboard.html",stats=stats,low=low,exp=exp,recent=recent)

# ---------- SUPPLIERS ----------
@app.route("/suppliers",methods=["GET","POST"])
@login_required
def suppliers():
    c=db()
    if request.method=="POST":
        data={k:request.form.get(k,"").strip() for k in ["company_name","contact_person","phone","email","address"]}
        for k,label in [("company_name","Company name"),("contact_person","Contact person"),("phone","Phone"),("address","Address")]:
            if not data[k]: flash(f"{label} is required.","danger"); return redirect(url_for("suppliers"))
        c.execute("INSERT INTO suppliers(company_name,contact_person,phone,email,address) VALUES(?,?,?,?,?)",tuple(data.values())); c.commit()
        flash("Supplier added successfully.","success"); return redirect(url_for("suppliers"))
    q=request.args.get("q","")
    rows=c.execute("SELECT * FROM suppliers WHERE company_name LIKE ? OR contact_person LIKE ? ORDER BY id DESC",(f"%{q}%",f"%{q}%")).fetchall()
    return render_template("suppliers.html",rows=rows,q=q,title="Suppliers",singular="Supplier",fields=[("company_name","Company Name",True),("contact_person","Contact Person",True),("phone","Phone",True),("email","Email",False),("address","Address",True)],headers=["ID","Company","Contact Person","Phone","Email","Address"],keys=["id","company_name","contact_person","phone","email","address"],delete_base="/suppliers")

@app.route("/suppliers/<int:id>/delete",methods=["POST"])
@login_required
@admin_required
def delete_supplier(id):
    try: db().execute("DELETE FROM suppliers WHERE id=?",(id,)); db().commit(); flash("Supplier deleted.","success")
    except sqlite3.IntegrityError: flash("Cannot delete supplier while medicines use it.","danger")
    return redirect(url_for("suppliers"))

# ---------- CUSTOMERS ----------
@app.route("/customers",methods=["GET","POST"])
@login_required
def customers():
    c=db()
    if request.method=="POST":
        vals=[request.form.get(k,"").strip() for k in ["name","phone","email","address"]]
        if not vals[0] or not vals[1] or not vals[3]: flash("Name, phone and address are required.","danger")
        else: c.execute("INSERT INTO customers(name,phone,email,address) VALUES(?,?,?,?)",vals); c.commit(); flash("Customer added successfully.","success")
        return redirect(url_for("customers"))
    q=request.args.get("q","")
    rows=c.execute("SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY id DESC",(f"%{q}%",f"%{q}%")).fetchall()
    return render_template("customers.html",rows=rows,q=q,title="Customers",singular="Customer",fields=[("name","Customer Name",True),("phone","Phone",True),("email","Email",False),("address","Address",True)],headers=["ID","Name","Phone","Email","Address"],keys=["id","name","phone","email","address"],delete_base="/customers")

@app.route("/customers/<int:id>/delete",methods=["POST"])
@login_required
@admin_required
def delete_customer(id):
    try: db().execute("DELETE FROM customers WHERE id=?",(id,)); db().commit(); flash("Customer deleted.","success")
    except sqlite3.IntegrityError: flash("Cannot delete customer with sales.","danger")
    return redirect(url_for("customers"))

# ---------- MEDICINES ----------
@app.route("/medicines")
@login_required
def medicines():
    c=db(); q=request.args.get("q","")
    rows=c.execute("""SELECT medicines.*, suppliers.company_name FROM medicines JOIN suppliers ON suppliers.id=medicines.supplier_id
      WHERE medicines.name LIKE ? OR category LIKE ? ORDER BY medicines.id DESC""",(f"%{q}%",f"%{q}%")).fetchall()
    return render_template("medicines.html",rows=rows,q=q)

@app.route("/medicines/add",methods=["GET","POST"])
@login_required
def add_medicine():
    c=db(); suppliers=c.execute("SELECT * FROM suppliers ORDER BY company_name").fetchall()
    if request.method=="POST":
        name=request.form.get("name","").strip(); category=request.form.get("category","").strip(); brand=request.form.get("brand","").strip()
        try: sid=int(request.form.get("supplier_id","")); price=float(request.form.get("unit_price","")); stock=int(request.form.get("stock_quantity","")); exp=request.form.get("expiration_date","")
        except ValueError: flash("Price, stock and supplier must have valid values.","danger"); return render_template("medicine_form.html",suppliers=suppliers,row=None)
        if not name or not category or not brand or not exp: flash("All medicine fields are required.","danger")
        elif price<=0 or stock<0: flash("Price must be greater than 0 and stock cannot be negative.","danger")
        elif not c.execute("SELECT 1 FROM suppliers WHERE id=?",(sid,)).fetchone(): flash("Selected supplier does not exist.","danger")
        else:
            c.execute("INSERT INTO medicines(name,category,brand,supplier_id,unit_price,stock_quantity,expiration_date) VALUES(?,?,?,?,?,?,?)",(name,category,brand,sid,price,stock,exp)); c.commit()
            flash("Medicine added successfully.","success"); return redirect(url_for("medicines"))
    return render_template("medicine_form.html",suppliers=suppliers,row=None)

@app.route("/medicines/<int:id>/edit",methods=["GET","POST"])
@login_required
def edit_medicine(id):
    c=db(); row=c.execute("SELECT * FROM medicines WHERE id=?",(id,)).fetchone(); suppliers=c.execute("SELECT * FROM suppliers ORDER BY company_name").fetchall()
    if not row: return "Medicine not found",404
    if request.method=="POST":
        try: price=float(request.form["unit_price"]); stock=int(request.form["stock_quantity"]); sid=int(request.form["supplier_id"])
        except ValueError: flash("Invalid number.","danger"); return render_template("medicine_form.html",suppliers=suppliers,row=row)
        if price<=0 or stock<0: flash("Invalid price or stock.","danger")
        else:
            c.execute("UPDATE medicines SET name=?,category=?,brand=?,supplier_id=?,unit_price=?,stock_quantity=?,expiration_date=? WHERE id=?",
            (request.form["name"].strip(),request.form["category"].strip(),request.form["brand"].strip(),sid,price,stock,request.form["expiration_date"],id)); c.commit()
            flash("Medicine updated.","success"); return redirect(url_for("medicines"))
    return render_template("medicine_form.html",suppliers=suppliers,row=row)

@app.route("/medicines/<int:id>/delete",methods=["POST"])
@login_required
@admin_required
def delete_medicine(id):
    try: db().execute("DELETE FROM medicines WHERE id=?",(id,)); db().commit(); flash("Medicine deleted.","success")
    except sqlite3.IntegrityError: flash("Cannot delete medicine with sales.","danger")
    return redirect(url_for("medicines"))

# ---------- SALES ----------
@app.route("/sales",methods=["GET","POST"])
@login_required
def sales():
    c=db()
    if request.method=="POST":
        try: cid=int(request.form["customer_id"]); mid=int(request.form["medicine_id"]); qty=int(request.form["quantity"])
        except ValueError: flash("Customer, medicine and quantity are required.","danger"); return redirect(url_for("sales"))
        pay=request.form.get("payment_method",""); allowed={"Cash","Card","GCash"}
        med=c.execute("SELECT * FROM medicines WHERE id=?",(mid,)).fetchone()
        if not c.execute("SELECT 1 FROM customers WHERE id=?",(cid,)).fetchone(): flash("Customer does not exist.","danger")
        elif not med: flash("Medicine does not exist.","danger")
        elif qty<1 or qty>med["stock_quantity"]: flash("Quantity must be within available stock.","danger")
        elif pay not in allowed: flash("Invalid payment method.","danger")
        else:
            total=qty*med["unit_price"]; today=date.today().isoformat()
            c.execute("INSERT INTO sales(customer_id,medicine_id,quantity,payment_method,sale_date,total_amount) VALUES(?,?,?,?,?,?)",(cid,mid,qty,pay,today,total))
            c.execute("UPDATE medicines SET stock_quantity=stock_quantity-? WHERE id=?",(qty,mid)); c.commit()
            flash("Sale recorded successfully.","success"); return redirect(url_for("sales"))
    rows=c.execute("""SELECT sales.*,customers.name customer_name,medicines.name medicine_name FROM sales
      JOIN customers ON customers.id=sales.customer_id JOIN medicines ON medicines.id=sales.medicine_id ORDER BY sales.id DESC""").fetchall()
    customers=c.execute("SELECT * FROM customers ORDER BY name").fetchall(); meds=c.execute("SELECT * FROM medicines WHERE stock_quantity>0 ORDER BY name").fetchall()
    return render_template("sales.html",rows=rows,customers=customers,meds=meds)

@app.route("/sales/<int:id>/delete",methods=["POST"])
@login_required
@admin_required
def delete_sale(id):
    c=db(); s=c.execute("SELECT * FROM sales WHERE id=?",(id,)).fetchone()
    if s: c.execute("UPDATE medicines SET stock_quantity=stock_quantity+? WHERE id=?",(s["quantity"],s["medicine_id"])); c.execute("DELETE FROM sales WHERE id=?",(id,)); c.commit(); flash("Sale deleted and stock restored.","success")
    return redirect(url_for("sales"))

@app.route("/api/validate/medicine",methods=["POST"])
@login_required
def validate_medicine_api():
    data=request.get_json(silent=True) or {}
    if not data.get("name"): return error("name","Medicine name is required")
    if not isinstance(data.get("unit_price"),(int,float)) or data["unit_price"]<=0: return error("unit_price","Unit price must be a number greater than 0")
    return jsonify(status=200,message="Valid")

if __name__=="__main__":
    with app.app_context(): init_db()
    app.run(debug=True)
