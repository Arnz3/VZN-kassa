from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from escpos.printer import Usb
from database import init_db, close_db, save_order
import logging

# 1. Log configuratie
logging.basicConfig(
    filename='/home/arnz3/logs/vzn_kassa.log',
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s]: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ── Lifespan: DB connect / disconnect ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(lifespan=lifespan)

# Configure CORS to allow the frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for the incoming JSON payload
class Artikel(BaseModel):
    id: int
    naam: str
    prijs: float
    qty: int
    categorie: str = None

class OrderData(BaseModel):
    tafelnummer: int = None
    datum: str
    artikelen: List[Artikel]
    totaalbedrag: str

# USB Printer Configuration
# LET OP: Je moet de Vendor ID en Product ID van jouw USB printer invullen.
# Op macOS kun je deze vinden door `system_profiler SPUSBDataType` in de terminal uit te voeren.
# Converteer de hex waardes (zoals 0x04b8).
USB_VENDOR_ID = 0x1fc9  # Placeholder (Epson default)
USB_PRODUCT_ID = 0x2016 # Placeholder (Epson default)

@app.post("/print")
async def print_ticket(order: OrderData):
    # ── 1. Printen ──────────────────────────────────────────────
    p = None
    try:
        # Initialize USB Printer
        p = Usb(USB_VENDOR_ID, USB_PRODUCT_ID)

        # Header
        p.set(align='center', font='a', width=2, height=2)
        p.text("VRIJE ZWEMMERS\n")
        p.text("NIEUWPOORT\n")
        p.set(align='center', font='a', width=1, height=1)
        p.text("=" * 48 + "\n\n")

        # Tafel & datum
        p.set(align='left', font='a', width=1, height=1)
        if order.tafelnummer is not None:
            p.set(align='center', font='a', width=2, height=2)
            p.text(f"TAFEL {order.tafelnummer}\n")
            p.set(align='left', font='a', width=1, height=1)
            p.text("\n")
        p.text(f"Datum: {order.datum}\n\n")
        
        # Print items (aangepast voor een standaard 80mm printer = 48 karakters. Verander 48 naar 32 voor 58mm)
        PRINTER_WIDTH = 48
        
        for item in order.artikelen:
            subtotal = item.prijs * item.qty
            line = f"{item.qty}x {item.naam}"
            price_str = f"EUR {subtotal:.2f}"
            
            padding = PRINTER_WIDTH - len(line) - len(price_str)
            if padding > 0:
                p.text(f"{line}{' ' * padding}{price_str}\n")
            else:
                p.text(f"{line} {price_str}\n")

        p.text("\n" + "-" * PRINTER_WIDTH + "\n")
        
        p.set(align='right')
        p.text(f"TOTAAL: EUR {order.totaalbedrag}\n\n")
        
        p.set(align='center')
        p.text("Bedankt voor uw bestelling!\n\n")
        p.text("=" * 48 + "\n")
        p.text("www.vzn.be\n")
        
        p.cut()
        
    except Exception as e:
        logger.error(f"Printer error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Printer fout: {str(e)}")
    finally:
        if p:
            p.close()

    # ── 2. Opslaan in database (enkel als printen is gelukt) ─────
    try:
        order_id = await save_order(
            tafelnummer=order.tafelnummer,
            datum=order.datum,
            artikelen=[a.model_dump() for a in order.artikelen],
            totaalbedrag=order.totaalbedrag,
        )
    except Exception as e:
        logger.error(f"Database error: {e}")
        # We raise hier ook een error, maar het ticket is wel al geprint!
        raise HTTPException(status_code=500, detail=f"Database fout (ticket wel geprint!): {e}")

    logger.info(f"Ticket #{order_id} succesvol geprint en opgeslagen: EUR {order.totaalbedrag}")
    return {"status": "success", "message": "Ticket printed and saved", "order_id": order_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
