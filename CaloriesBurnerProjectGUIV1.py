import sqlite3
import joblib
import datetime
import tkinter as tk
from tkinter import messagebox, ttk
import hashlib, re, random
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import os

DB_NAME = "calories_app.db"

# --- ML Model ---
model = joblib.load("linear_calories_model.pkl")
scaler = joblib.load("scaler.pkl")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # --- Ensure table schema is correct ---
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if not {"age","height","gender"}.issubset(set(cols)):
        cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("""CREATE TABLE IF NOT EXISTS users(
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE,
                        phone TEXT UNIQUE,
                        country TEXT,
                        password TEXT,
                        age INTEGER,
                        height REAL,
                        gender TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS predictions(
                        prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        weight REAL,
                        duration REAL,
                        heart_rate REAL,
                        body_temp REAL,
                        predicted_calories REAL,
                        created_at TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))""")
    conn.commit(); conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email)

def validate_phone(phone):
    return re.match(r"^\d{7,15}$", phone)

def password_strength(password):
    if len(password) < 6: return "Weak"
    if re.search(r"\d", password) and re.search(r"[A-Za-z]", password):
        return "Strong"
    return "Medium"

class CaloriesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fitness Tracker")
        self.geometry("1000x700")
        self.configure(bg="#f5f5f5")
        self.conn = sqlite3.connect(DB_NAME)
        self.cursor = self.conn.cursor()
        self.current_user_id = None
        self.signup_mode = tk.StringVar(value="email")
        self.login_mode = tk.StringVar(value="email")
        self.create_signup_page()

    # ---------- SIGNUP ----------
    def create_signup_page(self):
        for w in self.winfo_children(): w.destroy()
        tk.Label(self, text="Sign Up", font=("Arial", 22, "bold"), bg="#f5f5f5").pack(pady=10)

        tk.Label(self, text="Signup Method:", bg="#f5f5f5").pack()
        tk.Radiobutton(self, text="Email", variable=self.signup_mode, value="email", bg="#f5f5f5").pack()
        tk.Radiobutton(self, text="Phone", variable=self.signup_mode, value="phone", bg="#f5f5f5").pack()

        self.signup_email = self._add_entry("Email")
        self.signup_phone = self._add_entry("Phone")
        self.update_signup_fields()

        self.country_var = tk.StringVar(value="Egypt")
        tk.Label(self, text="Country", bg="#f5f5f5").pack()
        ttk.Combobox(self, textvariable=self.country_var,
                     values=["Egypt","Saudi Arabia","UAE","USA","UK"], state="readonly").pack(pady=5)

        self.signup_password = self._add_password_entry("Password")
        self.strength_label = tk.Label(self, text="", fg="blue", bg="#f5f5f5"); self.strength_label.pack()
        self.signup_password.bind("<KeyRelease>", self.update_strength)

        self.age_var = tk.IntVar(); self.height_var = tk.DoubleVar()
        self.gender_var = tk.StringVar(value="Male")
        tk.Label(self, text="Age", bg="#f5f5f5").pack(); tk.Entry(self, textvariable=self.age_var).pack(pady=5)
        tk.Label(self, text="Height (cm)", bg="#f5f5f5").pack(); tk.Entry(self, textvariable=self.height_var).pack(pady=5)
        tk.Label(self, text="Gender", bg="#f5f5f5").pack()
        ttk.Combobox(self, textvariable=self.gender_var, values=["Male","Female"], state="readonly").pack()

        tk.Button(self, text="Sign Up", command=self.verify_code, bg="#007BFF", fg="white").pack(pady=10)
        tk.Button(self, text="Go to Login", command=self.create_login_page, bg="#ccc").pack(pady=5)
        self.signup_mode.trace_add("write", lambda *a: self.update_signup_fields())

    def update_signup_fields(self):
        if self.signup_mode.get() == "email":
            self.signup_email.config(state="normal")
            self.signup_phone.delete(0, tk.END)
            self.signup_phone.config(state="disabled")
        else:
            self.signup_phone.config(state="normal")
            self.signup_email.delete(0, tk.END)
            self.signup_email.config(state="disabled")

    def update_strength(self, e):
        strength = password_strength(self.signup_password.get())
        colors = {"Weak": "red", "Medium": "orange", "Strong": "green"}
        self.strength_label.config(text=f"Strength: {strength}", fg=colors[strength])

    def verify_code(self):
        mode = self.signup_mode.get()
        email, phone = self.signup_email.get(), self.signup_phone.get()
        if mode == "email" and not validate_email(email):
            messagebox.showerror("Error", "Invalid email format"); return
        if mode == "phone" and not validate_phone(phone):
            messagebox.showerror("Error", "Invalid phone number"); return
        if password_strength(self.signup_password.get()) == "Weak":
            messagebox.showerror("Error", "Password too weak"); return

        self.generated_code = str(random.randint(100000, 999999))
        messagebox.showinfo("Verification", f"Verification code: {self.generated_code}")

        code_window = tk.Toplevel(self); code_window.title("Enter Verification Code")
        tk.Label(code_window, text="Enter the code sent:").pack(pady=5)
        self.code_entry = tk.Entry(code_window); self.code_entry.pack(pady=5)
        tk.Button(code_window, text="Verify",
                  command=lambda: self.register_user(mode, email, phone, code_window)).pack()

    def register_user(self, mode, email, phone, code_window):
        if self.code_entry.get() != self.generated_code:
            messagebox.showerror("Error", "Invalid verification code"); return
        try:
            self.cursor.execute("""INSERT INTO users(email, phone, country, password, age, height, gender)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (email if mode=="email" else None,
                                 phone if mode=="phone" else None,
                                 self.country_var.get(),
                                 hash_password(self.signup_password.get()),
                                 self.age_var.get(),
                                 self.height_var.get(),
                                 self.gender_var.get()))
            self.conn.commit()
            messagebox.showinfo("Success", "Signup successful. Please login.")
            code_window.destroy()
            self.create_login_page()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Email/Phone already exists")

    # ---------- LOGIN ----------
    def create_login_page(self):
        for w in self.winfo_children(): w.destroy()
        tk.Label(self, text="Login", font=("Arial", 22, "bold"), bg="#f5f5f5").pack(pady=10)
        tk.Label(self, text="Login Method:", bg="#f5f5f5").pack()
        tk.Radiobutton(self, text="Email", variable=self.login_mode, value="email", bg="#f5f5f5").pack()
        tk.Radiobutton(self, text="Phone", variable=self.login_mode, value="phone", bg="#f5f5f5").pack()

        self.login_email = self._add_entry("Email")
        self.login_phone = self._add_entry("Phone")
        self.update_login_fields()

        self.login_password = self._add_password_entry("Password")
        tk.Button(self, text="Login", command=self.login_user, bg="#007BFF", fg="white").pack(pady=10)
        tk.Button(self, text="Go to Signup", command=self.create_signup_page, bg="#ccc").pack(pady=5)
        self.login_mode.trace_add("write", lambda *a: self.update_login_fields())

    def update_login_fields(self):
        if self.login_mode.get() == "email":
            self.login_email.config(state="normal")
            self.login_phone.delete(0, tk.END)
            self.login_phone.config(state="disabled")
        else:
            self.login_phone.config(state="normal")
            self.login_email.delete(0, tk.END)
            self.login_email.config(state="disabled")

    def login_user(self):
        mode = self.login_mode.get()
        password = hash_password(self.login_password.get())
        if mode == "email":
            self.cursor.execute("SELECT user_id FROM users WHERE email=? AND password=?", (self.login_email.get(), password))
        else:
            self.cursor.execute("SELECT user_id FROM users WHERE phone=? AND password=?", (self.login_phone.get(), password))
        user = self.cursor.fetchone()
        if user:
            self.current_user_id = user[0]
            self.create_main_page()
        else:
            messagebox.showerror("Error", "Invalid login credentials")

    # ---------- MAIN PAGE ----------
    def create_main_page(self):
        for w in self.winfo_children(): w.destroy()
        tk.Label(self, text="Dashboard", font=("Arial", 20, "bold"), bg="#f5f5f5").pack(pady=10)

        self.weight_var = tk.DoubleVar(); self.duration_var = tk.DoubleVar()
        self.hr_var = tk.DoubleVar(); self.temp_var = tk.DoubleVar()
        tk.Label(self, text="Weight (kg)", bg="#f5f5f5").pack(); tk.Entry(self, textvariable=self.weight_var).pack()
        tk.Label(self, text="Workout Duration (min)", bg="#f5f5f5").pack(); tk.Entry(self, textvariable=self.duration_var).pack()
        tk.Label(self, text="Heart Rate", bg="#f5f5f5").pack(); tk.Entry(self, textvariable=self.hr_var).pack()
        tk.Label(self, text="Body Temp (°C)", bg="#f5f5f5").pack(); tk.Entry(self, textvariable=self.temp_var).pack()

        tk.Button(self, text="Save & Predict", command=self.save_prediction, bg="#007BFF", fg="white").pack(pady=10)
        tk.Button(self, text="Show Charts", command=self.show_charts, bg="#28a745", fg="white").pack(pady=5)
        tk.Button(self, text="Logout", command=self.create_login_page, bg="#dc3545", fg="white").pack(pady=5)

        columns = ("Date","Weight","Duration","Heart Rate","Body Temp","Calories")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        for col in columns: self.tree.heading(col, text=col); self.tree.column(col, width=120)
        self.tree.pack(pady=20)
        self.load_records()

    def load_records(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.cursor.execute("""SELECT created_at, weight, duration, heart_rate, body_temp, predicted_calories
                               FROM predictions WHERE user_id=? ORDER BY created_at DESC""", (self.current_user_id,))
        for row in self.cursor.fetchall(): self.tree.insert("", "end", values=row)

    def save_prediction(self):
        self.cursor.execute("SELECT height FROM users WHERE user_id=?", (self.current_user_id,))
        height = self.cursor.fetchone()[0] / 100.0
        weight = self.weight_var.get()
        duration, hr, temp = self.duration_var.get(), self.hr_var.get(), self.temp_var.get()
        X = scaler.transform([[self.get_user_age(), weight, duration, hr, temp,
                               1 if self.get_user_gender()=="Male" else 0, height]])
        predicted_calories = model.predict(X)[0]
        self.cursor.execute("""INSERT INTO predictions(user_id, weight, duration, heart_rate, body_temp, predicted_calories, created_at)
                               VALUES (?,?,?,?,?,?,?)""",
                            (self.current_user_id, weight, duration, hr, temp,
                             predicted_calories, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit(); self.load_records()
        messagebox.showinfo("Result", f"Calories Burned: {predicted_calories:.2f}\nBMI Advice: {self.bmi_advice(weight, height)}")

    def get_user_age(self):
        self.cursor.execute("SELECT age FROM users WHERE user_id=?", (self.current_user_id,))
        return self.cursor.fetchone()[0]

    def get_user_gender(self):
        self.cursor.execute("SELECT gender FROM users WHERE user_id=?", (self.current_user_id,))
        return self.cursor.fetchone()[0]

    def bmi_advice(self, weight, height):
        bmi = weight / (height ** 2)
        if bmi < 18.5: return "Underweight: Eat more calories."
        elif bmi < 24.9: return "Normal: Maintain diet & workout."
        else: return "Overweight: Reduce calories & increase activity."

    def show_charts(self):
        self.cursor.execute("SELECT weight, created_at FROM predictions WHERE user_id=? ORDER BY created_at", (self.current_user_id,))
        data = self.cursor.fetchall()
        if not data:
            messagebox.showinfo("Info", "No records yet."); return
        weights = [r[0] for r in data]; dates = [r[1] for r in data]
        self.cursor.execute("SELECT height FROM users WHERE user_id=?", (self.current_user_id,))
        height = self.cursor.fetchone()[0] / 100.0
        bmis = [w/(height**2) for w in weights]
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 6))
        ax1.plot(dates, weights, marker='o', color='blue'); ax1.set_title("Weight Trend"); ax1.set_ylabel("Weight (kg)")
        ax2.plot(dates, bmis, marker='o', color='green'); ax2.set_title("BMI Trend"); ax2.set_ylabel("BMI")
        plt.xticks(rotation=45); plt.tight_layout()
        win = tk.Toplevel(self); win.title("Progress Charts")
        canvas = FigureCanvasTkAgg(fig, master=win); canvas.draw(); canvas.get_tk_widget().pack()

    def _add_entry(self, label):
        tk.Label(self, text=label, bg="#f5f5f5").pack()
        e = tk.Entry(self); e.pack(pady=5); return e

    def _add_password_entry(self, label):
        tk.Label(self, text=label, bg="#f5f5f5").pack()
        entry = tk.Entry(self, show="*"); entry.pack(pady=5)
        var = tk.IntVar()
        tk.Checkbutton(self, text="Show", variable=var,
                       command=lambda: entry.config(show="" if var.get() else "*"), bg="#f5f5f5").pack()
        return entry

if __name__ == "__main__":
    init_db()
    CaloriesApp().mainloop()
