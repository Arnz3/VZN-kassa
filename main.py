from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from escpos.printer import Usb
import logging

app = FastAPI()

# Configure CORS to allow the frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for the incoming JSON payload
class Artikel(BaseModel):
    id: int
    naam: str
    prijs: float
    qty: int
    categorie: str = None

class OrderData(BaseModel):
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
    try:
        # Initialize USB Printer
        p = Usb(USB_VENDOR_ID, USB_PRODUCT_ID)

        # Header
        p.set(align='center', font='a', width=2, height=2)
        p.text("VRIJE ZWEMMERS NIEUWPOORT\n")
        p.text("=================\n\n")

        p.set(align='left', font='a', width=1, height=1)
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
        p.text("Bedankt voor uw bestelling!\n")
        p.text("===========================\n\n\n\n\n\n")
        
        p.cut()
        
        logger.info(f"Ticket succesvol geprint: {order.totaalbedrag}")
        return {"status": "success", "message": "Ticket printed"}
        
    except Exception as e:
        logger.error(f"Printer error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Printer fout: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
