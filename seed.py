from app import app, db, User, Pharmacy, Medicine, Inventory

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Users
        u = User(name="Test User", email="test@example.com")
        u.set_password("test123")
        db.session.add(u)

        # Pharmacies
        p1 = Pharmacy(name="HealthPlus Pharmacy", address="MG Road, Bengaluru",
                      latitude=12.9716, longitude=77.5946, phone="+91-9999999991")
        p2 = Pharmacy(name="CityCare Medicals", address="Jubilee Hills, Hyderabad",
                      latitude=17.4449, longitude=78.3933, phone="+91-9999999992")

        db.session.add_all([p1, p2])

        # Medicines
        m1 = Medicine(name="Dolo 650", generic_name="Paracetamol", strength="650 mg", form="Tablet")
        m2 = Medicine(name="Paracetamol 650 mg", generic_name="Paracetamol", strength="650 mg", form="Tablet")
        m3 = Medicine(name="Azithral 500", generic_name="Azithromycin", strength="500 mg", form="Tablet")
        db.session.add_all([m1, m2, m3])
        db.session.flush()

        # Inventory (prices in INR)
        db.session.add_all([
            Inventory(pharmacy_id=1, medicine_id=m1.id, price=28.0, stock_qty=20),
            Inventory(pharmacy_id=1, medicine_id=m2.id, price=22.0, stock_qty=15),
            Inventory(pharmacy_id=2, medicine_id=m1.id, price=29.5, stock_qty=30),
            Inventory(pharmacy_id=2, medicine_id=m3.id, price=120.0, stock_qty=10),
        ])

        db.session.commit()
        print("Database seeded. Login with email: test@example.com, password: test123")

if __name__ == "__main__":
    seed()
