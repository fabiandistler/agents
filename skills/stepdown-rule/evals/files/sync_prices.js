export async function syncPrices(apiUrl, db, logger) {
  logger.info("starting sync");

  const payload = await loadPricePayload(apiUrl);
  const updates = await collectPriceUpdates(payload.items, db);

  await writePriceUpdates(updates, db, logger);

  logger.info(`finished sync with ${updates.length} updates`);
  return updates.length;
}

async function loadPricePayload(apiUrl) {
  const res = await fetch(apiUrl);
  if (!res.ok) throw new Error("bad response");

  return res.json();
}

async function collectPriceUpdates(items, db) {
  const updates = [];

  for (const item of items) {
    if (await shouldUpdatePrice(item, db)) {
      updates.push({
        sku: item.sku,
        price: Number(item.price),
        currency: item.currency,
      });
    }
  }

  return updates;
}

async function shouldUpdatePrice(item, db) {
  const existing = await db.getProduct(item.sku);
  const price = Number(item.price);

  return !existing || existing.price !== price || existing.currency !== item.currency;
}

async function writePriceUpdates(updates, db, logger) {
  for (const update of updates) {
    await db.upsertPrice(update);
    logger.info(`updated ${update.sku}`);
  }
}
