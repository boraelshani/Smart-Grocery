import { randomUUID } from "crypto";
import { List, PublicList } from "../models/index.js";
import { recalculateListTotal } from "./pricing.service.js";

export const createList = async ({ userId, name }) => {
  const row = await List.create({
    listId: `list_${randomUUID()}`,
    userId,
    name,
    items: [],
    totalPrice: 0
  });
  return row.toObject();
};

export const addItemToList = async ({ listId, item }) => {
  const list = await List.findOne({ listId });
  if (!list) {
    throw Object.assign(new Error("List not found"), { status: 404 });
  }

  const existing = list.items.findIndex(
    (x) => x.productId === item.productId && (x.storeId || null) === (item.storeId || null)
  );

  if (existing >= 0) {
    list.items[existing].quantity += item.quantity || 1;
  } else {
    list.items.push({
      productId: item.productId,
      storeId: item.storeId || null,
      quantity: item.quantity || 1,
      checked: false
    });
  }

  await list.save();
  return recalculateListTotal(listId);
};

export const toggleListItemChecked = async ({ listId, productId, storeId, checked }) => {
  const list = await List.findOne({ listId });
  if (!list) {
    throw Object.assign(new Error("List not found"), { status: 404 });
  }

  const row = list.items.find((x) => x.productId === productId && (x.storeId || null) === (storeId || null));
  if (!row) {
    throw Object.assign(new Error("List item not found"), { status: 404 });
  }

  row.checked = Boolean(checked);
  await list.save();
  return list.toObject();
};

export const shareList = async (listId) => {
  const list = await List.findOne({ listId });
  if (!list) {
    throw Object.assign(new Error("List not found"), { status: 404 });
  }

  list.shared = true;
  if (!list.shareCode) {
    list.shareCode = randomUUID().slice(0, 10);
  }

  await list.save();
  return list.toObject();
};

export const publishAsPublicTemplate = async ({ listId, type, creatorUserId, name_en, name_de, description_en, description_de }) => {
  const list = await List.findOne({ listId }).lean();
  if (!list) {
    throw Object.assign(new Error("List not found"), { status: 404 });
  }

  const publicList = await PublicList.create({
    id: `public_${randomUUID()}`,
    type,
    name_en,
    name_de,
    description_en,
    description_de,
    creatorUserId,
    items: list.items,
    popularityScore: 0
  });

  return publicList.toObject();
};
