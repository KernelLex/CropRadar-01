import sqlite3, time

db = sqlite3.connect(r'D:\Z-work\CropRadar\CropRadar-01\cropradar.db')
for i in range(3):
    db.execute(
        "INSERT INTO disease_reports (disease_type, confidence, latitude, longitude, timestamp) "
        "VALUES ('Leaf Blight', 0.91, 12.97, 77.59, ?)",
        (time.time() - i * 100,)
    )
db.commit()
db.close()
print("3 fake Leaf Blight reports inserted near Bangalore!")
