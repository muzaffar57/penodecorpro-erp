# tools/vaqt_sayohati/sitecustomize.py — kech105: `tools/vaqt_sayohati.sh` uchun. Shu papka PYTHONPATH ga qo'yilsa, har
# Python jarayoni VAQT_SAYOHAT paytiga ko'chadi (time-machine, tick=True — soat shu paytdan yuradi). O'zgaruvchi berilmasa
# hech narsa qilmaydi. Faqat SINOV asbobi — ilova kodi uni import qilmaydi.
import os

_t = os.environ.get("VAQT_SAYOHAT")
if _t:
    import time_machine
    _sayohat = time_machine.travel(_t, tick=True)
    _sayohat.start()
