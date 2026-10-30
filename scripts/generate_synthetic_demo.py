"""Generates synthetic, leak-free demo data for COD Compass.

Ensures the public repository can be run and tested without access to the private dataset.
Contains ZERO real customer names, phone numbers, or residential addresses.
All records are explicitly labeled with SYN_ prefixes.
"""

from __future__ import annotations

import csv
import os
import random
from datetime import datetime, timedelta

SYNTHETIC_NAMES = [
    "Aarav Sharma", "Vivaan Patel", "Aditya Verma", "Vihaan Iyer", "Arjun Gupta",
    "Sai Kumar", "Reyansh Reddy", "Ayaan Joshi", "Krishna Nair", "Ishaan Bhatia",
    "Diya Malhotra", "Saanvi Rao", "Ananya Deshmukh", "Aadhya Choudhury", "Pari Sen",
    "Kiara Kulkarni", "Myra Menon", "Riya Mukherjee", "Anvi Pillai", "Fatima Khan",
    "Zoya Siddiqui", "Meera Nambiar", "Tanvi Agarwal", "Kavya Bhatt", "Sneha Kapoor",
    "Pooja Mehta", "Rohan Das", "Nikhil Chopra", "Sameer Saxena", "Karan Singhal",
    # Intentionally include a small fraction of suspicious test names to test filters
    "Test User", "asdf asdf", "qwerty", "na na", "abc test"
]

CITIES_STATES = [
    ("Mumbai", "Maharashtra", "400001"),
    ("Pune", "Maharashtra", "411001"),
    ("Bengaluru", "Karnataka", "560001"),
    ("Mysuru", "Karnataka", "570001"),
    ("Delhi", "Delhi", "110001"),
    ("Noida", "Uttar Pradesh", "201301"),
    ("Gurugram", "Haryana", "122001"),
    ("Hyderabad", "Telangana", "500001"),
    ("Chennai", "Tamil Nadu", "600001"),
    ("Coimbatore", "Tamil Nadu", "641001"),
    ("Kolkata", "West Bengal", "700001"),
    ("Ahmedabad", "Gujarat", "380001"),
    ("Surat", "Gujarat", "395001"),
    ("Jaipur", "Rajasthan", "302001"),
    ("Lucknow", "Uttar Pradesh", "226001"),
    ("Patna", "Bihar", "800001"),
    ("Bhopal", "Madhya Pradesh", "462001"),
    ("Indore", "Madhya Pradesh", "452001"),
    ("Chandigarh", "Punjab", "160001"),
    ("Kochi", "Kerala", "682001")
]

PRODUCTS = [
    ("Redensyl Hair Growth Serum 50ml", 799.0),
    ("Rosemary & Biotin Anti-Hairfall Oil 100ml", 499.0),
    ("Fermented Rice Water Shampoo 250ml", 399.0),
    ("Deep Conditioning Keratin Hair Mask 200g", 649.0),
    ("Onion & Ginger Scalp Cleanser 200ml", 449.0),
    ("Peptide Volumizing Hair Mist 100ml", 599.0),
    ("Complete Hair Growth Trio (Serum + Oil + Shampoo)", 1499.0),
    ("Intense Damage Repair Combo (Mask + Serum)", 1199.0)
]

UTM_SOURCES = ["instagram", "facebook", "google_cpc", "influencer_collab", "organic", "whatsapp"]


def generate_synthetic_orders(num_orders: int = 500, output_path: str = "data/demo_orders.csv") -> None:
    random.seed(42)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    start_date = datetime(2026, 7, 1, 9, 0, 0)

    rows = []
    customer_memory = {}  # phone -> prior order stats

    for i in range(1, num_orders + 1):
        order_id = f"SYN{100000 + i}"
        order_time = start_date + timedelta(
            minutes=random.randint(0, 90 * 24 * 60)  # across July, August, September 2026
        )

        # 80% new customer, 20% repeat customer
        is_repeat = random.random() < 0.20 and len(customer_memory) > 10
        if is_repeat:
            phone, (cust_name, prior_orders, prior_rtos, city, state, pincode) = random.choice(
                list(customer_memory.items())
            )
            prior_orders += 1
            customer_memory[phone] = (cust_name, prior_orders, prior_rtos, city, state, pincode)
        else:
            cust_name = random.choice(SYNTHETIC_NAMES)
            phone = f"9{random.randint(100000000, 999999999)}"
            city, state, pincode = random.choice(CITIES_STATES)
            prior_orders = 0
            prior_rtos = 0
            customer_memory[phone] = (cust_name, prior_orders, prior_rtos, city, state, pincode)

        # Address generation
        if cust_name in ["Test User", "asdf asdf", "qwerty", "na na", "abc test"] or random.random() < 0.05:
            # Suspicious / incomplete address
            address = random.choice(["xyz", "home", ".", "near temple", "call before delivery", "asdfgh"])
        else:
            house_no = random.randint(1, 450)
            street = random.choice([
                "MG Road", "Link Road", "Station Road", "Gandhi Nagar", "Park Avenue",
                "Civil Lines", "Sector 14", "Green Park", "Banjara Hills", "Indiranagar"
            ])
            landmark = random.choice([
                "Opposite SBI Bank", "Near City Mall", "Behind Post Office", "Next to Metro Station",
                "Near Apollo Hospital"
            ])
            address = f"Flat {house_no}, {street}, {landmark}"

        # Items
        chosen_prod, prod_price = random.choice(PRODUCTS)
        num_items = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]
        order_value = prod_price * num_items

        utm = random.choice(UTM_SOURCES)

        # Determine outcome probabilistically based on signals
        rto_prob = 0.20  # base
        if prior_rtos >= 1:
            rto_prob += 0.40
        if len(address) < 15:
            rto_prob += 0.35
        if order_value > 1200:
            rto_prob += 0.12
        if utm == "instagram":
            rto_prob += 0.05

        rto_prob = min(0.95, max(0.05, rto_prob))
        final_status = "RTO" if random.random() < rto_prob else "DELIVERED"

        if final_status == "RTO":
            # update customer memory
            c_data = list(customer_memory[phone])
            c_data[2] += 1
            customer_memory[phone] = tuple(c_data)

        rows.append({
            "order_id": order_id,
            "order_datetime": order_time.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": cust_name,
            "phone": phone,
            "address": address,
            "city": city,
            "state": state,
            "pincode": pincode,
            "order_value": order_value,
            "items": f"{num_items}x {chosen_prod}",
            "num_items": num_items,
            "customer_prior_orders": prior_orders,
            "customer_prior_rto": prior_rtos,
            "utm_source": utm,
            "courier": random.choice(["Delhivery", "Bluedart", "Shadowfax", "Ekart"]),
            "payment_method": "COD",
            "final_status": final_status
        })

    # Sort chronologically
    rows.sort(key=lambda r: r["order_datetime"])

    fieldnames = [
        "order_id", "order_datetime", "customer_name", "phone", "address",
        "city", "state", "pincode", "order_value", "items", "num_items",
        "customer_prior_orders", "customer_prior_rto", "utm_source",
        "courier", "payment_method", "final_status"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} synthetic orders written to {output_path}")


if __name__ == "__main__":
    generate_synthetic_orders(500, "data/demo_orders.csv")

