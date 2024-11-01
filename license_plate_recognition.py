import cv2
import pytesseract
import re
import sqlite3
#import RPi.GPIO as GPIO
#import time

pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# Ustawienia GPIO
#SERVO_PIN = 18  # Ustaw pin GPIO dla serwa
#GPIO.setmode(GPIO.BCM)
#GPIO.setup(SERVO_PIN, GPIO.OUT)

# Inicjalizuj serwo
#servo = GPIO.PWM(SERVO_PIN, 50)  # 50 Hz
#servo.start(0)  # Ustaw serwo w pozycji 0

def init_db():
    conn = sqlite3.connect('license_plates.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL UNIQUE
        )
    ''')
    conn.commit()
    return conn

def extract_license_plate_text(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 100, 200)
    contours, _ = cv2.findContours(edged, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)

        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)

            if 2 < aspect_ratio < 5:
                license_plate = gray[y:y + h, x:x + w]
                license_plate = cv2.equalizeHist(license_plate)
                _, license_plate = cv2.threshold(license_plate, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                license_plate = cv2.dilate(license_plate, kernel, iterations=1)
                license_plate = cv2.erode(license_plate, kernel, iterations=1)

                custom_config = r'--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                text = pytesseract.image_to_string(license_plate, config=custom_config)

                if text.startswith("PL"):
                    text = text[2:].strip()

                #zamianki
                text = text.replace("|", "I")
                text = text.replace(" ", "")
                text = re.sub(r'(?<![A-Z0-9])1(?![A-Z0-9])', 'I', text)
                text = text.strip()

                #text = text.replace("S", "5")  # Zamiana S na 5
                text = re.sub(r'(?<=F|L|C)S', '5', text)  # Przykład kontekstu, gdzie S może być 5
                text = re.sub(r'(?<=R)5', 'S', text)  # Przykład kontekstu, gdzie 5 może być S

                print(f"Odczytana tablica: {text.strip()}")

                cv2.imshow("License Plate", license_plate)

                return text.strip()

    return None

#def lift_gate():
#    servo.ChangeDutyCycle(7)  # Ustaw kąt serwa do podniesienia szlabanu
#    time.sleep(1)  # Czas na podniesienie
#    servo.ChangeDutyCycle(0)  # Zatrzymaj sygnał PWM

def save_to_db(conn, plate):
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO plates (plate) VALUES (?)', (plate,))
        conn.commit()
        print(f"Tablica '{plate}' została zapisana w bazie danych.")
    except sqlite3.IntegrityError:
        print("Tablica już istnieje w bazie danych.")

def check_plate_in_db(conn, plate):
    cursor = conn.cursor()
    cursor.execute('SELECT plate FROM plates WHERE plate = ?', (plate,))
    return cursor.fetchone() is not None

def interactive_mode(conn):
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        license_plate_text = extract_license_plate_text(frame)

        if license_plate_text:
            print("Znaleziono tablicę:", license_plate_text)

            confirmation = input("Czy tablica jest poprawna? (t/n): ").strip().lower()
            if confirmation == 't':
                save_to_db(conn, license_plate_text)

            exit_confirmation = input("Czy chcesz wrocic do menu? (t/n): ").strip().lower()
            if exit_confirmation == 't':
                break

        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) != -1:
            break

    cap.release()
    cv2.destroyAllWindows()


def automatic_mode(conn):
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        license_plate_text = extract_license_plate_text(frame)

        if license_plate_text:
            print("Znaleziono tablicę:", license_plate_text)
            if check_plate_in_db(conn, license_plate_text):
                print(f"Tablica '{license_plate_text}' znajduje się w bazie danych!")
                #lift_gate()
                break

        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) != -1:
            break

    cap.release()
    cv2.destroyAllWindows()

def list_all_plates(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT plate FROM plates')
    rows = cursor.fetchall()
    if rows:
        print("Tablice w bazie danych:")
        for row in rows:
            print(row[0])
    else:
        print("Brak tablic w bazie danych.")

def main():
    conn = init_db()

    while True:
        print("Wybierz opcję:")
        print("1 - Tryb interaktywny")
        print("2 - Tryb automatyczny")
        print("3 - Wypisz tablice w bazie")
        print("0 - Zakończ program")
        choice = input("Twój wybór: ").strip()

        if choice == '1':
            interactive_mode(conn)
        elif choice == '2':
            automatic_mode(conn)
        elif choice == '3':
            list_all_plates(conn)
        elif choice == '0':
            break
        else:
            print("Nieznany wybór. Proszę wybrać opcję od 0 do 3.")

    #cap.release()
    #cv2.destroyAllWindows()
    conn.close()
    #GPIO.cleanup()

if __name__ == "__main__":
    main()
