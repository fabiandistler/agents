export async function syncPrices(apiUrl, db, logger) {
  logger.info("starting sync");

  const res = await fetch(apiUrl);
  if (!res.ok) throw new Error("bad response");
  const payload = await res.json();

  const updates = [];
  for (const item of payload.items) {
    const existing = await db.getProduct(item.sku);
    const price = Number(item.price);
    if (!existing || existing.price !== price || existing.currency !== item.currency) {
      updates.push({
        sku: item.sku,
        price: price,
        currency: item.currency,
      });
    }
  }

  for (const update of updates) {
    await db.upsertPrice(update);
    logger.info(`updated ${update.sku}`);
  }

  logger.info(`finished sync with ${updates.length} updates`);
  return updates.length;
}
