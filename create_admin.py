
import getpass
import mysql.connector
from werkzeug.security import generate_password_hash

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Wadawaowao@123",
    database="public_transport"
)

email = input("Admin email: ").strip().lower()
password = getpass.getpass("Admin password: ")

if not email or len(password) < 8:
    raise ValueError("Enter an email and a password of at least 8 characters.")

cursor = db.cursor()

try:
    cursor.execute(
        """
        INSERT INTO Accounts (email, password_hash, role)
        VALUES (%s, %s, 'admin')
        """,
        (email, generate_password_hash(password))
    )
    db.commit()
    print("Admin account created successfully.")

except mysql.connector.Error as error:
    db.rollback()
    print("Could not create admin:", error)

finally:
    cursor.close()
    db.close()
