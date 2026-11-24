import socket
import urllib.request
import io
import threading
import time
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock
from kivy.core.window import Window

# === SÍŤOVÉ NASTAVENÍ DRONU ===
IP_DRONU = "192.168.0.100"  # Ujisti se, že sedí IP adresa tvého dronu!
PORT_UDP = 5005
URL_VIDEO = f"http://{IP_DRONU}:8080/stream.mjpg"

class DronKokpitLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        
        self.video_obraz = Image(allow_stretch=True, keep_ratio=True)
        self.add_widget(self.video_obraz)
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.posledni_jpeg = None
        self.bezi = True
        
        # Výchozí hodnoty pro ovládání
        self.jizda = 0.0
        self.zataceni = 0.0
        self.vertikal = 0.0
        self.povel_kamera = 0
        self.povel_reset = 0
        self.povel_prepnuti = 0
        self.povel_led = 0
        self.btn_plus = False
        self.btn_minus = False

        # Spuštění čtení MJPEG streamu na pozadí
        threading.Thread(target=self.vlakno_videa, daemon=True).start()
        
        # Časovače pro vykreslování obrazu (30 FPS) a odesílání povelů (25 Hz)
        Clock.schedule_interval(self.aktualizuj_obrazovku, 1.0 / 30.0)
        Clock.schedule_interval(self.odesli_povely_dronu, 0.04)

        # Nativní zachycení gamepadu a tlačítek přímo v Kivy (bez Pygame)
        Window.bind(on_keyboard=self.stisk_klavesy)
        Window.bind(on_joy_axis=self.pohyb_osy)
        Window.bind(on_joy_button_down=self.tlacitko_dolu)
        Window.bind(on_joy_button_up=self.tlacitko_nahoru)

    def vlakno_videa(self):
        while self.bezi:
            try:
                stream = urllib.request.urlopen(URL_VIDEO, timeout=5)
                bajt_data = b''
                while self.bezi:
                    bajt_data += stream.read(4096)
                    start = bajt_data.find(b'\xff\xd8')
                    konec = bajt_data.find(b'\xff\xd9')
                    if start != -1 and konec != -1:
                        jpg = bajt_data[start:konec+2]
                        bajt_data = bajt_data[konec+2:]
                        self.posledni_jpeg = jpg
            except:
                time.sleep(1.0)

    def aktualizuj_obrazovku(self, dt):
        if self.posledni_jpeg:
            data = io.BytesIO(self.posledni_jpeg)
            self.posledni_jpeg = None
            im = CoreImage(data, ext="jpg")
            self.video_obraz.texture = im.texture

    # --- OCHRANA PROTI ZAVŘENÍ APLIKACE TLAČÍTKEM B / ZPĚT ---
    def stisk_klavesy(self, window, key, *args):
        if key == 27:  # Systémové tlačítko Zpět (tlačítko B na ovladači)
            return True
        return False

    # --- NATIVNÍ ČTENÍ PÁČEK GAMEPADU V ANDROIDU ---
    def pohyb_osy(self, window, stickid, axisid, value):
        hodnota = round(value / 32768.0, 2)
        if abs(hodnota) < 0.12:
            hodnota = 0.0
            
        if axisid == 1:      # Levá páčka dopředu/dozadu
            self.jizda = -hodnota
        elif axisid == 0:    # Levá páčka doleva/doprava
            self.zataceni = hodnota
        elif axisid == 3 or axisid == 4:  # Pravá páčka nahoru/dolů (Android podle modelu)
            self.vertikal = -hodnota
        elif axisid == 2 or axisid == 5:  # Levá spoušť L2 (ubírání jasu LED)
            self.btn_minus = hodnota > 0.3

    # --- NATIVNÍ ČTENÍ TLAČÍTEK GAMEPADU V ANDROIDU ---
    def tlacitko_dolu(self, window, stickid, buttonid):
        if buttonid == 0:    # Tlačítko A (Kamera dolů)
            self.povel_kamera = -1
        elif buttonid == 3:  # Tlačítko Y (Kamera nahoru)
            self.povel_kamera = 1
        elif buttonid == 1:  # Tlačítko B (Reset horizontu)
            self.povel_reset = 1
        elif buttonid == 2:  # Tlačítko X (Přepnutí režimu)
            self.povel_prepnuti = 1
        elif buttonid == 4:  # Horní L1 (Přidání jasu LED)
            self.btn_plus = True
        elif buttonid == 6:  # Spodní L2 (pokud se hlásí jako tlačítko)
            self.btn_minus = True

    def tlacitko_nahoru(self, window, stickid, buttonid):
        if buttonid in (0, 3):
            self.povel_kamera = 0
        elif buttonid == 1:
            self.povel_reset = 0
        elif buttonid == 2:
            self.povel_prepnuti = 0
        elif buttonid == 4:
            self.btn_plus = False
        elif buttonid == 6:
            self.btn_minus = False

    def odesli_povely_dronu(self, dt):
        povel_led = 1 if self.btn_plus else (-1 if self.btn_minus else 0)
        data_string = f"{self.jizda},{self.zataceni},{self.vertikal},{self.povel_kamera},{self.povel_reset},{self.povel_prepnuti},{povel_led}"
        try:
            self.sock.sendto(data_string.encode('utf-8'), (IP_DRONU, PORT_UDP))
        except:
            pass

class DronApp(App):
    def build(self):
        Window.clear_color = (0.05, 0.05, 0.05, 1)
        return DronKokpitLayout()
        
    def on_stop(self):
        self.root.bezi = False

if __name__ == '__main__':
    DronApp().run()
