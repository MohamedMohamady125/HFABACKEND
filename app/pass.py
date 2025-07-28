from passlib.hash import bcrypt

password = "Adham1234!"
password_hash = bcrypt.hash(password)
print(password_hash)