import { List, Product, StoreProduct } from "../models/index.js";

export const effectivePrice = (storeProduct) =>
  storeProduct?.promoPrice ?? storeProduct?.basePrice ?? 0;

export const getCheapestStoreProductForProduct = async (productId, preferredStoreId = null) => {
  const query = { productId, isAvailable: true };

  if (preferredStoreId) {
    const preferred = await StoreProduct.findOne({ ...query, storeId: preferredStoreId })
      .sort({ promoPrice: 1, basePrice: 1 })
      .lean();
    if (preferred) {
      return preferred;
    }
  }

  return StoreProduct.findOne(query)
    .sort({ promoPrice: 1, basePrice: 1, lastPriceUpdate: -1 })
    .lean();
};

export const recalculateListTotal = async (listId) => {
  const list = await List.findOne({ listId });
  if (!list) {
    throw Object.assign(new Error("List not found"), { status: 404 });
  }

  let total = 0;

  for (let i = 0; i < list.items.length; i += 1) {
    const item = list.items[i];
    const offer = await getCheapestStoreProductForProduct(item.productId, item.storeId);
    const unitPrice = effectivePrice(offer);
    const lineTotal = Number((unitPrice * item.quantity).toFixed(2));

    list.items[i].unitPrice = unitPrice;
    list.items[i].lineTotal = lineTotal;
    total += lineTotal;
  }

  list.totalPrice = Number(total.toFixed(2));
  await list.save();
  return list.toObject();
};

export const refreshListPricesByProduct = async (productId) => {
  const affectedLists = await List.find({ "items.productId": productId }).select({ listId: 1 }).lean();
  for (const row of affectedLists) {
    await recalculateListTotal(row.listId);
  }
};

export const updateCheapestStoreProjection = async (productId) => {
  const cheapest = await getCheapestStoreProductForProduct(productId);
  await Product.updateOne(
    { productId },
    {
      $set: {
        cheapestStoreProductId: cheapest?.storeProductId || null,
        cheapestPrice: cheapest ? effectivePrice(cheapest) : null
      }
    }
  );
};
