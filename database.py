import os
# pyrefly: ignore [missing-import]
import asyncpg
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://kassa:kassa_secret@localhost:5432/kassa_db"
)

pool: asyncpg.Pool = None


async def init_db():
    """Create connection pool and ensure tables exist."""
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bestellingen (
                id            SERIAL PRIMARY KEY,
                tafelnummer   INTEGER,
                datum         TEXT NOT NULL,
                totaalbedrag  NUMERIC(10,2) NOT NULL,
                created_at    TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bestelling_items (
                id              SERIAL PRIMARY KEY,
                bestelling_id   INTEGER NOT NULL REFERENCES bestellingen(id) ON DELETE CASCADE,
                product_id      INTEGER NOT NULL,
                naam            TEXT NOT NULL,
                prijs           NUMERIC(10,2) NOT NULL,
                qty             INTEGER NOT NULL,
                categorie       TEXT
            );
        """)
    logger.info("Database geïnitialiseerd")


async def close_db():
    """Close the connection pool."""
    global pool
    if pool:
        await pool.close()
        pool = None


async def save_order(tafelnummer, datum, artikelen, totaalbedrag):
    """Insert an order with its items. Returns the order id."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            order_id = await conn.fetchval(
                """
                INSERT INTO bestellingen (tafelnummer, datum, totaalbedrag)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                tafelnummer, datum, float(totaalbedrag)
            )

            for item in artikelen:
                await conn.execute(
                    """
                    INSERT INTO bestelling_items
                        (bestelling_id, product_id, naam, prijs, qty, categorie)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    order_id,
                    item["id"],
                    item["naam"],
                    float(item["prijs"]),
                    item["qty"],
                    item.get("categorie"),
                )

    logger.info(f"Bestelling {order_id} opgeslagen (tafel {tafelnummer})")
    return order_id
