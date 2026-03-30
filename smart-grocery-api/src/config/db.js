import mongoose from "mongoose";
import { env } from "./env.js";

export const connectMongo = async () => {
  if (!env.mongoUri) {
    throw new Error("MONGODB_URI is missing");
  }

  mongoose.set("strictQuery", true);
  await mongoose.connect(env.mongoUri, {
    maxPoolSize: 40,
    minPoolSize: 5,
    serverSelectionTimeoutMS: 5000,
    socketTimeoutMS: 30000
  });
};
