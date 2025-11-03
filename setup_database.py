import sqlite3
import os

# Define the path for the database
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "sample_data.db")

# Ensure the database directory exists
os.makedirs(DB_DIR, exist_ok=True)

# SQL statements for creating tables
create_customer_orders_table = """
CREATE TABLE IF NOT EXISTS customer_orders (
    OrderID TEXT PRIMARY KEY NOT NULL,
    CustomerID TEXT NOT NULL,
    OrderDate TEXT NOT NULL,
    Quantity INTEGER NOT NULL CHECK(Quantity > 0),
    Price REAL NOT NULL,
    DiscountCode TEXT
);
"""

create_products_table = """
CREATE TABLE IF NOT EXISTS products (
    ProductID TEXT PRIMARY KEY NOT NULL,
    ProductName TEXT NOT NULL,
    Category TEXT,
    Price REAL NOT NULL CHECK(Price >= 0),
    Stock INTEGER NOT NULL CHECK(Stock >= 0)
);
"""

# SQL statements for inserting sample historical data
insert_orders_data = """
INSERT INTO customer_orders (OrderID, CustomerID, OrderDate, Quantity, Price, DiscountCode)
VALUES
    ('ORD1001', 'CUST001', '2025-10-20', 5, 19.99, 'SAVE10'),
    ('ORD1002', 'CUST002', '2025-10-21', 2, 45.50, NULL),
    ('ORD1003', 'CUST001', '2025-10-22', 1, 150.00, 'NEW25');
"""

insert_products_data = """
INSERT INTO products (ProductID, ProductName, Category, Price, Stock)
VALUES
    ('PROD001', 'Laptop', 'Electronics', 1200.00, 50),
    ('PROD002', 'Mouse', 'Electronics', 25.50, 150),
    ('PROD003', 'Coffee Mug', 'Homeware', 15.00, 300);
"""

try:
    # Connect to the SQLite database (it will be created if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Database connection established.")

    # Create tables
    cursor.execute(create_customer_orders_table)
    print("Table 'customer_orders' created successfully.")
    
    cursor.execute(create_products_table)
    print("Table 'products' created successfully.")

    # Insert sample data (checking if empty first to avoid duplicates on re-run)
    cursor.execute("SELECT COUNT(*) FROM customer_orders")
    if cursor.fetchone()[0] == 0:
        cursor.execute(insert_orders_data)
        print("Sample data inserted into 'customer_orders'.")
    else:
        print("'customer_orders' already contains data.")

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute(insert_products_data)
        print("Sample data inserted into 'products'.")
    else:
        print("'products' already contains data.")

    # Commit changes and close the connection
    conn.commit()
    print("Changes committed.")

except sqlite3.Error as e:
    print(f"An error occurred: {e}")

finally:
    if conn:
        conn.close()
        print("Database connection closed.")